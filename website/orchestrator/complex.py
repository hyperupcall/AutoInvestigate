"""The Evaluation Complex: three steward agents that watch the swarm in parallel and decide whether it should
continue or stop, then hand the swarm to its final verdict.

They share one goal (continue or stop) but optimize for different things, so they genuinely disagree:
  usefulness  — is there a useful, implementable result in what the collectives produced?
  convergence — would another round actually change anything (information gain)?
  roi         — is another round worth its cost in time and money?

The complex runs as a background task for the whole run. It re-assesses after each swarm round and on a timer,
logs its own events, and asks the run to stop when enough stewards vote stop, when the time limit is reached, or
when the user forces it. The pipeline watches run.complex_stop and goes straight to the final verdict."""
import asyncio
import time

from deliberation import openrouter as orr
from deliberation import prompts, settings


def _clip(text, n: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n].rstrip() + " ..."


def swarm_snapshot(run, groups: list[dict]) -> str:
    """What the collectives have produced so far, compact enough for a steward to read each assessment."""
    out = []
    for g in groups:
        out.append(f"=== {g['name']} ===")
        summ = (run.summaries or {}).get(g["id"])
        if summ:
            out.append("Summary: " + _clip(summ, 900))
        names = {a["id"]: a["name"] for a in g["agents"]}
        ev = (run.latest_evals or {}).get(g["id"]) or {}
        for aid, text in ev.items():
            out.append(f"--- {names.get(aid, aid)} ---\n{_clip(text, 700)}")
        turns = run.transcripts.get(g["id"]) or []
        if turns:
            out.append("Discussion: " + " | ".join(
                f"{names.get(t['agent'], t['agent'])}: {_clip(t['text'], 220)}" for t in turns[-6:]))
    return "\n\n".join(out) or "(the groups have not produced anything yet)"


def _validate(o: dict) -> str | None:
    if o.get("decision") not in ("continue", "stop"):
        return "decision must be 'continue' or 'stop'"
    if not isinstance(o.get("reason"), str) or not o["reason"].strip():
        return "reason is required"
    return None


