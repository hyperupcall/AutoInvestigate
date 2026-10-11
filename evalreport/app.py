"""
Outshift Research Intelligence
A specialist research pipeline for emerging-technology evaluation.

Important: This is an evaluation system built around an LLM API, not a newly trained
foundation model. It does not claim to beat ChatGPT without running the benchmark.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, asdict
from typing import Any

import pandas as pd
import streamlit as st
from openai import OpenAI

APP_TITLE = "Outshift Research Intelligence"
PERSPECTIVES = {
    "Business": {
        "weight": 0.30,
        "criteria": [
            ("Customer pain", 0.25, "Urgency, frequency, and cost of the problem"),
            ("Market opportunity", 0.20, "Reachable market and valuable niche"),
            ("Willingness to pay", 0.20, "Budget owner and measurable value"),
            ("Cisco / Outshift fit", 0.20, "Strategic fit with enterprise networking, security, and platform capabilities"),
            ("Adoption friction", 0.15, "Procurement, integration, trust, and behavior-change barriers"),
        ],
    },
    "Venture Capital": {
        "weight": 0.25,
        "criteria": [
            ("Upside / market size", 0.25, "Potential for a substantial business or strategic platform"),
            ("Timing", 0.15, "Why the opportunity is viable now"),
            ("Differentiation / moat", 0.20, "Durable advantage from IP, data, distribution, or ecosystem"),
            ("Capital efficiency", 0.15, "Time, talent, compute, and validation cost"),
            ("Growth potential", 0.15, "Expansion into adjacent markets or products"),
            ("Risk-adjusted return", 0.10, "Whether plausible upside justifies risks and resources"),
        ],
    },
    "Technical": {
        "weight": 0.45,
        "criteria": [
            ("Feasibility / maturity", 0.20, "Availability and maturity of algorithms, libraries, and reference implementations"),
            ("Architecture / integration", 0.20, "Integration with realistic enterprise systems"),
            ("Performance / scalability", 0.20, "Latency, throughput, and cost against explicit targets"),
            ("Security / privacy", 0.20, "Threat model, trust boundaries, and failure modes"),
            ("Prototype speed", 0.10, "How quickly the key hypothesis can be tested reproducibly"),
            ("Operational complexity", 0.10, "Deployment, monitoring, maintenance, and debugging"),
        ],
    },
}

SYSTEM_PROMPT = """You are a specialist research analyst for emerging technologies.
Be rigorous, skeptical, and decision-oriented. Never invent sources, benchmarks,
customer interviews, prices, market sizes, or performance measurements. Clearly label
assumptions and unknowns. Distinguish demonstrated facts from hypotheses. If browsing
or source retrieval is not available, explicitly say evidence is not verified.
Return valid JSON only, following the requested schema. Scores are 1-10, where 10 is
strong. Include concise rationales and a concrete validation experiment. A prototype
is not proof of production readiness or security.
"""

def json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model did not return a JSON object.")
    return json.loads(text[start:end + 1])

def call_json(client: OpenAI, model: str, system: str, user: str, temperature: float = 0.2) -> dict:
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return json_from_text(response.choices[0].message.content or "{}")

def score_perspective(client: OpenAI, model: str, idea: str, perspective: str) -> dict:
    config = PERSPECTIVES[perspective]
    criteria_text = "\n".join(
        f'- {name} (weight {weight:.0%}): {description}'
        for name, weight, description in config["criteria"]
    )
    prompt = f"""Evaluate this emerging-technology opportunity from the {perspective} perspective.

IDEA / RESEARCH OBJECTIVE:
{idea}

CRITERIA:
{criteria_text}

