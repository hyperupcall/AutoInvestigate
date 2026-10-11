"""One evaluation run: the settings snapshot, the cost budget, the event log, and per-group stages."""
import json
import os
import random
import time
from datetime import datetime, timezone
from uuid import uuid4

from council import settings
from council.openrouter import BudgetExceeded, RunBudget

MAX_TURNS_PER_GROUP = 40  # hard stop so a long time-box can never run away on cost
RUNS_DIR = "logs/runs"


def transcript_text(transcript: list[dict], names: dict) -> str:
    return "\n".join(f"{names.get(t['agent'], t['agent'])}: {t['text']}" for t in transcript)


class Run:
    def __init__(self, idea: str, s: dict | None = None, bus=None):
        self.id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:4]
        self.idea = idea.strip()
        self.s = s or settings.load()
        self.budget = RunBudget(self.s["max_cost_usd"])
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

    async def start(self) -> None:
        if self.bus.client is None:
            await self.bus.connect(self.s["groups"][0]["agents"][0]["id"])
        self.log("run_start", run=self.id, idea=self.idea, max_cost=self.budget.max_usd,
                 groups=[{"id": g["id"], "name": g["name"], "consensus": g["consensus"],
                          "agents": [{"id": a["id"], "name": a["name"], "model": a["model"], "prompt": a["prompt"]} for a in g["agents"]]}
                         for g in self.s["groups"]])

    def charge(self, reply: dict) -> None:
        if reply.get("cost"):
            self.budget.add(reply.get("model", "?"), float(reply["cost"]))

    def _agents_cfg(self, group: dict) -> dict:
        return {a["id"]: {"model": a["model"], "prompt": a["prompt"], "name": a["name"],
                          "reasoning_effort": a.get("reasoning_effort")} for a in group["agents"]}

    def _on_open(self, group: dict, purpose: str):
        return lambda channel, members: self.log("slim_group", group=group["id"], channel=channel,
                                                 members=members, purpose=purpose)

    async def deliberate(self, group: dict, seconds: float, prior_context: str = "", stage: str = "deliberation_1") -> list[dict]:
        """Round-robin discussion: agents speak one at a time in a shuffled order, each hearing everything said
        so far. Runs for `seconds`, but every agent speaks at least once."""
        agents = list(group["agents"])
        random.shuffle(agents)
        names = {a["id"]: a["name"] for a in agents}
        members = [a["id"] for a in agents]
        transcript: list[dict] = []
        t0, turn = time.monotonic(), 0
        self.log("stage_start", stage=stage, group=group["id"], seconds=seconds, order=members)
        while turn < MAX_TURNS_PER_GROUP:
            if turn >= len(agents) and time.monotonic() - t0 >= seconds:
                break
            self.budget.check()
            speaker = agents[turn % len(agents)]
            self.log("turn_start", stage=stage, group=group["id"], agent=speaker["id"])
            replies = await self.bus.ask(members, {
                "kind": "turn", "group_name": group["name"], "consensus": group["consensus"], "idea": self.idea,
                "colleagues": [names[m] for m in members if m != speaker["id"]], "agents": self._agents_cfg(group),
                "transcript": transcript_text(transcript, names), "prior_context": prior_context},
                expect=[speaker["id"]], timeout=min(max(seconds, 20), 45),  # a slow call is skipped, not waited on
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

    async def evaluate(self, group: dict, stage: str, kind: str, transcript: list[dict],
                       summaries: str = "", prior_context: str = "") -> dict[str, str]:
        """Every agent in the group writes its evaluation at the same time (one SLIM group, one command)."""
        self.budget.check()
        names = {a["id"]: a["name"] for a in group["agents"]}
        members = list(names)
        self.log("stage_start", stage=stage, group=group["id"], order=members)
        replies = await self.bus.ask(members, {
            "kind": kind, "group_name": group["name"], "idea": self.idea, "agents": self._agents_cfg(group),
            "transcript": transcript_text(transcript, names), "summaries": summaries, "prior_context": prior_context},
            expect=members, timeout=240, on_open=self._on_open(group, stage))
        missing = [a for a in members if a not in replies or replies[a].get("error")]
        if missing:  # ask the missing members once more, in a fresh SLIM group
            self.log("eval_retry", stage=stage, group=group["id"], agents=missing)
            replies.update(await self.bus.ask(members, {
                "kind": kind, "group_name": group["name"], "idea": self.idea, "agents": self._agents_cfg(group),
                "transcript": transcript_text(transcript, names), "summaries": summaries, "prior_context": prior_context},
                expect=missing, timeout=240, on_open=self._on_open(group, stage)))
        out = {}
        for a in members:
            r = replies.get(a)
            if not r or r.get("error"):
                self.log("eval_failed", stage=stage, group=group["id"], agent=a, error=(r or {}).get("error", "no reply in time"))
                continue
            self.charge(r)
            out[a] = r["text"]
            self.log("eval", stage=stage, group=group["id"], agent=a, name=names[a], model=r["model"],
                     text=r["text"], cost=r.get("cost", 0), truncated=bool(r.get("truncated")))
        self.log("stage_end", stage=stage, group=group["id"], evaluations=len(out))
        return out
