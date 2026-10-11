from council.report import parse_evaluation, parse_summary
from orchestrator.analysis import _norm, verify

EVAL = """PART 1
**Feasibility score:** 6
Final verdict: Achievable with limitations
Confidence score: 85%

PART 2. Evaluation
**Verdict:** Hold. Narrow niche only.
| Metric | Score | Why |
|---|---|---|
| Feasibility (can it be built with what exists) | 7 | libs exist |
| Technical risk (10 = very risky) | 8 | latency |
Market demand: 3/10
"""


def test_parse_evaluation():
    p = parse_evaluation(EVAL)
    assert p["template_verdict"] == "Hold"
    assert p["template_scores"] == {"Feasibility": 7, "Technical risk": 8, "Market demand": 3}
    assert {"label": "Feasibility score", "value": 6, "max": 10} in p["role_scores"]
    assert {"label": "Confidence score", "value": 85, "max": 100} in p["role_scores"]
    assert p["role_verdict"]["label"] == "Final verdict" and p["complete"]
    assert parse_evaluation("Verdict: No go.", expect_template=True)["template_verdict"] == "No-go"
    assert parse_evaluation("Reaction: Mixed", expect_template=False)["complete"]
    assert not parse_evaluation("Reaction: Mixed", expect_template=True)["complete"]


def test_parse_summary_sections_and_lists():
    s = parse_summary("PROS\n- one\n  continued\n- two\n\nCONS\n1. bad\n\nWHERE THEY DISAGREED\nA vs B\n\nOPEN QUESTIONS\n- why?")
    assert s["pros"] == ["one continued", "two"] and s["cons"] == ["bad"]
    assert s["disagreements"] == "A vs B" and s["open_questions"] == ["why?"]


def test_verify_drops_invented_quotes_and_unknown_ids():
    said = {"a": _norm("We think the latency will be far too high for real users today."), "b": _norm("Cost is fine for us.")}
    group_of = {"a": "g1", "b": "g1"}
    obj = {"within_group": {"g1": [{"topic": "latency", "sides": [{"agent_ids": ["a"], "position": "too slow"}, {"agent_ids": ["b", "ghost"], "position": "fine"}],
                                    "status": "open", "evidence": [{"agent_id": "a", "quote": "the latency will be far too high"},
                                                                  {"agent_id": "b", "quote": "an invented sentence nobody ever said"}]}]},
           "cross_group": [], "agreements": []}
    clean, kept, dropped, _ = verify(obj, said, group_of)
    item = clean["within_group"]["g1"][0]
    assert kept == 1 and dropped == 1 and item["sides"][1]["agent_ids"] == ["b"] and item["evidence_verified"]


def test_report_includes_reality_check():
    from council.report import build
    events = [
        {"kind": "run_start", "t": "2026-01-01T00:00:00+00:00", "run": "r1", "idea": "x", "max_cost": 1, "mode": "quick",
         "groups": [{"id": "g", "name": "G", "consensus": "converge", "use_sources": False,
                     "agents": [{"id": "a", "name": "A", "model": "m", "prompt": None}]}]},
        {"kind": "reality_check", "t": "2026-01-01T00:00:01+00:00", "verdict": "nonsense", "confidence": 90,
         "category": "physically_impossible", "summary": "Breaks physics.", "blockers": ["energy"],
         "assumptions": [], "model": "m"},
        {"kind": "run_end", "t": "2026-01-01T00:00:02+00:00", "status": "done", "calls": 1, "spent": 0.01},
    ]
    r = build(events)
    assert r["reality_check"]["verdict"] == "nonsense" and r["reality_check"]["blockers"] == ["energy"]


def test_exported_reports_match_the_schema():
    import glob
    import json
    import jsonschema
    schema = json.load(open("schema/evaluation-report.schema.json"))
    files = [f for f in glob.glob("results/*.json") if not f.endswith("index.json")]
    for f in files:
        jsonschema.validate(json.load(open(f)), schema)
