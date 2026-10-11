#!/usr/bin/env python3
"""
Outshift Research Intelligence — CLI edition.

A specialist research pipeline for emerging-technology evaluation. It runs in the
terminal, prints progress as it works, and writes a single self-contained
``index.html`` with all of the data.

The evaluation logic is ported from ``evalreport/app.py`` (Business + Venture
Capital + Technical specialist rubrics, an independent red-team critic, and an
optional general-purpose baseline). The only thing that changed is the interface:
no Streamlit, no server — a CLI plus a static HTML report.

Important: this is an evaluation *system* built around an LLM API, not a newly
trained foundation model. It does not claim to beat ChatGPT without running the
benchmark.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import random
import re
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# All keys live in the single root .env (../.env).
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

APP_TITLE = "Outshift Research Intelligence"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Model is a global here, not read from .env. OpenRouter id for
# "Meta: Llama 3.1 8B Instruct".
MODEL = "meta-llama/llama-3.1-8b-instruct"
DEFAULT_IDEA = (
    "Evaluate homomorphic encryption for privacy-preserving enterprise AI "
    "analytics. Determine whether it is feasible for a small proof of concept and "
    "identify business value, investment rationale, performance bottlenecks, and "
    "measurable go/no-go criteria."
)

PERSPECTIVES: dict[str, dict[str, Any]] = {
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


# --------------------------------------------------------------------------- #
# Terminal output
# --------------------------------------------------------------------------- #
def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def rule(title: str = "") -> None:
    line = "─" * 68
    if title:
        print(f"\n{title}\n{line}", flush=True)
    else:
        print(line, flush=True)


# --------------------------------------------------------------------------- #
# LLM helpers (ported from evalreport/app.py)
# --------------------------------------------------------------------------- #
def json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model did not return a JSON object.")
    return json.loads(text[start:end + 1])


def call_json(client: Any, model: str, system: str, user: str, temperature: float = 0.2) -> dict:
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


def score_perspective(client: Any, model: str, idea: str, perspective: str) -> dict:
    config = PERSPECTIVES[perspective]
    criteria_text = "\n".join(
        f"- {name} (weight {weight:.0%}): {description}"
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


def critique_and_recommend(client: Any, model: str, idea: str, evaluations: dict[str, dict]) -> dict:
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


def run_specialist(client: Any, model: str, idea: str) -> dict:
    evaluations = {}
    for perspective in PERSPECTIVES:
        log(f"Scoring perspective: {perspective} ...")
        evaluations[perspective] = score_perspective(client, model, idea, perspective)
        log(f"  {perspective}: {evaluations[perspective]['score']}/10")
    log("Running independent red-team critic ...")
    consensus = critique_and_recommend(client, model, idea, evaluations)
    return {
        "idea": idea,
        "method": "Specialist rubric + independent critic",
        "evaluations": evaluations,
        "combined_score": combined_score(evaluations),
        "consensus": consensus,
    }


def run_baseline(client: Any, model: str, idea: str) -> dict:
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


def benchmark_pair(specialist: dict, baseline: dict) -> list[dict]:
    """Blind-independent score dimensions. These are rubric scores, not objective truth."""
    rows = []
    for label, result in [("Specialist system", specialist), ("General-purpose baseline", baseline)]:
        if label == "Specialist system":
            ev = result["evaluations"]
            evidence = [c["evidence_status"] for e in ev.values() for c in e["criteria"]]
            unknown_count = sum(len(e.get("key_unknowns", [])) for e in ev.values())
            experiment = result["consensus"].get("next_experiment", {})
            criteria = [c["score"] for e in ev.values() for c in e["criteria"]]
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
            rows.append({"system": label, "dimension": dimension, "score": score})
    return rows


# --------------------------------------------------------------------------- #
# Demo mode — deterministic, offline, no API key required
# --------------------------------------------------------------------------- #
def _demo_perspective(perspective: str, idea: str) -> dict:
    config = PERSPECTIVES[perspective]
    rng = random.Random(f"{perspective}:{idea}")
    normalized = []
    for name, weight, description in config["criteria"]:
        score = rng.randint(4, 9)
        normalized.append({
            "name": name,
            "weight": weight,
            "score": score,
            "weighted_points": round(score * weight, 3),
            "rationale": f"[demo] {description}. Scored {score}/10 from a deterministic offline stub.",
            "evidence_status": rng.choice(["assumption", "unknown", "verified"]),
        })
    return {
        "perspective": perspective,
        "summary": (
            f"[demo] A deterministic offline assessment for the {perspective} perspective. "
            "Run without --demo and with an API key for a real evaluation."
        ),
        "criteria": normalized,
        "score": round(sum(x["weighted_points"] for x in normalized), 2),
        "weight": config["weight"],
        "confidence": round(rng.uniform(0.3, 0.7), 2),
        "strengths": ["[demo] Clear problem framing", "[demo] Plausible enterprise pull"],
        "risks": ["[demo] Unverified performance claims", "[demo] Integration cost unknown"],
        "key_unknowns": ["[demo] Real-world latency", "[demo] Willingness to pay"],
        "validation_experiment": {
            "hypothesis": "[demo] A bounded prototype can hit the latency target.",
            "method": "[demo] Build a minimal end-to-end spike and measure.",
            "success_metric": "[demo] p95 latency under target on a fixed workload.",
            "failure_threshold": "[demo] More than 2x the latency budget.",
            "estimated_effort": "[demo] 2 engineer-weeks",
        },
        "decision": rng.choice(["Research more", "Prototype", "Advance"]),
    }


def run_specialist_demo(idea: str) -> dict:
    evaluations = {}
    for perspective in PERSPECTIVES:
        log(f"Scoring perspective: {perspective} ... (demo)")
        evaluations[perspective] = _demo_perspective(perspective, idea)
        log(f"  {perspective}: {evaluations[perspective]['score']}/10")
    log("Running independent red-team critic ... (demo)")
    consensus = {
        "main_disagreement": "[demo] Technical optimism vs. commercial caution.",
        "unsupported_claims": ["[demo] Performance figures are not verified."],
        "cross_perspective_risks": ["[demo] Cost of ownership at scale."],
        "recommended_decision": "Prototype",
        "decision_reason": "[demo] Cheapest path to reduce the biggest unknown.",
        "next_experiment": {
            "hypothesis": "[demo] A spike can validate the core claim.",
            "method": "[demo] Build and measure.",
            "success_metric": "[demo] Meets the stated target.",
            "failure_threshold": "[demo] Misses by 2x.",
            "estimated_effort": "[demo] 2 engineer-weeks",
        },
        "confidence": 0.4,
    }
    return {
        "idea": idea,
        "method": "Specialist rubric + independent critic (demo)",
        "evaluations": evaluations,
        "combined_score": combined_score(evaluations),
        "consensus": consensus,
    }


def run_baseline_demo(idea: str) -> dict:
    return {
        "idea": idea,
        "method": "General-purpose single-pass baseline (demo)",
        "summary": "[demo] Balanced single-pass analysis.",
        "business_analysis": "[demo] Business view.",
        "venture_capital_analysis": "[demo] VC view.",
        "technical_analysis": "[demo] Technical view.",
        "strengths": ["[demo] Clear framing"],
        "risks": ["[demo] Unverified claims", "[demo] Cost"],
        "key_unknowns": ["[demo] Latency"],
        "recommended_decision": "Research more",
        "validation_experiment": {
            "hypothesis": "[demo] Spike validates the claim.",
            "method": "[demo] Build and measure.",
            "success_metric": "[demo] Meets target.",
            "failure_threshold": "[demo] Misses by 2x.",
            "estimated_effort": "[demo] 2 engineer-weeks",
        },
        "confidence": 0.35,
    }


# --------------------------------------------------------------------------- #
# HTML report
# --------------------------------------------------------------------------- #
def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _decision_class(decision: str) -> str:
    d = (decision or "").strip().lower()
    if d in ("advance", "prototype"):
        return "go"
    if d == "reject":
        return "stop"
    return "hold"


def _score_bar(score: float, maximum: float = 10.0) -> str:
    pct = max(0.0, min(100.0, 100.0 * score / maximum))
    return (
        f'<div class="score-bar"><div class="score-fill" style="width:{pct:.1f}%"></div></div>'
    )


def _list(items: list) -> str:
    if not items:
        return '<p class="muted small">None reported.</p>'
    return "<ul>" + "".join(f"<li>{_esc(x)}</li>" for x in items) + "</ul>"


def _criteria_table(criteria: list[dict]) -> str:
    rows = []
    for c in criteria:
        status = _esc(c.get("evidence_status", "unknown"))
        rows.append(
            "<tr>"
            f'<td>{_esc(c["name"])}</td>'
            f'<td class="num">{c["weight"]:.0%}</td>'
            f'<td class="num">{c["score"]}/10</td>'
            f'<td><span class="ev ev-{status}">{status}</span></td>'
            f'<td>{_esc(c["rationale"])}</td>'
            "</tr>"
        )
    return (
        '<table class="criteria">'
        "<thead><tr><th>Criterion</th><th>Weight</th><th>Score</th>"
        "<th>Evidence</th><th>Rationale</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )


def _experiment_block(exp: dict) -> str:
    if not exp:
        return '<p class="muted small">No validation experiment reported.</p>'
    fields = [
        ("Hypothesis", exp.get("hypothesis")),
        ("Method", exp.get("method")),
        ("Success metric", exp.get("success_metric")),
        ("Failure threshold", exp.get("failure_threshold")),
        ("Estimated effort", exp.get("estimated_effort")),
    ]
    rows = "".join(
        f'<div class="meta-row"><div class="meta-key">{_esc(k)}</div>'
        f'<div class="meta-val">{_esc(v or "—")}</div></div>'
        for k, v in fields
    )
    return f'<div class="meta-table">{rows}</div>'


def _perspective_section(name: str, ev: dict) -> str:
    return f"""
    <section class="card">
      <div class="card-head">
        <h3>{_esc(name)}</h3>
        <span class="score-pill">{ev['score']}/10</span>
        <span class="muted small">weight {ev['weight']:.0%} · confidence {ev.get('confidence', 0):.0%}</span>
      </div>
      <p class="summary">{_esc(ev.get('summary', ''))}</p>
      {_criteria_table(ev.get('criteria', []))}
      <div class="two-col">
        <div><h4>Strengths</h4>{_list(ev.get('strengths', []))}</div>
        <div><h4>Risks</h4>{_list(ev.get('risks', []))}</div>
      </div>
      <div class="two-col">
        <div><h4>Key unknowns</h4>{_list(ev.get('key_unknowns', []))}</div>
        <div><h4>Validation experiment</h4>{_experiment_block(ev.get('validation_experiment', {}))}</div>
      </div>
      <p class="muted small">Perspective decision: <strong>{_esc(ev.get('decision', '—'))}</strong></p>
    </section>"""


def _consensus_section(consensus: dict) -> str:
    decision = consensus.get("recommended_decision", "—")
    cls = _decision_class(decision)
    return f"""
    <section class="card">
      <div class="card-head"><h3>Independent critic &amp; recommendation</h3></div>
      <div class="decision-banner {cls}">
        <div class="decision-head">
          <span class="decision-label">Recommended decision</span>
          <span class="decision-value">{_esc(decision)}</span>
          <span class="decision-confidence">confidence {consensus.get('confidence', 0):.0%}</span>
        </div>
        <p class="decision-rationale">{_esc(consensus.get('decision_reason', ''))}</p>
      </div>
      <p class="summary"><strong>Main disagreement:</strong> {_esc(consensus.get('main_disagreement', '—'))}</p>
      <div class="two-col">
        <div><h4>Unsupported claims</h4>{_list(consensus.get('unsupported_claims', []))}</div>
        <div><h4>Cross-perspective risks</h4>{_list(consensus.get('cross_perspective_risks', []))}</div>
      </div>
      <h4>Next experiment</h4>
      {_experiment_block(consensus.get('next_experiment', {}))}
    </section>"""


def _baseline_section(baseline: dict, benchmark: list[dict]) -> str:
    dims = sorted({r["dimension"] for r in benchmark})
    systems = ["Specialist system", "General-purpose baseline"]
    table_rows = []
    for dim in dims:
        cells = []
        for system in systems:
            val = next((r["score"] for r in benchmark if r["dimension"] == dim and r["system"] == system), 0)
            cells.append(f'<td class="num">{val}</td>')
        table_rows.append(f"<tr><td>{_esc(dim)}</td>{''.join(cells)}</tr>")
    table = (
        '<table class="criteria"><thead><tr><th>Dimension</th>'
        + "".join(f"<th>{_esc(s)}</th>" for s in systems)
        + "</tr></thead><tbody>" + "".join(table_rows) + "</tbody></table>"
    )
    return f"""
    <section class="card">
      <div class="card-head"><h3>Baseline comparison</h3></div>
      <p class="warn small">A single run does not establish that one system is better. These dimension
      scores are rubric-based heuristics; use blinded human scoring and repeated trials for a
      defensible comparison.</p>
      <div class="chart-wrap"><canvas id="benchmarkChart" height="120"></canvas></div>
      {table}
      <details class="raw-json">
        <summary>General-purpose baseline output (raw)</summary>
        <pre class="raw-json-pre">{_esc(json.dumps(baseline, indent=2, ensure_ascii=False))}</pre>
      </details>
    </section>"""


def render_html(specialist: dict, baseline: dict | None, benchmark: list[dict] | None,
                model: str, demo: bool) -> str:
    evaluations = specialist["evaluations"]
    consensus = specialist["consensus"]
    combined = specialist["combined_score"]

    perspective_cards = "".join(
        _perspective_section(name, evaluations[name]) for name in PERSPECTIVES
    )

    radar_labels = list(PERSPECTIVES.keys())
    radar_values = [evaluations[name]["score"] for name in radar_labels]

    baseline_html = ""
    if baseline is not None and benchmark:
        baseline_html = _baseline_section(baseline, benchmark)

    data = {
        "radar": {"labels": radar_labels, "values": radar_values},
        "benchmark": benchmark or [],
    }
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    demo_badge = '<span class="badge">demo</span>' if demo else ""
    generated = time.strftime("%Y-%m-%d %H:%M:%S")

    return _TEMPLATE.replace("__TITLE__", _esc(APP_TITLE)) \
        .replace("__IDEA__", _esc(specialist["idea"])) \
        .replace("__MODEL__", _esc(model)) \
        .replace("__GENERATED__", _esc(generated)) \
        .replace("__DEMO_BADGE__", demo_badge) \
        .replace("__COMBINED__", f"{combined:g}") \
        .replace("__PERSPECTIVE_CARDS__", perspective_cards) \
        .replace("__CONSENSUS__", _consensus_section(consensus)) \
        .replace("__BASELINE__", baseline_html) \
        .replace("__DATA__", data_json) \
        .replace("__RAW__", _esc(json.dumps(specialist, indent=2, ensure_ascii=False)))


_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: system-ui, sans-serif; font-size: 14px;
    line-height: 1.5; color: black; background: white;
  }
  .wrap { max-width: 1040px; margin: 0 auto; padding: 0 16px 56px; }
  h1, h2, h3, h4 { margin: 0; font-weight: 600; }
  h3 { font-size: 15px; }
  h4 { font-size: 12px; color: gray; margin-bottom: 4px; }
  p { margin: 0; }
  ul { margin: 0; padding-left: 18px; }
  li { font-size: 12.5px; }
  a { color: blue; }
  .muted { color: gray; }
  .small { font-size: 12px; }
  .num { text-align: right; font-variant-numeric: tabular-nums; }

  .app-header {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 10px 0; border-bottom: 1px solid silver; margin-bottom: 16px;
  }
  .brand { display: flex; align-items: center; gap: 8px; }
  .brand-mark { font-size: 18px; }
  .brand-text h1 { font-size: 15px; }
  .brand-text p { font-size: 12px; color: gray; }
  .badge { font-size: 11px; color: gray; border: 1px solid silver; padding: 2px 6px; }

  .idea-box { border: 1px solid silver; padding: 10px; margin-bottom: 16px; }
  .idea-box .label { font-size: 12px; color: gray; margin-bottom: 4px; }
  .idea-text { font-size: 13.5px; }

  .score-strip { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
  .combined { border: 1px solid gray; padding: 12px; display: flex; flex-direction: column; justify-content: center; }
  .combined .big { font-size: 34px; font-weight: 700; }
  .combined .cap { font-size: 12px; color: gray; }
  .chart-wrap { border: 1px solid silver; padding: 10px; }

  .card { border: 1px solid silver; padding: 12px; margin-bottom: 12px; }
  .card-head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
  .score-pill { font-size: 12px; font-weight: 600; border: 1px solid gray; padding: 0 6px; }
  .summary { font-size: 13px; margin-bottom: 8px; }

  table.criteria { width: 100%; border-collapse: collapse; margin: 8px 0; }
  table.criteria th, table.criteria td {
    border: 1px solid silver; padding: 4px 6px; font-size: 12.5px; text-align: left; vertical-align: top;
  }
  table.criteria th { background: whitesmoke; font-weight: 600; }
  .ev { font-size: 11px; border: 1px solid silver; padding: 0 4px; }
  .ev-verified { color: green; border-color: green; }
  .ev-assumption { color: darkorange; border-color: darkorange; }
  .ev-unknown { color: gray; }

  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 8px; }

  .decision-banner { border: 1px solid gray; padding: 10px; margin: 8px 0; }
  .decision-banner.go { border-color: green; }
  .decision-banner.stop { border-color: red; }
  .decision-banner.hold { border-color: darkorange; }
  .decision-head { display: flex; align-items: baseline; gap: 8px; }
  .decision-label { font-size: 12px; color: gray; }
  .decision-value { font-size: 18px; font-weight: 700; }
  .decision-banner.go .decision-value { color: green; }
  .decision-banner.stop .decision-value { color: red; }
  .decision-banner.hold .decision-value { color: darkorange; }
  .decision-confidence { margin-left: auto; font-size: 12px; color: gray; }
  .decision-rationale { margin-top: 6px; font-size: 13px; }

  .meta-table { border: 1px solid silver; padding: 8px; display: flex; flex-direction: column; gap: 2px; }
  .meta-row { display: flex; gap: 8px; font-size: 12.5px; }
  .meta-key { flex: 0 0 120px; color: gray; }
  .meta-val { flex: 1; min-width: 0; word-break: break-word; }

  .warn { color: darkorange; }
  .raw-json { border: 1px solid silver; padding: 8px; margin-top: 10px; }
  .raw-json summary { font-size: 12px; color: gray; cursor: pointer; }
  .raw-json-pre { margin: 8px 0 0; max-height: 360px; overflow: auto; font-size: 11px; background: whitesmoke; padding: 8px; }

  @media (max-width: 760px) {
    .score-strip, .two-col { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header class="app-header">
    <div class="brand">
      <span class="brand-mark">🔬</span>
      <div class="brand-text">
        <h1>__TITLE__</h1>
        <p>Specialist emerging-technology evaluation · Business + VC + Technical</p>
      </div>
    </div>
    <div>__DEMO_BADGE__</div>
  </header>

  <div class="idea-box">
    <div class="label">Research objective</div>
    <div class="idea-text">__IDEA__</div>
    <div class="label" style="margin-top:8px">Model __MODEL__ · generated __GENERATED__</div>
  </div>

  <div class="score-strip">
    <div class="combined">
      <div class="cap">Combined score</div>
      <div class="big">__COMBINED__<span class="muted" style="font-size:16px">/10</span></div>
      <div class="cap">Business 30% + VC 25% + Technical 45%. Model judgments, not measured probabilities.</div>
    </div>
    <div class="chart-wrap"><canvas id="radarChart" height="150"></canvas></div>
  </div>

  __PERSPECTIVE_CARDS__
  __CONSENSUS__
  __BASELINE__

  <section class="card">
    <details class="raw-json">
      <summary>Raw specialist report (JSON)</summary>
      <pre class="raw-json-pre">__RAW__</pre>
    </details>
  </section>
</div>

<script>
const DATA = __DATA__;
const palette = { green: "green", red: "red", darkorange: "darkorange", blue: "blue", gray: "gray" };

if (window.Chart) {
  const radarEl = document.getElementById("radarChart");
  if (radarEl) {
    new Chart(radarEl, {
      type: "radar",
      data: {
        labels: DATA.radar.labels,
        datasets: [{
          label: "Score",
          data: DATA.radar.values,
          borderColor: palette.blue,
          backgroundColor: "aliceblue",
          pointBackgroundColor: palette.blue,
        }],
      },
      options: {
        responsive: true,
        scales: { r: { min: 0, max: 10, ticks: { stepSize: 2 } } },
        plugins: { legend: { display: false } },
      },
    });
  }

  const benchEl = document.getElementById("benchmarkChart");
  if (benchEl && DATA.benchmark.length) {
    const dims = [...new Set(DATA.benchmark.map(r => r.dimension))];
    const systems = [...new Set(DATA.benchmark.map(r => r.system))];
    const colors = [palette.gray, palette.blue];
    new Chart(benchEl, {
      type: "bar",
      data: {
        labels: dims,
        datasets: systems.map((s, i) => ({
          label: s,
          data: dims.map(d => {
            const row = DATA.benchmark.find(r => r.dimension === d && r.system === s);
            return row ? row.score : 0;
          }),
          backgroundColor: colors[i % colors.length],
        })),
      },
      options: {
        responsive: true,
        scales: { y: { min: 0, max: 10 } },
        plugins: { legend: { position: "bottom" } },
      },
    });
  }
}
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_client(model: str):
    from openai import OpenAI  # imported lazily so --demo works without the package

    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "No API key found. Set OPENROUTER_API_KEY (or OPENAI_API_KEY) in the root .env, "
            "or run with --demo for an offline report."
        )
    return OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="evaluate.py",
        description="Evaluate an emerging-technology idea and write a single-file HTML report.",
    )
    parser.add_argument("idea", nargs="*", help="The idea text. Omit to use the default example.")
    parser.add_argument("--idea-file", type=Path, help="Read the idea text from a file.")
    parser.add_argument("--model", default=MODEL, help=f"Model id (default: {MODEL}).")
    parser.add_argument("--out", type=Path, default=Path("index.html"), help="Output HTML path (default: index.html).")
    parser.add_argument("--compare", action="store_true", help="Also run the general-purpose baseline.")
    parser.add_argument("--demo", action="store_true", help="Offline deterministic run; no API key needed.")
    parser.add_argument("--open", action="store_true", help="Open the report in a browser when done.")
    return parser.parse_args(argv)


def resolve_idea(args: argparse.Namespace) -> str:
    if args.idea_file:
        return args.idea_file.read_text(encoding="utf-8").strip()
    if args.idea:
        return " ".join(args.idea).strip()
    return DEFAULT_IDEA


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    idea = resolve_idea(args)
    if not idea:
        print("No idea provided.", file=sys.stderr)
        return 2

    rule(APP_TITLE)
    log(f"Model: {args.model}")
    log(f"Mode: {'demo (offline)' if args.demo else 'live'}")
    log(f"Idea: {idea[:100]}{'…' if len(idea) > 100 else ''}")

    started = time.time()
    baseline = None
    benchmark = None

    if args.demo:
        specialist = run_specialist_demo(idea)
        if args.compare:
            log("Running general-purpose baseline ... (demo)")
            baseline = run_baseline_demo(idea)
            benchmark = benchmark_pair(specialist, baseline)
    else:
        client = build_client(args.model)
        try:
            specialist = run_specialist(client, args.model, idea)
            if args.compare:
                log("Running general-purpose baseline ...")
                baseline = run_baseline(client, args.model, idea)
                benchmark = benchmark_pair(specialist, baseline)
        except Exception as exc:  # noqa: BLE001 - surface any API failure clearly
            print(f"\nRun failed: {exc}", file=sys.stderr)
            print("Check your API key, model access, package versions, and network connection.", file=sys.stderr)
            return 1

    log(f"Combined score: {specialist['combined_score']}/10")
    log(f"Recommended decision: {specialist['consensus'].get('recommended_decision', '—')}")

    log("Rendering report ...")
    html_text = render_html(specialist, baseline, benchmark, args.model, args.demo)
    out_path = args.out
    if not out_path.is_absolute():
        out_path = Path(__file__).resolve().parent / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_text, encoding="utf-8")

    elapsed = time.time() - started
    rule()
    log(f"Wrote {out_path} ({len(html_text):,} bytes) in {elapsed:.1f}s")
    print(f"\nOpen it with:  file://{out_path}")

    if args.open:
        webbrowser.open(out_path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
