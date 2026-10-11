"""One evaluation run: the settings snapshot, the cost budget, the event log, and per-group stages."""
import asyncio
import json
import os
import random
import time
from datetime import datetime, timezone
from uuid import uuid4

from deliberation import settings
from deliberation.openrouter import RunBudget
from deliberation.prompts import resolve_consensus

MAX_TURNS_PER_GROUP = 40  # hard stop so a long time-box can never run away on cost
RUNS_DIR = "logs/runs"


def transcript_text(transcript: list[dict], names: dict) -> str:
    return "\n".join(f"{names.get(t['agent'], t['agent'])}: {t['text']}" for t in transcript)


class Run:
    def __init__(self, idea: str, s: dict | None = None, bus=None):
        self.id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:4]
        self.idea = idea.strip()
        self.s = s or settings.load()
        for g in self.s.get("groups", []):  # resolve 'auto' discussion styles once, so every stage sees a concrete style
            g["consensus"] = resolve_consensus(g)
        self.budget = RunBudget(self.s["max_cost_usd"])
        self.quick = self.s.get("mode", "quick") == "quick"
        self.reality_check: dict | None = None  # the outside check that runs before the groups (see pipeline)
        self.sources: dict = {}
        self.sources_text = ""
        self._sources_task = None
        self.transcripts: dict[str, list] = {}  # each group's latest discussion (shown to it in the next round)
        self.latest_evals: dict[str, dict[str, str]] = {}  # each group's latest evaluations (read by the final writer)
        self.summaries: dict[str, str] = {}  # each group's latest summary (read by the Evaluation Complex)
        # The Evaluation Complex (see orchestrator/complex.py): three stewards that watch the swarm in parallel
        # and can ask it to stop. complex_stop is set by the stewards' vote, the time limit, or the user.
        self.complex = None
        self.complex_task = None
        self.complex_stop = asyncio.Event()
        self._stop_reason: str | None = None
        if bus is None:
            from orchestrator.bus import Bus  # imported lazily so the pipeline logic is testable without SLIM
            bus = Bus()
        self.bus = bus
        os.makedirs(RUNS_DIR, exist_ok=True)
        self.path = f"{RUNS_DIR}/{self.id}.jsonl"

    def log(self, kind: str, **fields) -> dict:
        ev = {"t": datetime.now(timezone.utc).isoformat(), "kind": kind, "spent": round(self.budget.spent, 5), **fields}
        with open(self.path, "a") as f:
            f.write(json.dumps(ev) + "\n")
        return ev

    def request_stop(self, by: str, detail: str = "") -> None:
        """Ask the swarm to stop and go straight to the final verdict. Set by the stewards' vote, the time
        limit, or the user (see web.py /api/finalize). Idempotent; safe to call from the event loop thread."""
        if self.complex_stop.is_set():
            return
        self._stop_reason = by
        self.log("complex_stop", by=by, reason=detail or f"stopped by {by}")
        self.complex_stop.set()

    async def start(self) -> None:
        if self.bus.client is None:
            await self.bus.connect(self.s["groups"][0]["agents"][0]["id"])
        self.log("run_start", run=self.id, idea=self.idea, max_cost=self.budget.max_usd, mode="quick" if self.quick else "deep",
                 groups=[{"id": g["id"], "name": g["name"], "consensus": g["consensus"], "use_sources": bool(g.get("use_sources")),
                          "agents": [{"id": a["id"], "name": a["name"], "model": a["model"], "prompt": a["prompt"],
                                      "mcp_servers": a.get("mcp_servers", [])} for a in g["agents"]]}
                         for g in self.s["groups"]])

    async def ensure_sources(self, max_wait: float = 12) -> None:
        """Fetch the arXiv papers once per run. Groups that use them wait up to max_wait seconds, then go ahead
        without (the fetch keeps going, and later stages use the papers once they are in). Others never wait."""
        if self._sources_task is None:
            self._sources_task = asyncio.ensure_future(self._fetch_sources())
        try:
            await asyncio.wait_for(asyncio.shield(self._sources_task), max_wait)
        except (asyncio.TimeoutError, TimeoutError):
            pass

    async def _fetch_sources(self) -> None:
        from orchestrator.sources import as_prompt, find_safely
        self.log("stage_start", stage="sources")
        self.sources = await find_safely(self.idea, self.s, self.budget)
        self.sources_text = as_prompt(self.sources.get("papers", []))
        self.log("sources", **self.sources)

    def _src(self, group: dict) -> str:
        return self.sources_text if group.get("use_sources") else ""

    def charge(self, reply: dict) -> None:
        if reply.get("cost"):
            self.budget.add(reply.get("model", "?"), float(reply["cost"]))

    def _agents_cfg(self, group: dict) -> dict:
        return {a["id"]: {"model": a["model"], "prompt": a["prompt"], "name": a["name"],
                          "reasoning_effort": a.get("reasoning_effort"),
                          "mcp_servers": a.get("mcp_servers", [])} for a in group["agents"]}

    def _on_open(self, group: dict, purpose: str):
        return lambda channel, members: self.log("slim_group", group=group["id"], channel=channel,
                                                 members=members, purpose=purpose)

    async def deliberate(self, group: dict, seconds: float, prior_context: str = "", stage: str = "deliberation_1") -> list[dict]:
        """Round-robin discussion: agents speak one at a time in a shuffled order, each hearing everything said
        so far. Runs for `seconds`, but every agent speaks at least once."""
        if self.quick:
            return await self._deliberate_together(group, prior_context, stage)
        agents = list(group["agents"])
        random.shuffle(agents)
        names = {a["id"]: a["name"] for a in agents}
        members = [a["id"] for a in agents]
        transcript: list[dict] = []
        t0, turn = time.monotonic(), 0
        self.log("stage_start", stage=stage, group=group["id"], seconds=seconds, order=members)
        while turn < MAX_TURNS_PER_GROUP:
            if self.complex_stop.is_set():
                break  # the Evaluation Complex asked the swarm to stop: go to the final verdict
            if turn >= len(agents) and (self.quick or time.monotonic() - t0 >= seconds):
                break  # quick: one pass, every member speaks once; deep: keep going until the time is up
            self.budget.check()
            speaker = agents[turn % len(agents)]
            self.log("turn_start", stage=stage, group=group["id"], agent=speaker["id"])
            replies = await self.bus.ask(members, {
                "kind": "turn", "group_name": group["name"], "consensus": group["consensus"], "idea": self.idea,
                "colleagues": [names[m] for m in members if m != speaker["id"]], "agents": self._agents_cfg(group),
                "transcript": transcript_text(transcript, names), "prior_context": prior_context,
                "quick": self.quick, "sources": self._src(group)},
                expect=[speaker["id"]], timeout=20 if self.quick else min(max(seconds, 20), 45),  # slow calls are skipped
                on_open=self._on_open(group, stage))
            reply = replies.get(speaker["id"])
            if not reply or reply.get("error"):
                self.log("turn_failed", stage=stage, group=group["id"], agent=speaker["id"],
                         error=(reply or {}).get("error", "no reply in time"))
                turn += 1
                continue
            self.charge(reply)
            transcript.append({"agent": speaker["id"], "text": reply["text"]})
            self.log("turn", stage=stage, group=group["id"], agent=speaker["id"], name=speaker["name"],
                     model=reply["model"], text=reply["text"], cost=reply.get("cost", 0),
                     elapsed=round(time.monotonic() - t0, 1))
            turn += 1
        self.log("stage_end", stage=stage, group=group["id"], turns=len(transcript), elapsed=round(time.monotonic() - t0, 1))
        return transcript

    async def _deliberate_together(self, group: dict, prior_context: str, stage: str) -> list[dict]:
        """Quick mode: every member speaks at once (one SLIM group, one command) and each reply is logged the
        moment it arrives. In later rounds they answer each other, because the previous round is in the context."""
        self.budget.check()
        names = {a["id"]: a["name"] for a in group["agents"]}
        members = list(names)
        transcript: list[dict] = []
        t0 = time.monotonic()
        self.log("stage_start", stage=stage, group=group["id"], seconds=0, order=members)

        def on_reply(r):
            if r.get("error"):
                return
            self.charge(r)
            transcript.append({"agent": r["agent"], "text": r["text"]})
            self.log("turn", stage=stage, group=group["id"], agent=r["agent"], name=names[r["agent"]], model=r["model"],
                     text=r["text"], cost=r.get("cost", 0), elapsed=round(time.monotonic() - t0, 1))
        replies = await self.bus.ask(members, {
            "kind": "turn", "group_name": group["name"], "consensus": group["consensus"], "idea": self.idea,
            "colleagues": list(names.values()), "agents": self._agents_cfg(group), "transcript": "",
            "prior_context": prior_context, "quick": True, "sources": self._src(group)},
            expect=members, timeout=18, on_open=self._on_open(group, stage), on_reply=on_reply)
        for a in members:
            if a not in replies or replies[a].get("error"):
                self.log("turn_failed", stage=stage, group=group["id"], agent=a,
                         error=(replies.get(a) or {}).get("error", "no reply in time"))
        self.log("stage_end", stage=stage, group=group["id"], turns=len(transcript), elapsed=round(time.monotonic() - t0, 1))
        return transcript

    async def evaluate(self, group: dict, stage: str, kind: str, transcript: list[dict],
                       summaries: str = "", prior_context: str = "") -> dict[str, str]:
        """Every agent in the group writes its evaluation at the same time (one SLIM group, one command)."""
        self.budget.check()
        names = {a["id"]: a["name"] for a in group["agents"]}
        members = list(names)
        self.log("stage_start", stage=stage, group=group["id"], order=members)
        cmd = {"kind": kind, "group_name": group["name"], "idea": self.idea, "agents": self._agents_cfg(group),
               "transcript": transcript_text(transcript, names), "summaries": summaries, "prior_context": prior_context,
               "quick": self.quick, "sources": self._src(group)}
        out: dict[str, str] = {}

        def on_reply(r):  # log each evaluation the moment it arrives
            if r.get("error") or r["agent"] in out:
                return
            self.charge(r)
            out[r["agent"]] = r["text"]
            self.log("eval", stage=stage, group=group["id"], agent=r["agent"], name=names[r["agent"]], model=r["model"],
                     text=r["text"], cost=r.get("cost", 0), truncated=bool(r.get("truncated")))
        replies = await self.bus.ask(members, cmd, expect=members, timeout=20 if self.quick else 240,
                                     on_open=self._on_open(group, stage), on_reply=on_reply)
        missing = [a for a in members if a not in replies or replies[a].get("error")]
        if missing and not self.quick:  # deep mode: ask the missing members once more, in a fresh SLIM group
            self.log("eval_retry", stage=stage, group=group["id"], agents=missing)
            replies.update(await self.bus.ask(members, cmd, expect=missing, timeout=240, on_open=self._on_open(group, stage),
                                              on_reply=on_reply))
        for a in members:
            if a not in out:
                self.log("eval_failed", stage=stage, group=group["id"], agent=a,
                         error=(replies.get(a) or {}).get("error", "no reply in time"))
        self.log("stage_end", stage=stage, group=group["id"], evaluations=len(out))
        return out
