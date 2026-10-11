"""Generic council agent executor.

Peers' replies are relayed to every group member as incoming messages, so an
agent that answered everything would chatter forever. This executor speaks only
when the moderator addresses it (JSON commands), and records everything peers
say. Outcomes are computed by each agent itself (agents/common/tally.py).
"""
import json
import logging
import os
import re
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Message, Part, Role, TextPart
from a2a.utils import new_task

from agents.common.config import SILENT
from agents.common.data import load_ideas, load_notes
from agents.common.llm import ask_json
from agents.common.schema import AGENT_NAMES, EXPERT_NAMES, CouncilMessage, Trade, parse_council_message
from agents.common.tally import BUDGET_HOURS, SLOTS, tally

logger = logging.getLogger("council.executor")


SYSTEM = """You are the "{name}" agent on a 4-agent research council deciding which \
emerging-technology research ideas Cisco Outshift builds first. Only {slots} ideas get \
a build slot, and together they must fit in {budget} engineer-hours.
Your goal: {goal}.
Your success is measured by how many of YOUR OWN priorities get a slot. The other \
three agents have different goals and private information; do not assume they agree \
with you. No one decides for the council: a set wins only if 3 of 4 agents back it. \
You are NOT trying to find consensus yourself; you are advocating for your own goal.
Your private notes (the others cannot see them):
{notes}"""

TURN_RULES = """Choose exactly ONE action this round:
- "propose": back a NEW set of exactly 3 ideas (replaces your current backing). idea_ids = the 3 ids.
- "accept": back a set of exactly 3 ideas that some agent currently backs (see "Current backing"). idea_ids = that exact set.
- "support": publicly argue for specific idea(s) without changing your backing. idea_ids = 1-3 ids. target = the agent you are backing (optional).
- "object": publicly argue against specific idea(s) with a concrete reason. idea_ids = 1-3 ids. target = the council agent whose pick you are challenging (REQUIRED, never yourself): name them and say why they are wrong.
- "offer_trade": signal a deal: you will drop idea `give` from your set if `want` is included. trade = {{"give": id, "want": id}}.
- "consult": ask an OUTSIDE expert agent a question; the expert is invited into the group and everyone sees the answer. expert = "security_expert" (feasibility of security, crypto and identity-standards ideas), "customer_voice" (what enterprise buyers actually want and pay for), or "specialist_on_demand" (any other expertise you need: set role to the kind of expert, e.g. "open-source licensing lawyer"; it is a generated persona answering from general knowledge, unverified). idea_ids = the ideas the question is about; reason = your question. Experts only advise, they never vote. {consult_note}
Rules of the game: a set wins only when 3 of 4 agents back that same set (within {budget}h). \
If no set wins after round {last_round}, the question escalates to a human with the disagreement on record; \
that is allowed, but every agent then gets none of its priorities decided.
Other agents cannot see your private notes. When a fact from your notes justifies a position, state it in your reason \
so the others can weigh it. Keep the reason to 1-2 sentences.
{early_note}
{late_note}
{consult_hint}
Reply JSON only: {{"action": "...", "idea_ids": [...], "reason": "...", "trade": null, "expert": null, "role": null, "target": null}}"""



