"""Outside expert agents: invited into a group only when a council agent consults
them. They answer from their own knowledge notes and NEVER vote or back a set."""
import json
import logging
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Message, Part, Role, TextPart
from a2a.utils import new_task

from agents.common.config import SILENT
from agents.common.data import load_ideas, load_notes
from agents.common.llm import ask_json
from agents.common.schema import CouncilMessage, parse_council_message

logger = logging.getLogger("council.expert")

SYSTEM = """You are "{name}", an OUTSIDE expert advisor to a research council that picks which \
emerging-technology ideas Cisco Outshift builds first. You are not on the council: you do not vote, \
you do not care which ideas win, and you must not recommend a full set. Give honest, concrete, \
factual advice that answers the question, from your knowledge below. If your knowledge does not \
cover the question, say so briefly. At most 3 sentences.
Your knowledge:
{notes}"""


class ExpertExecutor(AgentExecutor):
    def __init__(self, name: str, role: str):
        self.name, self.role = name, role
        self.ideas = load_ideas()
        try:
            self.system = SYSTEM.format(name=name, notes=load_notes(name))
        except FileNotFoundError:  # specialist_on_demand has no fixed knowledge: its persona comes with each question
            self.system = None

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
        if parse_council_message(text) is not None:  # council chatter: ignore
            return SILENT
        try:
            cmd = json.loads(text)
        except Exception:
            return SILENT
        if cmd.get("kind") != "consult" or cmd.get("expert") != self.name:
            return SILENT
        ids = cmd.get("idea_ids", [])
        system = self.system or (
            f"You are a generated expert persona: {cmd.get('role') or 'general advisor'}. You were not pre-verified. You are advising a "
            "research council choosing which emerging-technology ideas Cisco Outshift builds. Answer from general knowledge, concisely "
            "and honestly, say when you are unsure, do not vote, do not recommend a full set. At most 3 sentences.")
        about = [i for i in self.ideas if i["id"] in ids]
        user = (f"{cmd.get('asker')} asks: {cmd.get('question')}\nAbout these ideas: {json.dumps(about)}\n"
                'Reply JSON only: {"advice": "<=3 sentences"}')
        try:
            o = await ask_json(system, user, lambda o: None if o.get("advice") else "advice is required")
            advice = str(o["advice"])[:500]
        except Exception as e:
            logger.error("advise failed: %s", e)
            advice = f"ERROR: {e}"[:300]
        return CouncilMessage(round=cmd.get("round", 0), agent=self.name, action="advise",
                              idea_ids=ids, reason=advice, expert=self.name).to_json()

    async def cancel(self, request, event_queue):
        raise NotImplementedError
