"""Control flow of the pipeline with every model call faked: stop -> 2 rounds; go -> exactly one extra round,
then always the final step."""
import asyncio
import types

import pytest

from orchestrator import pipeline as P

GROUPS = [{"id": "research", "name": "Research", "consensus": "converge", "agents": [{"id": "a", "name": "A"}]},
          {"id": "market", "name": "Market", "consensus": "diverge", "agents": [{"id": "b", "name": "B"}]}]


class FakeRun:
    def __init__(self):
        self.s = {"groups": GROUPS, "deliberation_seconds": 1}
        self.calls, self.events = [], []
        self.idea = "idea"
        self.budget = types.SimpleNamespace(calls=0)
        self.transcripts = {}
        self.quick = False

    def log(self, kind, **f):
        self.events.append(kind)

    async def start(self):
        self.calls.append("start")

    async def deliberate(self, g, secs, prior, stage):
        self.calls.append(stage)
        return [{"agent": g["agents"][0]["id"], "text": "hi"}]

    async def evaluate(self, g, stage, kind, transcript, summaries="", prior_context=""):
        self.calls.append(f"{stage}:{kind}")
        return {g["agents"][0]["id"]: "eval"}


def fake_stage(decision, seen):
    async def reality_check(run):
        seen.append("reality_check")
        return {"verdict": "grounded", "summary": "coherent"}

    async def summarize(run, g, stage, t, e):
        seen.append(stage)
        return f"summary of {g['id']}"

    async def stop_or_go(run, groups, summaries):
        seen.append("stop_go")
        return {"decision": decision, "overall": {"rationale": "x"}, "if_go_resolve": "pricing"}

    async def conclude(run, groups, summaries, sg, log=True):
        seen.append(("final", sorted(summaries)))
        return {"overall": {"headline": "h"}, "groups": {}, "_model": "m", "_cost": 0}
    return reality_check, summarize, stop_or_go, conclude


@pytest.mark.parametrize("decision,rounds", [("stop", 2), ("go", 3)])
def test_rounds_and_always_finish(monkeypatch, decision, rounds):
    seen = []
    rc, s, sg, c = fake_stage(decision, seen)
    monkeypatch.setattr(P, "reality_check", rc)
    monkeypatch.setattr(P, "summarize", s)
    monkeypatch.setattr(P, "stop_or_go", sg)
    monkeypatch.setattr(P, "conclude", c)
    run = FakeRun()
    assert asyncio.run(P.pipeline(run)) == "done"
    assert seen.count("reality_check") == 1 and seen[0] == "reality_check"  # runs once, before any group
    delib = [c for c in run.calls if c.startswith("deliberation_")]
    assert len(delib) == rounds * len(GROUPS)
    assert "evaluation_1:evaluate" in run.calls and "evaluation_2:cross_review" in run.calls
    assert ("evaluation_3:cross_review" in run.calls) == (decision == "go")
    assert seen.count("stop_go") == 1                         # asked once, never again after the extra round
    assert seen[-1] == ("final", ["market", "research"])      # always finishes with every group's conclusion
    assert "run_end" in run.events and set(run.events[run.events.index("run_end") + 1:]) <= {"report", "note"}


def test_budget_stop_ends_cleanly(monkeypatch):
    run = FakeRun()

    async def broke(*a, **k):
        raise P.BudgetExceeded("cap")
    monkeypatch.setattr(run, "deliberate", broke)
    assert asyncio.run(P.pipeline(run)) == "budget_stopped"
    assert "run_end" in run.events and set(run.events[run.events.index("run_end") + 1:]) <= {"report", "note"}


def test_quick_mode_uses_the_early_verdict_when_stop(monkeypatch):
    seen = []
    rc, s, sg, c = fake_stage("stop", seen)
    monkeypatch.setattr(P, "reality_check", rc)
    monkeypatch.setattr(P, "summarize", s)
    monkeypatch.setattr(P, "stop_or_go", sg)
    monkeypatch.setattr(P, "conclude", c)
    run = FakeRun()
    run.quick = True
    assert asyncio.run(P.pipeline(run)) == "done"
    assert seen.count("stop_go") == 1 and seen.count(("final", ["market", "research"])) == 1
    ev = run.events
    assert ev.index("final") > ev.index("run_end") - 3 and "final" in ev   # verdict logged after the decision, before the end
