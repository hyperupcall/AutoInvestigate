import os
import time
from pathlib import Path
from typing import List, Dict

import streamlit as st
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from openai import OpenAI

# All keys live in the single root .env (../.env).
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

st.set_page_config(
    page_title="Outshift Research Swarm",
    page_icon="🛰️",
    layout="wide",
)

AGENTS = [
    {
        "name": "Frontier Researcher",
        "emoji": "🔬",
        "goal": "Find novelty, scientific opportunity, relevant research directions, and what is genuinely unknown.",
        "style": "Curious and ambitious, but distinguish established facts from hypotheses.",
    },
    {
        "name": "Venture Analyst",
        "emoji": "📈",
        "goal": "Assess users, pain points, market potential, adoption barriers, and a plausible route to value.",
        "style": "Commercially minded; challenge ideas without a credible customer or benefit.",
    },
    {
        "name": "Technical Skeptic",
        "emoji": "🧪",
        "goal": "Test feasibility, implementation complexity, security, evaluation quality, and failure modes.",
        "style": "Constructively skeptical; request measurable claims and falsifiable experiments.",
    },
    {
        "name": "Cisco Opportunity Scout",
        "emoji": "🌐",
        "goal": "Assess strategic relevance to networking, security, observability, infrastructure, AI, and Cisco Outshift. If the topic is unrelated to Cisco, say so clearly and evaluate broader strategic relevance instead.",
        "style": "Look for concrete strategic fit without forcing a Cisco connection.",
    },
]

DEMO_RESPONSES = {
    "Frontier Researcher": "A promising research direction is to identify the narrowest capability that is both underexplored and testable. I would compare the proposed approach against current baselines, state which claims are hypotheses, and define what evidence would count as a meaningful advance.",
    "Venture Analyst": "The opportunity is only compelling if a specific user experiences a costly problem and would change their workflow for this solution. Before estimating market size, interview or model one initial customer segment and quantify the time, cost, or risk reduced.",
    "Technical Skeptic": "The current proposal needs a falsifiable success metric and a baseline. The main risk is confusing a polished demo with evidence of technical advantage. I recommend a small experiment, an explicit failure threshold, and a list of assumptions that have not been validated.",
    "Cisco Opportunity Scout": "Potential Cisco relevance depends on whether the idea improves networking, security, infrastructure, observability, or enterprise AI. I would not claim strategic fit until the use case and buyer are concrete. If the connection is weak, treat this as a general technology opportunity rather than forcing a Cisco narrative.",
}

def get_client(api_key: str):
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)

def ask_agent(client, model: str, agent: Dict, topic: str, goal: str,
              context: str, transcript: List[Dict], task: str) -> str:
    history = "\n\n".join(
        f"[Round {m['round']} — {m['agent']}]\n{m['text']}"
        for m in transcript[-18:]
    ) or "(No prior messages.)"

    prompt = f"""
You are the {agent['name']} in a multi-agent technology research debate.
Your independent objective: {agent['goal']}
Your style: {agent['style']}

USER'S TOPIC:
{topic}

USER'S OBJECTIVE:
{goal or "Explore this topic and identify a useful, testable opportunity."}

USER-PROVIDED CONTEXT:
{context or "No extra context supplied."}

DEBATE TRANSCRIPT SO FAR:
{history}

YOUR TASK:
{task}

Rules:
- Actually engage with the transcript. Name at least one specific prior claim or agent when a transcript exists.
- Make your reasoning useful and concrete. Separate facts, assumptions, and hypotheses.
- Do not invent citations, papers, repository links, market statistics, or experimental results.
- If evidence is missing, say what source or experiment would be needed.
- Where appropriate, propose a small experiment with a metric, baseline, and pass/fail threshold.
- Be concise (roughly 120–220 words).
- End with: POSITION: SUPPORT / MODIFY / OPPOSE / UNCERTAIN — followed by one sentence explaining why.
"""
    response = client.responses.create(model=model, input=prompt)
    return response.output_text.strip()

def demo_reply(agent: Dict, transcript: List[Dict], task: str, topic: str) -> str:
    base = DEMO_RESPONSES[agent["name"]]
    if transcript:
        prior = transcript[-1]
        return (
            f"Responding to {prior['agent']}'s latest point: “{prior['text'][:220].strip()}...”\n\n"
            f"{base}\n\nFor **{topic}**, I would turn this into a testable question: what measurable result would demonstrate an advantage over a credible baseline? I would revise my position if that test failed or stronger evidence contradicted the premise.\n\n"
            "POSITION: MODIFY — the direction is worth investigating, but the evidence and evaluation plan need to be made concrete."
        )
    return (
        f"{base}\n\nFor **{topic}**, first define the problem, baseline, and smallest useful test. The current assessment is preliminary; no external sources or experiments have been checked in demo mode.\n\n"
        "POSITION: UNCERTAIN — the opportunity is plausible but needs evidence."
    )

