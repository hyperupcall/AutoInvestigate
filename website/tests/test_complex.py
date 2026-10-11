"""The Evaluation Complex: three stewards vote continue/stop; enough stop votes stop the swarm, and the complex's
own report is logged once. Every model call is faked."""
import asyncio
import types

from orchestrator import complex as C

STEWARDS = [
    {"id": "usefulness", "name": "Usefulness Steward", "objective": "useful?", "model": "m",
     "prompt": "prompts/system/complex_usefulness.md", "reasoning_effort": "low"},
    {"id": "convergence", "name": "Convergence Steward", "objective": "new info?", "model": "m",
     "prompt": "prompts/system/complex_convergence.md", "reasoning_effort": "low"},
    {"id": "roi", "name": "ROI Steward", "objective": "worth it?", "model": "m",
     "prompt": "prompts/system/complex_roi.md", "reasoning_effort": "low"},
]
GROUPS = [{"id": "research", "name": "Research", "agents": [{"id": "a", "name": "A"}]}]


class FakeRun:
    def __init__(self, stop_votes=2):
        self.idea = "idea"
        self.s = {"complex": {"enabled": True, "max_seconds": 300, "interval_seconds": 5, "stop_votes": stop_votes,
                              "stewards": STEWARDS}, "groups": GROUPS}
        self.summaries = {"research": "the group thinks it is buildable"}
        self.latest_evals = {"research": {"a": "a concrete plan"}}
        self.transcripts = {"research": [{"agent": "a", "text": "we can build it"}]}
        self.budget = types.SimpleNamespace(spent=0.02, max_usd=1.0, calls=0)
        self.events = []
        self.complex_stop = asyncio.Event()
        self._stop_reason = None

    def log(self, kind, **f):
        self.events.append({"kind": kind, **f})

    def charge(self, res):
        pass

    def request_stop(self, by, detail=""):
        self._stop_reason = by
        self.log("complex_stop", by=by, reason=detail)
        self.complex_stop.set()


def fake_chat(decisions):
    """Return a chat_json stand-in that votes `decisions[i]` for the i-th steward (by call order)."""
    calls = {"n": 0}

    async def _f(model, messages, key, validate, **kw):
        d = decisions[calls["n"] % len(decisions)]
        calls["n"] += 1
        obj = {"decision": d, "confidence": 70, "reason": "because", "signals": ["x"], "if_continue": ""}
        assert validate(obj) is None
        return obj, types.SimpleNamespace(model=model, cost=0.001)
    return _f


def test_snapshot_includes_every_group(monkeypatch):
    run = FakeRun()
    text = C.swarm_snapshot(run, GROUPS)
    assert "Research" in text and "the group thinks it is buildable" in text


def test_enough_stop_votes_stop_the_swarm(monkeypatch):
    run = FakeRun(stop_votes=2)
    monkeypatch.setattr(C.orr, "chat_json", fake_chat(["stop", "stop", "continue"]))
    cx = C.Complex(run)
    asyncio.run(cx.assess(1, 12.0))
    assert run.complex_stop.is_set() and run._stop_reason == "votes"
    assert cx.history[-1]["decision"] == "stop" and cx.history[-1]["votes"] == {"stop": 2, "continue": 1}
    assert any(e["kind"] == "complex_verdict" for e in run.events)
    assert sum(1 for e in run.events if e["kind"] == "complex_assess") == 3


def test_short_votes_keep_going(monkeypatch):
    run = FakeRun(stop_votes=2)
    monkeypatch.setattr(C.orr, "chat_json", fake_chat(["stop", "continue", "continue"]))
    cx = C.Complex(run)
    asyncio.run(cx.assess(1, 12.0))
    assert not run.complex_stop.is_set()
    assert cx.history[-1]["decision"] == "continue"


def test_finalize_logs_once(monkeypatch):
    run = FakeRun()
    monkeypatch.setattr(C.orr, "chat_json", fake_chat(["continue", "continue", "continue"]))
    cx = C.Complex(run)
    asyncio.run(cx.assess(1, 5.0))
    cx.finalize()
    cx.finalize()
    assert sum(1 for e in run.events if e["kind"] == "complex_final") == 1
    rep = cx.report
    assert rep is not None and rep["rounds"] == 1 and len(rep["stewards"]) == 3