Return JSON:
{{
 "perspective": "{perspective}",
 "summary": "2-4 sentence assessment",
 "criteria": [
   {{"name": "criterion name", "weight": 0.0, "score": 1, "rationale": "why", "evidence_status": "verified|assumption|unknown"}}
 ],
 "strengths": ["..."],
 "risks": ["..."],
 "key_unknowns": ["..."],
 "validation_experiment": {{
   "hypothesis": "...",
   "method": "...",
   "success_metric": "...",
   "failure_threshold": "...",
   "estimated_effort": "..."
 }},
 "confidence": 0.0,
 "decision": "Reject|Research more|Prototype|Advance"
}}
Use exactly the criteria listed, weights as given, and integer scores from 1 to 10.
Confidence is 0 to 1 and must reflect evidence quality, not rhetorical certainty."""
    result = call_json(client, model, SYSTEM_PROMPT, prompt)
    # Enforce rubric weights and compute transparent criterion and perspective scores locally.
    returned = {item.get("name"): item for item in result.get("criteria", [])}
    normalized = []
    for name, weight, description in config["criteria"]:
        item = returned.get(name, {})
        try:
            score = max(1, min(10, int(item.get("score", 5))))
        except (ValueError, TypeError):
            score = 5
        normalized.append({
            "name": name,
            "weight": weight,
            "score": score,
            "weighted_points": round(score * weight, 3),
            "rationale": str(item.get("rationale", "No rationale returned.")),
            "evidence_status": str(item.get("evidence_status", "unknown")),
        })
    result["perspective"] = perspective
    result["criteria"] = normalized
    result["score"] = round(sum(x["weighted_points"] for x in normalized), 2)
    result["weight"] = config["weight"]
    result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.35))))
    return result

def critique_and_recommend(client: OpenAI, model: str, idea: str, evaluations: dict[str, dict]) -> dict:
    compact = {
        name: {
            "score": result["score"],
            "summary": result.get("summary", ""),
            "risks": result.get("risks", []),
            "key_unknowns": result.get("key_unknowns", []),
            "experiment": result.get("validation_experiment", {}),
        }
        for name, result in evaluations.items()
    }
    prompt = f"""You are an independent red-team reviewer. Do not simply average or agree with
the three specialist analyses. Identify unsupported assumptions, contradictions, and
the cheapest experiment that could change the decision.

Idea: {idea}
Specialist assessments:
{json.dumps(compact, ensure_ascii=False)}

Return JSON:
{{
 "main_disagreement": "...",
 "unsupported_claims": ["..."],
 "cross_perspective_risks": ["..."],
 "recommended_decision": "Reject|Research more|Prototype|Advance",
 "decision_reason": "...",
 "next_experiment": {{
   "hypothesis": "...", "method": "...", "success_metric": "...",
   "failure_threshold": "...", "estimated_effort": "..."
 }},
 "confidence": 0.0
}}
Do not invent evidence. If key claims are unknown, prefer Research more or a bounded Prototype."""
    return call_json(client, model, SYSTEM_PROMPT, prompt)

def combined_score(evaluations: dict[str, dict]) -> float:
    return round(sum(PERSPECTIVES[name]["weight"] * evaluations[name]["score"]
                     for name in PERSPECTIVES), 2)

def run_specialist(client: OpenAI, model: str, idea: str) -> dict:
    evaluations = {}
    for perspective in PERSPECTIVES:
        evaluations[perspective] = score_perspective(client, model, idea, perspective)
    consensus = critique_and_recommend(client, model, idea, evaluations)
    return {
        "idea": idea,
        "method": "Specialist rubric + independent critic",
        "evaluations": evaluations,
        "combined_score": combined_score(evaluations),
        "consensus": consensus,
    }

def run_baseline(client: OpenAI, model: str, idea: str) -> dict:
    """General-purpose baseline using one neutral prompt, with the same decision goal."""
    prompt = f"""Analyze this emerging-technology opportunity as a general-purpose assistant.
Use business, venture-capital, and technical perspectives. Give balanced analysis and
a recommendation, but do not use the specialist system's multi-agent rubric.

Idea: {idea}