class CouncilExecutor(AgentExecutor):
    def __init__(self, name: str, goal: str):
        self.name, self.goal = name, goal
        self.ideas = load_ideas()  # `planted` is stripped by load_ideas
        self.hours = {i["id"]: i["est_hours"] for i in self.ideas}
        self.system = SYSTEM.format(name=name, slots=SLOTS, budget=BUDGET_HOURS,
                                    goal=goal, notes=load_notes(name))
        self.seen: dict[tuple, CouncilMessage] = {}  # every agent message heard (deduped)
        self.info: list[tuple[int, str]] = []        # external new-information events

    def _record(self, m: CouncilMessage) -> None:
        if m.agent in AGENT_NAMES or m.agent in EXPERT_NAMES:
            self.seen[(m.agent, m.action, m.timestamp)] = m

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        text = context.get_user_input() or ""
        task = context.current_task or new_task(context.message)
        if not context.current_task:
            await event_queue.enqueue_event(task)
        reply = await self._decide(text)
        await event_queue.enqueue_event(Message(
            message_id=str(uuid4()), role=Role.agent, metadata={"name": self.name},
            parts=[Part(TextPart(text=reply))]))

    async def _decide(self, text: str) -> str:
        peer = parse_council_message(text)
        if peer is not None:  # broadcast from a peer: record it, stay quiet
            self._record(peer)
            return SILENT
        try:
            cmd = json.loads(text)
        except Exception:
            return SILENT
        kind, rnd = cmd.get("kind"), cmd.get("round", 0)
        if kind == "hello":
            return CouncilMessage(round=rnd, agent=self.name, action="hello",
                                  reason=f"{self.name} here. Goal: {self.goal}").to_json()
        if kind == "round0":
            self.seen.clear()  # round 0 starts a fresh negotiation
            self.info.clear()
            return (await self._propose(rnd)).to_json()
        if kind == "turn":
            if cmd.get("new_info"):
                self.info.append((rnd, cmd["new_info"]))
            return (await self._turn(rnd, cmd.get("last_round", 4))).to_json()
        if kind == "tally":
            return self._commit(rnd).to_json()
        return SILENT

    # ---- round 0 -----------------------------------------------------------
    async def _propose(self, rnd: int) -> CouncilMessage:
        ideas = json.dumps(self.ideas, indent=1)
        user = (f"Round {rnd}. Ideas:\n{ideas}\n\nPrivately rank the ideas by your goal, then "
                f"propose your top {SLOTS} whose est_hours sum to at most {BUDGET_HOURS}. "
                "Round 0 is your sincere opening position: choose the ideas that best serve YOUR "
                "goal and the priorities in your notes, even if you expect others to disagree. "
                "Bargaining and compromise happen in later rounds, not now. "
                'Reply JSON only: {"top3": ["idea_xx","idea_yy","idea_zz"], '
                '"reason": "1-2 sentences shown to the other agents"}')

        def validate(o: dict) -> str | None:
            return self._check_set(o.get("top3"))

        try:
            o = await ask_json(self.system, user, validate)
            msg = CouncilMessage(round=rnd, agent=self.name, action="propose",
                                 idea_ids=o["top3"], reason=str(o.get("reason", ""))[:400])
        except Exception as e:  # surface failures instead of hanging the round
            logger.error("propose failed: %s", e)
            msg = CouncilMessage(round=rnd, agent=self.name, action="propose",
                                 reason=f"ERROR: {e}"[:400])
        self._record(msg)  # own proposal counts in own tally
        return msg

    def _check_set(self, ids) -> str | None:
        if not isinstance(ids, list) or len(set(ids)) != SLOTS:
            return f"must be {SLOTS} distinct idea ids"
        if any(i not in self.hours for i in ids):
            return "unknown idea id"
        if sum(self.hours[i] for i in ids) > BUDGET_HOURS:
            return f"hours {sum(self.hours[i] for i in ids)} exceed budget {BUDGET_HOURS}"
        return None

    # ---- rounds 1..N -------------------------------------------------------
    def _transcript(self) -> str:
        lines = []
        for m in sorted(self.seen.values(), key=lambda m: (m.round, m.timestamp)):
            if m.action in ("commit", "hello") or not m.reason:
                continue
            extra = f" trade {m.trade.give}->{m.trade.want}" if m.trade else ""
            extra += f" to {m.expert}" if m.expert else ""
            who = f"EXPERT {m.agent}" if m.agent in EXPERT_NAMES else m.agent
            lines.append(f"r{m.round} {who} {m.action.upper()} {','.join(m.idea_ids)}{extra}: {m.reason}")
        return "\n".join(lines) or "(none)"

    async def _turn(self, rnd: int, last_round: int) -> CouncilMessage:
        res = tally(list(self.seen.values()), self.hours)
        backing = {a: next((m for m in sorted(self.seen.values(), key=lambda m: m.timestamp, reverse=True)
                            if m.agent == a and m.action in ("propose", "accept") and len(m.idea_ids) == SLOTS), None)
                   for a in AGENT_NAMES}
        backing_txt = "\n".join(f"  {a}: {','.join(m.idea_ids) if m else '(none)'}" for a, m in backing.items())
        consult_used = any(m.agent == self.name and m.action == "consult" for m in self.seen.values())
        late = rnd >= last_round - 1
        late_note = ("This is a LATE round. Unless you have a strong objection, move toward the set with the most "
                     "support that contains at least one of your priorities, using propose or accept, so the council can decide."
                     if late else "")
        early = rnd <= max(1, last_round - 2)
        early_note = ("This is an EARLY round: disagreement is expected and healthy. Defend your own priorities and "
                      "directly challenge the specific agent (target) whose pick you think is a mistake. Do not yet "
                      "accept a set that leaves out all of your priorities." if early else "")
        consult_hint = ("" if consult_used or rnd > 3 else
                        "You have not used your one consult. If an expert's factual answer (feasibility, buyer demand) could settle a dispute, consider asking now.")
        info_txt = "\n".join(f"  (before round {r}) {t}" for r, t in self.info) or "  (none)"
        user = (f"Round {rnd} of {last_round}.\nIdeas:\n{json.dumps(self.ideas)}\n\n"
                f"New information from outside the council:\n{info_txt}\n\n"
                f"Conversation so far:\n{self._transcript()}\n\n"
                f"Current backing (latest propose/accept per agent):\n{backing_txt}\n"
                f"Tally right now: {res.reason}\n\n"
                + TURN_RULES.format(budget=BUDGET_HOURS, last_round=last_round,
                                    consult_note="You already consulted once; do not consult again." if consult_used else "Use at most one consult in the whole negotiation, and only if an expert answer could change someone's mind.",
                                    late_note=late_note, early_note=early_note, consult_hint=consult_hint))
        backed_sets = {frozenset(m.idea_ids) for m in backing.values() if m}

        def validate(o: dict) -> str | None:
            a, ids = o.get("action"), o.get("idea_ids")
            if a in ("propose",):
                return self._check_set(ids)
            if a == "accept":
                err = self._check_set(ids)
                if err:
                    return err
                if frozenset(ids) not in backed_sets:
                    return "accept requires a set that some agent currently backs; use propose for a new set"
                return None
            if a in ("support", "object"):
                ok = isinstance(ids, list) and 1 <= len(ids) <= 3 and all(i in self.hours for i in ids)
                if not ok:
                    return "idea_ids must be 1-3 valid idea ids"
                if a == "object" and (o.get("target") not in AGENT_NAMES or o.get("target") == self.name):
                    return f"object needs target = another council agent in {[n for n in AGENT_NAMES if n != self.name]}"
                return None
            if a == "offer_trade":
                t = o.get("trade") or {}
                ok = t.get("give") in self.hours and t.get("want") in self.hours and t["give"] != t["want"]
                return None if ok else "trade needs distinct valid give and want idea ids"
            if a == "consult":
                if consult_used:
                    return "you already used your consult"
                ok = (o.get("expert") in EXPERT_NAMES and (o.get("expert") != "specialist_on_demand" or str(o.get("role") or "").strip()) and isinstance(ids, list) and 1 <= len(ids) <= 3
                      and all(i in self.hours for i in ids) and str(o.get("reason", "")).strip())
                return None if ok else f"consult needs expert in {list(EXPERT_NAMES)}, 1-3 idea_ids and a question in reason (specialist_on_demand also needs role)"
            return "action must be one of propose, accept, support, object, offer_trade, consult"

        try:
            o = await ask_json(self.system, user, validate)
            a = o["action"]
            trade = Trade(**o["trade"]) if a == "offer_trade" else None
            ids = [trade.give, trade.want] if trade else o["idea_ids"]
            msg = CouncilMessage(round=rnd, agent=self.name, action=a, idea_ids=ids,
                                 reason=str(o.get("reason", ""))[:400], trade=trade,
                                 expert=o.get("expert") if a == "consult" else None,
                                 role=str(o.get("role"))[:80] if a == "consult" and o.get("role") else None,
                                 target=o.get("target") if a in ("object", "support") and o.get("target") in AGENT_NAMES else None)
        except Exception as e:
            logger.error("turn failed: %s", e)
            msg = CouncilMessage(round=rnd, agent=self.name, action="object", idea_ids=[],
                                 reason=f"ERROR: {e}"[:400])
        self._record(msg)
        return msg

    def _commit(self, rnd: int) -> CouncilMessage:
        res = tally(list(self.seen.values()), self.hours)
        return CouncilMessage(round=rnd, agent=self.name, action="commit",
                              idea_ids=res.winner or [], reason=res.reason)

    async def cancel(self, request, event_queue):
        raise NotImplementedError