def summarize(client, model, topic, goal, transcript, context):
    history = "\n\n".join(
        f"[Round {m['round']} — {m['agent']}]\n{m['text']}" for m in transcript
    )
    prompt = f"""
Summarize this multi-agent research debate. Do not pretend the agents reached consensus if they did not.
Topic: {topic}
Objective: {goal}
Context: {context}
Transcript:
{history}

Return these headings:
1. Current recommendation
2. Points of agreement
3. Unresolved disagreements
4. Strongest assumptions / missing evidence
5. Best next experiment (include hypothesis, baseline, metric, and a proposed pass/fail threshold)
6. Potential Cisco relevance (say "limited/unclear" if not supported)
7. Suggested artifact to build next

Do not invent external citations or claim that research was browsed. Keep it concise.
"""
    return client.responses.create(model=model, input=prompt).output_text.strip()

st.title("🛰️ Outshift Research Swarm")
st.caption("A topic-agnostic multi-agent R&D debate: agents challenge each other, revise positions, and produce a testable next step.")

with st.sidebar:
    st.header("Investigation setup")
    topic = st.text_area(
        "Research topic",
        value="How could AI agents make enterprise network troubleshooting faster and more reliable?",
        height=100,
        help="Choose any topic: a technology, product idea, scientific question, or business problem.",
    )
    goal = st.text_input("What do you want to decide?", value="Find a differentiated opportunity and define a prototype experiment.")
    rounds = st.slider("Debate rounds", min_value=1, max_value=4, value=2)
    model = st.text_input("Model", value=os.getenv("EVALREPORT_MODEL", "openai/gpt-4.1-mini"))
    api_key = st.text_input(
        "OpenRouter API key",
        value=os.getenv("OPENROUTER_API_KEY", ""),
        type="password",
        help="Alternatively set OPENROUTER_API_KEY in the root .env file. Your key is used only by this local app.",
    )
    demo_mode = st.toggle("Run in demo mode (no API calls)", value=not bool(api_key))
    context = st.text_area(
        "Optional background / constraints",
        placeholder="Paste project notes, customer context, technical constraints, or links you have already reviewed.",
        height=120,
    )
    run_button = st.button("▶ Run research debate", type="primary", use_container_width=True)
    st.divider()
    st.caption("Demo mode illustrates the workflow with scripted responses. Enable live mode and provide an API key for actual model-generated debate.")

if "transcript" not in st.session_state:
    st.session_state.transcript = []
if "summary" not in st.session_state:
    st.session_state.summary = ""
if "last_topic" not in st.session_state:
    st.session_state.last_topic = ""