Return JSON:
{{
 "summary": "...",
 "business_analysis": "...",
 "venture_capital_analysis": "...",
 "technical_analysis": "...",
 "strengths": ["..."],
 "risks": ["..."],
 "key_unknowns": ["..."],
 "recommended_decision": "Reject|Research more|Prototype|Advance",
 "validation_experiment": {{
   "hypothesis": "...", "method": "...", "success_metric": "...",
   "failure_threshold": "...", "estimated_effort": "..."
 }},
 "confidence": 0.0
}}
Never invent sources, data, or measurements. Label assumptions and unknowns."""
    return {
        "idea": idea,
        "method": "General-purpose single-pass baseline",
        **call_json(client, model, SYSTEM_PROMPT, prompt),
    }

def benchmark_pair(specialist: dict, baseline: dict) -> pd.DataFrame:
    """Blind-independent score dimensions. These are rubric scores, not objective truth."""
    rows = []
    for label, result in [("Specialist system", specialist), ("General-purpose baseline", baseline)]:
        if label == "Specialist system":
            ev = result["evaluations"]
            evidence = [c["evidence_status"] for e in ev.values() for c in e["criteria"]]
            unknown_count = sum(len(e.get("key_unknowns", [])) for e in ev.values())
            experiment = result["consensus"].get("next_experiment", {})
            criteria = [c["score"] for e in ev.values() for c in e["criteria"]]
            mean_coverage = len(criteria) / max(1, len(criteria))
            rubric_compliance = 10 if len(criteria) == sum(len(x["criteria"]) for x in PERSPECTIVES.values()) else 0
            evidence_transparency = max(1, min(10, round(10 * (evidence.count("verified") + 0.5 * evidence.count("assumption")) / max(1, len(evidence)))))
            experiment_quality = 7 if experiment.get("success_metric") and experiment.get("failure_threshold") else 3
            dimensions = {
                "Rubric coverage": rubric_compliance,
                "Evidence transparency": evidence_transparency,
                "Actionability": experiment_quality,
                "Risk / unknown visibility": max(1, min(10, 10 - min(9, unknown_count // 2))),
                "Output completeness": 9,
            }
        else:
            has = lambda key: bool(result.get(key))
            dimensions = {
                "Rubric coverage": 6 if has("business_analysis") and has("venture_capital_analysis") and has("technical_analysis") else 3,
                "Evidence transparency": 7 if has("key_unknowns") else 4,
                "Actionability": 7 if result.get("validation_experiment", {}).get("success_metric") else 3,
                "Risk / unknown visibility": min(10, 4 + len(result.get("risks", []))),
                "Output completeness": 8 if has("summary") and has("recommended_decision") else 4,
            }
        for dimension, score in dimensions.items():
            rows.append({"System": label, "Dimension": dimension, "Score (1-10)": score})
    return pd.DataFrame(rows)

st.set_page_config(page_title=APP_TITLE, page_icon="🔬", layout="wide")
st.title("🔬 Outshift Research Intelligence")
st.caption("Specialist emerging-technology evaluation · Business + VC + Technical · Benchmark against a baseline")
with st.sidebar:
    st.header("Model configuration")
    api_key = st.text_input("OpenAI API key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    model_name = st.text_input("Model name", value=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    st.caption("The API key is used only by this running app process. Do not commit it to source control.")
    st.divider()
    st.markdown("**Perspective weights**")
    for name, cfg in PERSPECTIVES.items():
        st.write(f"{name}: {cfg['weight']:.0%}")

idea = st.text_area(
    "Research objective / emerging technology",
    value="Evaluate homomorphic encryption for privacy-preserving enterprise AI analytics. Determine whether it is feasible for a small proof of concept and identify business value, investment rationale, performance bottlenecks, and measurable go/no-go criteria.",
    height=130,
)
run_col1, run_col2 = st.columns([1, 1])
with run_col1:
    run_specialist_btn = st.button("Run specialist system", type="primary", use_container_width=True)
with run_col2:
    run_compare_btn = st.button("Compare against baseline", use_container_width=True)

if run_specialist_btn or run_compare_btn:
    if not api_key:
        st.error("Add your API key in the sidebar, or set OPENAI_API_KEY in your environment.")
        st.stop()
    if not idea.strip():
        st.error("Enter a research objective first.")
        st.stop()
    client = OpenAI(api_key=api_key)
    with st.spinner("Evaluating the idea..."):
        try:
            specialist = run_specialist(client, model_name, idea)
            st.session_state["specialist_result"] = specialist
            if run_compare_btn:
                baseline = run_baseline(client, model_name, idea)
                st.session_state["baseline_result"] = baseline
                st.session_state["benchmark_df"] = benchmark_pair(specialist, baseline)
        except Exception as exc:
            st.error(f"Run failed: {exc}")
            st.info("Check your API key, model access, package versions, and network connection.")
            st.stop()

if "specialist_result" in st.session_state:
    result = st.session_state["specialist_result"]
    st.divider()
    st.header("Specialist system results")
    metric_cols = st.columns(4)
    metric_cols[0].metric("Combined score", f"{result['combined_score']}/10")
    metric_cols[1].metric("Business", f"{result['evaluations']['Business']['score']}/10")
    metric_cols[2].metric("Venture capital", f"{result['evaluations']['Venture Capital']['score']}/10")
    metric_cols[3].metric("Technical", f"{result['evaluations']['Technical']['score']}/10")
    st.caption("Combined score = Business 30% + VC 25% + Technical 45%. Scores are model judgments, not measured probabilities.")
    tabs = st.tabs(["Business", "Venture Capital", "Technical", "Consensus"])
    for tab, name in zip(tabs[:3], PERSPECTIVES):
        with tab:
            ev = result["evaluations"][name]
            st.subheader(f"{name}: {ev['score']}/10")
            st.write(ev.get("summary", ""))
            st.dataframe(pd.DataFrame(ev["criteria"]), use_container_width=True, hide_index=True)
            left, right = st.columns(2)
            with left:
                st.markdown("**Strengths**")
                st.write(ev.get("strengths", []))
                st.markdown("**Risks**")
                st.write(ev.get("risks", []))
            with right:
                st.markdown("**Key unknowns**")
                st.write(ev.get("key_unknowns", []))
                st.markdown("**Validation experiment**")
                st.json(ev.get("validation_experiment", {}))
            st.write(f"Confidence: {ev.get('confidence', 0):.0%}")
    with tabs[3]:
        st.subheader("Independent critic and recommendation")
        st.json(result["consensus"])
    st.download_button(
        "Export specialist report (JSON)",
        data=json.dumps(result, indent=2, ensure_ascii=False),
        file_name="specialist_research_report.json",
        mime="application/json",
    )

if "baseline_result" in st.session_state:
    st.divider()
    st.header("Baseline comparison")
    st.warning("A single run does not establish that one system is better. The current dimension scores are rubric-based heuristics; use blinded human scoring and repeated trials for a defensible comparison.")
    baseline = st.session_state["baseline_result"]
    st.subheader("General-purpose baseline output")
    st.json(baseline)
    if "benchmark_df" in st.session_state:
        df = st.session_state["benchmark_df"]
        pivot = df.pivot(index="Dimension", columns="System", values="Score (1-10)")
        st.dataframe(pivot, use_container_width=True)
        st.bar_chart(pivot)
        st.download_button(
            "Export comparison (CSV)",
            data=df.to_csv(index=False),
            file_name="baseline_comparison.csv",
            mime="text/csv",
        )

with st.expander("How to evaluate whether this actually performs better"):
    st.markdown("""
1. Build a fixed test set of at least 30–50 research objectives, not just one example.
2. Run both systems on identical inputs and model versions; randomize output labels before review.
3. Have two or more reviewers score evidence traceability, criterion coverage, useful technical tests,
   business/VC reasoning, calibration, and factual errors using a written rubric.
4. Verify factual claims and cited evidence independently; penalize unsupported specifics.
5. Report mean scores, variance, error rate, and confidence intervals. Do not declare a winner from one run.
6. For a fair comparison, give the baseline the same tools and access to evidence, or clearly state the difference.
""")
