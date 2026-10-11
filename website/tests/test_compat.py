import glob
import json

from orchestrator import compat


def _ev():
    return [json.loads(l) for l in open(sorted(glob.glob("tests/fixtures/*.jsonl"))[0])]


def test_ui_events_cover_every_kind_the_frontend_renders():
    ui = compat.ui_events(_ev())
    kinds = [e["kind"] for e in ui]
    assert {"phase", "cluster", "group-start", "round-start", "turn", "evaluation", "summary", "stop-go", "verdict", "cross-group"} <= set(kinds)
    assert kinds[:2] == ["phase", "cluster"]
    assert all("ts" in e and "phase" in e for e in ui)
    turn = next(e for e in ui if e["kind"] == "turn")
    assert {"group", "groupId", "round", "agent_id", "model", "text", "turn"} <= set(turn)
    ev = next(e for e in ui if e["kind"] == "evaluation" and e["round"] == 2)
    assert {"role_verdict", "role_scores", "template_verdict", "template_scores", "complete"} <= set(ev)
    sg = next(e for e in ui if e["kind"] == "stop-go")["stop_go"]
    assert sg["decision"] in ("stop", "go") and "consensus_feasible" in sg   # same shape as the report schema
    summ = next(e for e in ui if e["kind"] == "summary")["summary"]
    assert {"pros", "cons", "complete"} <= set(summ)


def test_reality_check_event_translates():
    ev = _ev()
    ev.insert(2, {"kind": "reality_check", "t": ev[0]["t"], "verdict": "nonsense", "confidence": 90,
                  "category": "physically_impossible", "summary": "Breaks physics.", "blockers": ["energy"],
                  "assumptions": [], "model": "m"})
    ui = compat.ui_events(ev)
    rc = next(e for e in ui if e["kind"] == "reality-check")["reality_check"]
    assert rc["verdict"] == "nonsense" and rc["blockers"] == ["energy"] and rc["category"] == "physically_impossible"


def test_current_phase():
    assert compat.current(_ev())["phase"]