if run_button:
    if not topic.strip():
        st.error("Enter a research topic first.")
        st.stop()
    if not demo_mode and not api_key.strip():
        st.error("Add an OpenRouter API key or turn on demo mode.")
        st.stop()

    st.session_state.transcript = []
    st.session_state.summary = ""
    st.session_state.last_topic = topic.strip()
    client = None if demo_mode else get_client(api_key.strip())

    status = st.status("Starting the research swarm…", expanded=True)
    transcript = st.session_state.transcript
    try:
        # Independent opening positions
        status.write("Round 0 · Gathering independent positions")
        for agent in AGENTS:
            task = "Give your independent initial assessment, key opportunity, biggest uncertainty, and one recommended next step. Do not assume the other agents agree."
            if demo_mode:
                answer = demo_reply(agent, [], task, topic)
            else:
                answer = ask_agent(client, model, agent, topic, goal, context, [], task)
            transcript.append({"round": 0, "agent": agent["name"], "emoji": agent["emoji"], "text": answer})
            st.session_state.transcript = transcript.copy()

        # Sequential debate: each agent sees the actual evolving transcript.
        for round_num in range(1, rounds + 1):
            status.write(f"Round {round_num} · Challenging claims and revising positions")
            for agent in AGENTS:
                task = (
                    f"This is debate round {round_num}. Respond directly to at least one specific earlier claim. "
                    "Identify the strongest counterargument to your own view, state what evidence would change your mind, "
                    "and either defend or revise your position. Suggest a concrete next experiment or decision."
                )
                if demo_mode:
                    answer = demo_reply(agent, transcript, task, topic)
                else:
                    answer = ask_agent(client, model, agent, topic, goal, context, transcript, task)
                transcript.append({"round": round_num, "agent": agent["name"], "emoji": agent["emoji"], "text": answer})
                st.session_state.transcript = transcript.copy()

        status.write("Building a synthesis and identifying unresolved disagreement")
        if demo_mode:
            st.session_state.summary = (
                "## Current recommendation\nUse the debate to narrow the topic to one testable hypothesis.\n\n"
                "## Points of agreement\nThe agents recommend defining a baseline, measurable outcome, and explicit assumptions.\n\n"
                "## Unresolved disagreements\nDemo mode does not validate consensus; all responses are illustrative.\n\n"
                "## Strongest assumptions / missing evidence\nNo external research was retrieved and no experiment was run.\n\n"
                "## Best next experiment\nState one hypothesis, compare against a baseline, record a metric, and set a pass/fail threshold before running the test.\n\n"
                "## Potential Cisco relevance\nDepends on the topic; do not force a Cisco connection.\n\n"
                "## Suggested artifact to build next\nA small reproducible prototype or benchmark with a README and recorded results."
            )
        else:
            st.session_state.summary = summarize(client, model, topic, goal, transcript, context)
        status.update(label="Debate complete", state="complete", expanded=False)
    except Exception as exc:
        status.update(label="The run encountered an error", state="error", expanded=True)
        st.error(f"{type(exc).__name__}: {exc}")
        st.info("Check that your API key is valid, your model name is available to your account, and your internet connection is working.")

left, right = st.columns([1.55, 1])
with left:
    st.subheader("Live debate transcript")
    if not st.session_state.transcript:
        st.info("Choose a topic and click **Run research debate**. Messages will appear in sequence.")
    else:
        for i, message in enumerate(st.session_state.transcript):
            with st.container(border=True):
                st.markdown(f"**{message['emoji']} {message['agent']}**  ·  Round {message['round']}")
                st.markdown(message["text"])

with right:
    st.subheader("Research synthesis")
    if st.session_state.summary:
        st.markdown(st.session_state.summary)
        st.download_button(
            "Download debate report (.md)",
            data=f"# Outshift Research Swarm Report\n\n**Topic:** {st.session_state.last_topic}\n\n{st.session_state.summary}\n\n## Full transcript\n\n" +
                 "\n\n".join(f"### Round {m['round']} — {m['agent']}\n\n{m['text']}" for m in st.session_state.transcript),
            file_name="outshift_research_report.md",
            mime="text/markdown",
        )
    else:
        st.write("The synthesis will appear here after the debate.")
    st.divider()
    st.subheader("Agents")
    for agent in AGENTS:
        st.markdown(f"{agent['emoji']} **{agent['name']}**")
        st.caption(agent["goal"])


# ---------------------------------------------------------------------------
# Interactive score dashboard
# These scores are entered by the user because the debate's free-text outputs
# do not currently produce validated numeric scores automatically.
# ---------------------------------------------------------------------------
st.divider()
st.header("📊 Evaluation Score Dashboard")
st.caption(
    "Enter scores from 0–100 based on your review of the debate. "
    "These are manual evaluation inputs, not automatically verified model scores."
)

with st.expander("Set Business, VC, and Technical scores", expanded=True):
    score_col1, score_col2, score_col3 = st.columns(3)
    with score_col1:
        business_score = st.slider("Business score (0–100)", 0, 100, 0, key="business_score")
    with score_col2:
        vc_score = st.slider("Venture Capital score (0–100)", 0, 100, 0, key="vc_score")
    with score_col3:
        technical_score = st.slider("Technical score (0–100)", 0, 100, 0, key="technical_score")

perspective_scores = {
    "Business": business_score,
    "Venture Capital": vc_score,
    "Technical": technical_score,
}
perspective_weights = {
    "Business": 0.30,
    "Venture Capital": 0.25,
    "Technical": 0.45,
}
weighted_score = sum(
    perspective_scores[name] * perspective_weights[name]
    for name in perspective_scores
)

metric_col1, metric_col2 = st.columns(2)
metric_col1.metric("Weighted overall score", f"{weighted_score:.1f}/100")
metric_col2.metric(
    "Highest-scoring perspective",
    max(perspective_scores, key=perspective_scores.get)
    if any(perspective_scores.values()) else "Not scored yet",
)