class Complex:
    """One run's Evaluation Complex. Created by the pipeline; runs alongside the swarm."""

    def __init__(self, run):
        self.run = run
        self.cfg = run.s.get("complex") or {}
        self.stewards = [s for s in (self.cfg.get("stewards") or []) if s.get("id")]
        self.history: list[dict] = []   # one entry per assessment round
        self.last: dict[str, dict] = {}  # steward id -> its latest verdict (shown to the others next round)
        self.report: dict | None = None
        self.round_event = asyncio.Event()  # set by the pipeline after each swarm round

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled", True) and self.stewards)

    def note_round(self) -> None:
        """The pipeline finished a swarm round: assess again soon."""
        self.round_event.set()

    async def run_forever(self) -> None:
        if not self.enabled:
            return
        interval = max(5, int(self.cfg.get("interval_seconds", 45)))
        max_seconds = max(30, int(self.cfg.get("max_seconds", 300)))
        self.run.log("complex_start",
                     stewards=[{"id": s["id"], "name": s.get("name", s["id"]), "model": s.get("model"),
                                "objective": s.get("objective", "")} for s in self.stewards],
                     max_seconds=max_seconds, interval_seconds=interval,
                     stop_votes=int(self.cfg.get("stop_votes", 2)))
        t0 = time.monotonic()
        n = 0
        try:
            while not self.run.complex_stop.is_set():
                remaining = max_seconds - (time.monotonic() - t0)
                if remaining <= 0:
                    self.run.request_stop("time", f"the {max_seconds}s limit was reached")
                    break
                try:  # assess as soon as a swarm round lands, or every `interval` seconds, whichever is first
                    await asyncio.wait_for(self.round_event.wait(), timeout=min(interval, remaining))
                    self.round_event.clear()
                except (asyncio.TimeoutError, TimeoutError):
                    pass
                if self.run.complex_stop.is_set():
                    break
                n += 1
                await self.assess(n, round(time.monotonic() - t0, 1))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # the complex must never break the run
            self.run.log("note", text=f"Complex stopped: {type(e).__name__}: {e}"[:300])

    async def assess(self, n: int, elapsed: float) -> None:
        """One assessment round: every steward votes in parallel, then the votes are tallied."""
        groups = self.run.s["groups"]
        swarm = swarm_snapshot(self.run, groups)
        prior = self._prior_block()
        results = await asyncio.gather(*[self._ask(s, n, swarm, prior, elapsed) for s in self.stewards],
                                       return_exceptions=True)
        verdicts: dict[str, dict] = {}
        for s, r in zip(self.stewards, results):
            if isinstance(r, BaseException):
                self.run.log("note", text=f"Steward {s['id']} failed: {type(r).__name__}: {r}"[:200])
                continue
            verdicts[s["id"]] = r
        if not verdicts:
            return
        stop_votes = sum(1 for v in verdicts.values() if v["decision"] == "stop")
        need = max(1, int(self.cfg.get("stop_votes", 2)))
        decision = "stop" if stop_votes >= need else "continue"
        self.last = verdicts
        self.history.append({"round": n, "decision": decision,
                             "votes": {"stop": stop_votes, "continue": len(verdicts) - stop_votes},
                             "stewards": verdicts, "elapsed_seconds": elapsed})
        self.run.log("complex_verdict", round=n, decision=decision,
                     votes={"stop": stop_votes, "continue": len(verdicts) - stop_votes},
                     stewards={k: {"decision": v["decision"], "confidence": v.get("confidence"),
                                   "reason": v.get("reason", "")} for k, v in verdicts.items()},
                     rationale=self._rationale(verdicts, decision, stop_votes, need),
                     elapsed=elapsed, spent=round(self.run.budget.spent, 5))
        if decision == "stop":
            self.run.request_stop("votes", f"{stop_votes} of {len(verdicts)} stewards voted to stop")

    async def _ask(self, steward: dict, n: int, swarm: str, prior: str, elapsed: float) -> dict:
        prompt = prompts.render(prompts.read(steward["prompt"]), IDEA=self.run.idea, ROUNDS=str(n),
                                ELAPSED=str(int(elapsed)), SPENT=str(round(self.run.budget.spent, 4)),
                                MAX_COST=str(self.run.budget.max_usd), SWARM=swarm, PRIOR_VERDICTS=prior)
        key = settings.resolve_key(steward.get("api_key", ""), self.run.s)
        obj, res = await orr.chat_json(steward["model"], [{"role": "user", "content": prompt}], key, _validate,
                                       max_tokens=700, reasoning_effort=steward.get("reasoning_effort") or "low",
                                       budget=self.run.budget, web_results=0)
        self.run.charge(res)
        v = {"decision": obj["decision"], "confidence": obj.get("confidence"), "reason": obj["reason"],
             "signals": obj.get("signals", []), "if_continue": obj.get("if_continue", "")}
        self.run.log("complex_assess", round=n, steward=steward["id"], name=steward.get("name", steward["id"]),
                     model=res.model, decision=v["decision"], confidence=v["confidence"], reason=v["reason"],
                     signals=v["signals"], if_continue=v["if_continue"], cost=res.cost)
        return v

    def _prior_block(self) -> str:
        if not self.last:
            return "WHAT THE OTHER STEWARDS SAID LAST TIME:\n(this is the first assessment; the others have not voted yet)"
        lines = ["WHAT THE OTHER STEWARDS SAID LAST TIME:"]
        for s in self.stewards:
            v = self.last.get(s["id"])
            if not v:
                continue
            conf = f" ({v['confidence']}%)" if v.get("confidence") is not None else ""
            lines.append(f"- {s.get('name', s['id'])}: {v['decision']}{conf} — {_clip(v.get('reason', ''), 200)}")
        return "\n".join(lines)

    def _rationale(self, verdicts: dict, decision: str, stop_votes: int, need: int) -> str:
        names = {s["id"]: s.get("name", s["id"]) for s in self.stewards}
        stops = [names[i] for i, v in verdicts.items() if v["decision"] == "stop"]
        conts = [names[i] for i, v in verdicts.items() if v["decision"] == "continue"]
        if decision == "stop":
            head = f"{stop_votes} of {len(verdicts)} stewards voted to stop (needs {need}): {', '.join(stops)}."
        else:
            head = f"{stop_votes} of {len(verdicts)} stewards voted to stop (needs {need}): {', '.join(stops) or 'none'}."
        if conts:
            head += f" Still to continue: {', '.join(conts)}."
        return head

    def finalize(self) -> dict | None:
        """Log the complex's own report once, before the run ends. Idempotent."""
        if self.report is not None:
            return self.report
        if not self.enabled:
            return None
        latest = self.history[-1] if self.history else None
        self.report = {
            "enabled": True,
            "decision": latest["decision"] if latest else None,
            "stopped_by": getattr(self.run, "_stop_reason", None),
            "rounds": len(self.history),
            "stop_votes": int(self.cfg.get("stop_votes", 2)),
            "max_seconds": int(self.cfg.get("max_seconds", 300)),
            "stewards": [{"id": s["id"], "name": s.get("name", s["id"]), "objective": s.get("objective", ""),
                          "model": s.get("model"),
                          "decision": (self.last.get(s["id"]) or {}).get("decision"),
                          "confidence": (self.last.get(s["id"]) or {}).get("confidence"),
                          "reason": (self.last.get(s["id"]) or {}).get("reason"),
                          "signals": (self.last.get(s["id"]) or {}).get("signals", [])}
                         for s in self.stewards],
            "history": self.history,
        }
        self.run.log("complex_final", **self.report)
        return self.report
