"""One evaluator agent as a SLIM/A2A endpoint. Stateless: every command carries what it needs, and the
agent's model, key and role come from the shared settings file at command time (so settings changes apply
to the next command without restarting anything)."""
import json
import logging
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Message, Part, Role, TextPart
from a2a.utils import new_task

from council import openrouter as orr
from council import prompts, settings
from council.defaults import archetype_library
from council.openrouter import trim_to_sentence
from council.slim import SILENT

logger = logging.getLogger("council.agent")
KINDS = {"turn": "deliberation", "evaluate": "evaluation", "cross_review": "cross_review"}


def find_agent(agent_id: str, s: dict) -> dict | None:
    for g in s["groups"]:
        for a in g["agents"]:
            if a["id"] == agent_id:
                return a
    return next((a for a in archetype_library() if a["id"] == agent_id), None)


class AgentWorker(AgentExecutor):
    def __init__(self, agent_id: str):
        self.id = agent_id

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        text = context.get_user_input() or ""
        task = context.current_task or new_task(context.message)
        if not context.current_task:
            await event_queue.enqueue_event(task)
        reply = await self._decide(text)
        await event_queue.enqueue_event(Message(
            message_id=str(uuid4()), role=Role.agent, metadata={"name": self.id},
            parts=[Part(TextPart(text=reply))]))

    async def _decide(self, text: str) -> str:
        try:
            cmd = json.loads(text)
        except Exception:
            return SILENT
        # Replies from other agents are relayed to every member; commands for other agents are not ours.
        to = cmd.get("to") if isinstance(cmd, dict) else None
        if self.id not in (to if isinstance(to, list) else [to]) or cmd.get("kind") not in KINDS:
            return SILENT
        try:
            out = await self._run(cmd)
            return json.dumps({"kind": "reply", "cmd": cmd["cmd"], "agent": self.id, **out})
        except Exception as e:  # always answer, so the orchestrator never waits on a dead agent
            logger.error("%s failed: %s", self.id, e)
            return json.dumps({"kind": "reply", "cmd": cmd["cmd"], "agent": self.id, "error": str(e)[:300]})

    async def _run(self, cmd: dict) -> dict:
        s = settings.load()
        agent = find_agent(self.id, s)
        if agent is None:
            raise RuntimeError(f"agent {self.id} is not in the settings")
        # The orchestrator sends the run's snapshot of this agent (model, prompt, effort); the key stays local.
        agent = {**agent, **(cmd.get("agents", {}).get(self.id) or {})}
        stage = {"turn": "deliberate", "evaluate": "evaluate", "cross_review": "evaluate"}[cmd["kind"]]
        quick = bool(cmd.get("quick"))
        values = dict(AGENT_NAME=agent["name"], GROUP_NAME=cmd["group_name"], ROLE_DOC=prompts.read(agent["prompt"]),
                      IDEA=cmd["idea"], PRIOR_CONTEXT=cmd.get("prior_context", ""),
                      TRANSCRIPT=cmd.get("transcript") or "(nobody has spoken yet)", SOURCES=cmd.get("sources", ""))
        if cmd["kind"] == "turn":
            values.update(COLLEAGUES=", ".join(c for c in cmd["colleagues"] if c != agent["name"]) or "no one else",
                          CONSENSUS_INSTRUCTION=prompts.consensus_instruction(cmd["consensus"]))
        elif cmd["kind"] == "cross_review":
            values.update(SUMMARIES=cmd["summaries"],
                          EVALUATION_TEMPLATE=prompts.read("prompts/system/evaluation_template.md"))
        template = KINDS[cmd["kind"]] + ("_quick" if quick and cmd["kind"] != "turn" else "")
        prompt = prompts.system(template, **values)
        # Web search only when evaluating in deep mode (quick mode relies on the arXiv list: faster, cheaper).
        model = agent["model"].removesuffix(":online") if (cmd["kind"] == "turn" or quick) else agent["model"]
        QUICK_TOKENS = {"deliberate": 350, "evaluate": 800}
        kw = dict(
            max_tokens=QUICK_TOKENS[stage] if quick else s["max_tokens"][stage],
            reasoning_effort="none" if quick else (agent.get("reasoning_effort") or s["reasoning_effort"][stage]),
            web_results=s["web_search_results"], on_length="trim" if cmd["kind"] == "turn" else "retry")
        res = await self._answer(agent, s, cmd, model, [{"role": "user", "content": prompt}],
                                 settings.resolve_key(agent["api_key"], s), kw)
        text = trim_to_sentence(res.text) if res.finish_reason == "length" else res.text
        return {"text": text, "cost": res.cost, "model": model, "truncated": res.finish_reason == "length"}

    async def _answer(self, agent: dict, s: dict, cmd: dict, model: str, messages: list[dict], key: str, kw: dict):
        """Plain model call, or a tool-using call when the agent has MCP servers and this is a deep-mode
        evaluation stage. MCP is fail-safe: any error (server down, bad reply) falls back to the plain call."""
        mcp_cfg = s.get("mcp") or {}
        ids = agent.get("mcp_servers") or []
        use_mcp = (ids and mcp_cfg.get("enabled", True) and not cmd.get("quick")
                   and cmd["kind"] in ("evaluate", "cross_review"))
        if not use_mcp:
            return await orr.chat(model, messages, key, **kw)
        from council.defaults import MCP_CATALOG
        from council.mcp import MCPToolbox
        catalog = {m["id"]: m for m in MCP_CATALOG}
        servers = [catalog[i] for i in ids if i in catalog]
        if not servers:
            return await orr.chat(model, messages, key, **kw)
        try:
            async with MCPToolbox(servers, mcp_cfg.get("api_key") or "", mcp_cfg.get("timeout_seconds", 20)) as box:
                if not box.tools:
                    return await orr.chat(model, messages, key, **kw)
                logger.info("%s: %d MCP tools from %d servers", self.id, len(box.tools), len(box.servers))
                return await orr.chat_with_tools(model, messages, key, box.tools, box.call,
                                                 max_tool_calls=int(mcp_cfg.get("max_tool_calls", 2)), **kw)
        except Exception as e:  # never let MCP break an evaluation
            logger.warning("%s: MCP unavailable (%s); answering without tools", self.id, e)
            return await orr.chat(model, messages, key, **kw)

    async def cancel(self, request, event_queue):
        raise NotImplementedError
