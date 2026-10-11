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
    async def summarize(run, g, stage, t, e):
        seen.append(stage)
        return f"summary of {g['id']}"

    async def stop_or_go(run, groups, summaries):
        seen.append("stop_go")
        return {"decision": decision, "overall": {"rationale": "x"}, "if_go_resolve": "pricing"}

    async def conclude(run, groups, summaries, sg):
        seen.append(("final", sorted(summaries)))
        return {}
    return summarize, stop_or_go, conclude


@pytest.mark.parametrize("decision,rounds", [("stop", 2), ("go", 3)])
def test_rounds_and_always_finish(monkeypatch, decision, rounds):
    seen = []
    s, sg, c = fake_stage(decision, seen)
    monkeypatch.setattr(P, "summarize", s)
    monkeypatch.setattr(P, "stop_or_go", sg)
    monkeypatch.setattr(P, "conclude", c)
    run = FakeRun()
    assert asyncio.run(P.pipeline(run)) == "done"
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
