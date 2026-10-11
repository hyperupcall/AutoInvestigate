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


def test_complex_events_translate():
    ev = _ev()
    t = ev[0]["t"]
    ev.insert(2, {"kind": "complex_start", "t": t, "stewards": [
        {"id": "usefulness", "name": "Usefulness Steward", "model": "m", "objective": "useful?"}],
        "max_seconds": 300, "interval_seconds": 45, "stop_votes": 2})
    ev.insert(3, {"kind": "complex_assess", "t": t, "round": 1, "steward": "usefulness",
                  "name": "Usefulness Steward", "model": "m", "decision": "continue", "confidence": 60,
                  "reason": "still working", "signals": ["x"], "if_continue": "y", "cost": 0.001})
    ev.insert(4, {"kind": "complex_verdict", "t": t, "round": 1, "decision": "continue",
                  "votes": {"stop": 0, "continue": 1},
                  "stewards": {"usefulness": {"decision": "continue", "confidence": 60, "reason": "r"}},
                  "rationale": "0 of 1", "elapsed": 10, "spent": 0.01})
    ev.insert(5, {"kind": "complex_stop", "t": t, "by": "votes", "reason": "enough"})
    ev.insert(6, {"kind": "complex_final", "t": t, "enabled": True, "decision": "stop", "stopped_by": "votes",
                  "rounds": 1, "stop_votes": 2, "max_seconds": 300, "stewards": [], "history": []})
    ui = compat.ui_events(ev)
    kinds = [e["kind"] for e in ui]
    assert {"complex-cluster", "complex-turn", "complex-verdict", "complex-stop", "complex-final"} <= set(kinds)
    turn = next(e for e in ui if e["kind"] == "complex-turn")
    assert turn["agent_id"] == "usefulness" and turn["decision"] == "continue" and turn["confidence"] == 60
    assert next(e for e in ui if e["kind"] == "complex-final")["report"]["decision"] == "stop"