score_df = pd.DataFrame({
    "Perspective": list(perspective_scores.keys()),
    "Score": list(perspective_scores.values()),
})
score_bar = px.bar(
    score_df,
    x="Perspective",
    y="Score",
    color="Perspective",
    text="Score",
    range_y=[0, 100],
    title="Scores by Evaluation Perspective",
)
score_bar.update_traces(textposition="outside")
score_bar.update_layout(showlegend=False, xaxis_title="", yaxis_title="Score (0–100)")
st.plotly_chart(score_bar, use_container_width=True)

score_radar = px.line_polar(
    score_df,
    r="Score",
    theta="Perspective",
    line_close=True,
    range_r=[0, 100],
    title="Perspective Score Profile",
)
score_radar.update_traces(fill="toself")
st.plotly_chart(score_radar, use_container_width=True)

contribution_df = pd.DataFrame({
    "Perspective": list(perspective_scores.keys()),
    "Weighted points contributed": [
        perspective_scores[name] * perspective_weights[name]
        for name in perspective_scores
    ],
})
contribution_fig = px.bar(
    contribution_df,
    x="Perspective",
    y="Weighted points contributed",
    color="Perspective",
    text=contribution_df["Weighted points contributed"].map(lambda x: f"{x:.1f}"),
    title="Weighted Contribution to Overall Score",
)
contribution_fig.update_layout(
    showlegend=False, xaxis_title="", yaxis_title="Points toward total (0–100)"
)
st.plotly_chart(contribution_fig, use_container_width=True)

st.divider()
st.subheader("Compare Outshift against a baseline")
st.write(
    "Score both approaches on the same test ideas using the same rubric. "
    "Enter measured results below; zeros mean that results have not been entered."
)
comparison_criteria = [
    "Factual accuracy",
    "Risk identification",
    "Rubric coverage",
    "Experiment quality",
]
outshift_scores = {}
baseline_scores = {}

for criterion in comparison_criteria:
    left_score_col, right_score_col = st.columns(2)
    with left_score_col:
        outshift_scores[criterion] = st.slider(
            f"Outshift — {criterion}", 0, 100, 0,
            key=f"outshift_comparison_{criterion}",
        )
    with right_score_col:
        baseline_scores[criterion] = st.slider(
            f"Baseline — {criterion}", 0, 100, 0,
            key=f"baseline_comparison_{criterion}",
        )

comparison_df = pd.DataFrame({
    "Criterion": comparison_criteria * 2,
    "Approach": ["Outshift"] * len(comparison_criteria)
                + ["Baseline"] * len(comparison_criteria),
    "Score": [outshift_scores[c] for c in comparison_criteria]
             + [baseline_scores[c] for c in comparison_criteria],
})
comparison_fig = px.bar(
    comparison_df,
    x="Criterion",
    y="Score",
    color="Approach",
    barmode="group",
    range_y=[0, 100],
    title="Outshift vs. Baseline — Entered Benchmark Scores",
)
comparison_fig.update_layout(xaxis_title="", yaxis_title="Score (0–100)")
st.plotly_chart(comparison_fig, use_container_width=True)

outshift_average = sum(outshift_scores.values()) / len(comparison_criteria)
baseline_average = sum(baseline_scores.values()) / len(comparison_criteria)
avg_col1, avg_col2, avg_col3 = st.columns(3)
avg_col1.metric("Outshift average", f"{outshift_average:.1f}/100")
avg_col2.metric("Baseline average", f"{baseline_average:.1f}/100")
avg_col3.metric("Difference", f"{outshift_average - baseline_average:+.1f} points")

st.caption(
    "Do not treat a higher entered score as proof of superiority. "
    "Use a held-out set of ideas, the same rubric, and preferably blind scoring."
)

export_df = pd.DataFrame({
    "Section": ["Perspective scores"] * 3 + ["Outshift vs baseline"] * 8,
    "Item": list(perspective_scores.keys())
            + comparison_criteria + comparison_criteria,
    "Approach": ["Perspective"] * 3
                + ["Outshift"] * 4 + ["Baseline"] * 4,
    "Score": list(perspective_scores.values())
             + [outshift_scores[c] for c in comparison_criteria]
             + [baseline_scores[c] for c in comparison_criteria],
})
st.download_button(
    "Download graph scores as CSV",
    data=export_df.to_csv(index=False).encode("utf-8"),
    file_name="outshift_graph_scores.csv",
    mime="text/csv",
)
