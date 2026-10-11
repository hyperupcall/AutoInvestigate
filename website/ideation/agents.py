"""The ideation collective — a small team of agents that work *together*.

They do not compete. Each one takes what the previous agents produced and refines
it, so the team converges on a single, sharp idea. Every message they exchange has
the same shape:

    context        LARGE text: the background, the reasoning, and the text of the
                   websites/signals that were read
    idea           the idea itself — ONE sentence only
    justification  3-4 bullet points on why it is a good idea
    sources        the links the message drew on

The team is three agents: the **Idea Generator** researches the idea and finalizes
it (or replaces it with a better one), the **Builder** scores how well it can be
built as an MVP or artifact, and the **Analyzer** researches it and judges whether
it makes sense or is nonsense. Any agent may also propose what belongs in the
long-term memory.
"""
import asyncio
from typing import Any, Dict, List, Optional

from deliberation import openrouter
from deliberation import prompts as prompt_lib
from deliberation import settings as delib_settings

# The team. `model: None` means "use the daemon's configured model".
# `mcp_servers` are ids from deliberation.defaults.MCP_CATALOG (the same catalog the
# evaluation agents use); `skills` are directories under website/skills/ whose SKILL.md
# is folded into the agent's system prompt. Both are shown in the Ideation View.
AGENTS: List[Dict[str, Any]] = [
    {"id": "idea_generator", "name": "Idea Generator",
     "role": "Researches the idea and finalizes it — or replaces it with a better one.",
     "prompt": "ideation/prompts/idea_generator.md", "model": None,
     "mcp_servers": ["arxiv", "semantic-scholar", "thoughtbox"],
     "skills": ["brainstorming"]},
    {"id": "builder", "name": "Builder",
     "role": "Scores how well the idea can be built as an MVP or artifact.",
     "prompt": "ideation/prompts/builder.md", "model": None,
     "mcp_servers": ["arxiv", "crossref", "math-logic"],
     "skills": ["launch-strategy"]},
    {"id": "analyzer", "name": "Analyzer",
     "role": "Researches the idea and judges whether it makes sense or is nonsense.",
     "prompt": "ideation/prompts/analyzer.md", "model": None,
     "mcp_servers": ["citation-checker", "crossref", "logic-verifier", "invinoveritas"],
     "skills": []},
]

# The order the team speaks in each round: generate, then score, then analyze.
TEAM_ORDER = ["idea_generator", "builder", "analyzer"]


def agent_by_id(agent_id: str) -> Optional[Dict[str, Any]]:
    return next((a for a in AGENTS if a["id"] == agent_id), None)


def model_for(agent_id: str, default_model: str,
              agent_models: Optional[Dict[str, str]] = None) -> str:
    """The model an agent uses: its configured override, else its own default, else the daemon default."""
    agent = agent_by_id(agent_id) or {}
    return (agent_models or {}).get(agent_id) or agent.get("model") or default_model


def thinking_for(agent_id: str, default_thinking: bool = True,
                 agent_thinking: Optional[Dict[str, bool]] = None) -> bool:
    """Whether an agent runs with thinking (reasoning) on: its override, else the default."""
    overrides = agent_thinking or {}
    return bool(overrides[agent_id]) if agent_id in overrides else bool(default_thinking)


def public_agents(default_model: str, agent_models: Optional[Dict[str, str]] = None,
                  default_thinking: bool = True,
                  agent_thinking: Optional[Dict[str, bool]] = None) -> List[Dict[str, Any]]:
    """The agent roster the frontend draws as a graph (with each agent's resolved model,
    thinking, starting prompt, skills and MCP servers)."""
    return [{"id": a["id"], "name": a["name"], "role": a["role"],
             "model": model_for(a["id"], default_model, agent_models),
             "thinking": thinking_for(a["id"], default_thinking, agent_thinking),
             "prompt": a["prompt"], "prompt_text": system_prompt(a),
             "mcp_servers": list(a.get("mcp_servers") or []),
             "skills": skill_info(a)} for a in AGENTS]


# --------------------------------------------------------------- validation
def validate_message(obj: Any) -> Optional[str]:
    if not isinstance(obj, dict):
        return "reply must be a JSON object"
    if not str(obj.get("context", "")).strip():
        return "context is required (the large background text)"
    idea = str(obj.get("idea", "")).strip()
    if not idea:
        return "idea is required"
    if len(idea) > 400:
        return "idea must be ONE sentence (keep it under 400 characters)"
    just = obj.get("justification")
    if not isinstance(just, list) or not 3 <= len(just) <= 4:
        return "justification must be a list of 3 or 4 bullet points"
    return None


def validate_builder(obj: Any) -> Optional[str]:
    err = validate_message(obj)
    if err:
        return err
    build = obj.get("build")
    if not isinstance(build, dict):
        return "build must be an object"
    for key in ("mvp", "artifact"):
        if not isinstance(build.get(key), (int, float)):
            return f"build.{key} must be a number (1-10)"
    return None


def validate_analyzer(obj: Any) -> Optional[str]:
    err = validate_message(obj)
    if err:
        return err
    analysis = obj.get("analysis")
    if not isinstance(analysis, dict):
        return "analysis must be an object"
    if analysis.get("verdict") not in ("makes_sense", "questionable", "nonsense"):
        return "analysis.verdict must be makes_sense, questionable or nonsense"
    return None


VALIDATORS = {
    "idea_generator": validate_message,
    "builder": validate_builder,
    "analyzer": validate_analyzer,
}


# ------------------------------------------------------------------ helpers
def _key() -> str:
    return delib_settings.resolve_key()


def _effort(thinking: bool) -> str:
    """Thinking mode on -> a low reasoning effort; off -> none (the client retries if a model needs some)."""
    return "low" if thinking else "none"


def _run(coro):
    return asyncio.run(coro)


def _skill_path(skill_id: str) -> str:
    return f"skills/{skill_id}/SKILL.md"


def skill_info(agent: Dict[str, Any]) -> List[Dict[str, str]]:
    """The skills an agent can use, as {id, name, description} read from each SKILL.md."""
    out = []
    for sid in agent.get("skills") or []:
        try:
            text = prompt_lib.read(_skill_path(sid))
        except OSError:
            continue
        name, description = _skill_frontmatter(text, sid)
        out.append({"id": sid, "name": name, "description": description})
    return out


def _skill_frontmatter(text: str, fallback: str) -> tuple:
    """The `name` and `description` from a SKILL.md's YAML frontmatter (best effort)."""
    name, description = fallback.replace("-", " ").title(), ""
    if not text.startswith("---"):
        return name, description
    block = text.split("---", 2)[1] if text.count("---") >= 2 else ""
    for line in block.splitlines():
        key, _, value = line.partition(":")
        value = value.strip().strip('"').strip("'")
        if key.strip() == "name" and value:
            name = value
        elif key.strip() == "description" and value:
            description = value
    return name, description


def _skills_text(agent: Dict[str, Any]) -> str:
    """The full text of each skill an agent can use, folded into its system prompt."""
    blocks = []
    for sid in agent.get("skills") or []:
        try:
            blocks.append(prompt_lib.read(_skill_path(sid)).strip())
        except OSError:
            continue
    if not blocks:
        return ""
    return "## Skills you can use\n\n" + "\n\n---\n\n".join(blocks)


def system_prompt(agent: Dict[str, Any]) -> str:
    """The full starting prompt an agent is given: its role prompt, the message format,
    and the text of any skills it can use."""
    parts = [prompt_lib.read(agent["prompt"]).rstrip(),
             prompt_lib.read("ideation/prompts/message_format.md").rstrip()]
    skills = _skills_text(agent)
    if skills:
        parts.append(skills)
    return "\n\n".join(parts)


def _system(agent: Dict[str, Any]) -> str:
    return system_prompt(agent)


def format_signals(signals: List[Dict[str, Any]]) -> str:
    """The raw material: each signal with its full text, so the agents can read it."""
    if not signals:
        return "(no signals were found this cycle)"
    blocks = []
    for i, s in enumerate(signals, 1):
        blocks.append(
            f"[{i}] {s.get('title', '')}\n"
            f"    source: {s.get('source', '')}  url: {s.get('url', '')}\n"
            f"    text: {s.get('text', '') or '(no body)'}"
        )
    return "\n\n".join(blocks)


def format_transcript(messages: List[Dict[str, Any]]) -> str:
    """What the team has said so far, so the next agent can build on it."""
    if not messages:
        return "(nothing said yet)"
    blocks = []
    for m in messages:
        just = "\n".join(f"  - {b}" for b in m.get("justification", []))
        blocks.append(f"### {m.get('agent_name', m.get('agent_id', '?'))}\n"
                      f"IDEA: {m.get('idea', '')}\n"
                      f"WHY:\n{just}\n"
                      f"CONTEXT: {m.get('context', '')}")
    return "\n\n".join(blocks)


def run_agent(agent: Optional[Dict[str, Any]], user_prompt: str, *, model: str,
              thinking: bool = True, budget: openrouter.RunBudget,
              mcp: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One agent turn. Returns the parsed message (with agent_id/name/model attached).

    When the agent has MCP servers and MCP is enabled, the model may call their tools
    (fail-safe: any error falls back to a plain call)."""
    if agent is None:
        raise ValueError("unknown agent")
    messages = [{"role": "system", "content": _system(agent)},
                {"role": "user", "content": user_prompt}]
    validate = VALIDATORS.get(agent["id"], validate_message)
    obj, res = _run(_chat_json(agent, messages, model, thinking, budget, validate, mcp or {}))
    if not isinstance(obj, dict):
        raise openrouter.OpenRouterError(f"{agent['id']}: no JSON message returned")
    obj["agent_id"] = agent["id"]
    obj["agent_name"] = agent["name"]
    obj["model"] = model
    obj["cost"] = res.cost
    obj.setdefault("justification", [])
    obj.setdefault("sources", [])
    return obj


async def _chat_json(agent: Dict[str, Any], messages: List[Dict[str, Any]], model: str,
                     thinking: bool, budget: openrouter.RunBudget, validate, mcp: Dict[str, Any]):
    """A JSON reply, using the agent's MCP tools when it has any and they are enabled."""
    kw: Dict[str, Any] = {"max_tokens": 2200, "reasoning_effort": _effort(thinking), "budget": budget}
    ids = agent.get("mcp_servers") or []
    if ids and mcp.get("enabled", True):
        got = await _chat_json_with_tools(agent, messages, model, ids, validate, mcp, kw)
        if got is not None:
            return got
    return await openrouter.chat_json(model, messages, _key(), validate=validate, **kw)


async def _chat_json_with_tools(agent: Dict[str, Any], messages: List[Dict[str, Any]], model: str,
                                ids: List[str], validate, mcp: Dict[str, Any], kw: Dict[str, Any]):
    """Try the agent's MCP servers; return (obj, result) on a valid JSON reply, else None."""
    from deliberation.defaults import MCP_CATALOG
    from deliberation.mcp import MCPToolbox
    catalog = {m["id"]: m for m in MCP_CATALOG}
    servers = [catalog[i] for i in ids if i in catalog]
    if not servers:
        return None
    try:
        async with MCPToolbox(servers, delib_settings.mcp_key({}), mcp.get("timeout_seconds", 20)) as box:
            if not box.tools:
                return None
            res = await openrouter.chat_with_tools(
                model, messages, _key(), box.tools, box.call,
                max_tool_calls=int(mcp.get("max_tool_calls", 2)), **kw)
            obj = openrouter.extract_json(res.text)
            if obj is not None and validate(obj) is None:
                return obj, res
    except Exception:  # never let MCP break a session
        return None
    return None


def parse_sources(signals: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    return [{"title": s.get("title", ""), "url": s.get("url", "")} for s in signals if s.get("url")]


# ------------------------------------------------------- one-shot generation
def validate_generation(obj: Any) -> Optional[str]:
    if not isinstance(obj, dict):
        return "reply must be a JSON object"
    ideas = obj.get("ideas")
    if not isinstance(ideas, list) or not ideas:
        return "ideas must be a non-empty list"
    for idea in ideas:
        if not isinstance(idea, dict) or not str(idea.get("text", "")).strip():
            return "each idea needs a 'text'"
        just = idea.get("justification")
        if not isinstance(just, list) or not 3 <= len(just) <= 4:
            return "each idea needs 3 or 4 justification bullets"
    return None


def generate_ideas(source_ideas: List[Dict[str, Any]], iteration_type: str, variation_count: int,
                   freeform_prompt: str, seed_text: str, *, model: str, thinking: bool = True,
                   budget: openrouter.RunBudget) -> Dict[str, Any]:
    """The Part 1 contract (mock-backend.generateIdeas): seed/iterate ideas in one call."""
    sources = "\n".join(f"- {s.get('text', '')}" for s in source_ideas) or f"- {seed_text or '(none)'}"
    user = (
        f"ITERATION TYPE: {iteration_type}\n"
        f"HOW MANY IDEAS: {variation_count}\n"
        + (f"INSTRUCTION: {freeform_prompt}\n" if freeform_prompt else "")
        + f"\nSOURCE IDEAS:\n{sources}\n\n"
        "Produce the ideas now."
    )
    system = prompt_lib.read("ideation/prompts/generate.md")
    obj, res = _run(openrouter.chat_json(
        model, [{"role": "system", "content": system}, {"role": "user", "content": user}],
        _key(), validate=validate_generation, max_tokens=2000,
        reasoning_effort=_effort(thinking), budget=budget))
    if not isinstance(obj, dict):
        raise openrouter.OpenRouterError("generator returned no JSON object")
    return {
        "subject": obj.get("subject", ""),
        "ideas": obj.get("ideas", []),
        "model": model,
        "cost": res.cost,
    }


# ---------------------------------------------------- related-idea generation
def generate_related_ideas(topics: List[Dict[str, Any]], *, model: str, thinking: bool = True,
                           budget: openrouter.RunBudget) -> Dict[str, Any]:
    """Ask a model (by default Gemini 3.8 Flash) for ideas vaguely related to the watchlist topics.

    Unlike `generate_ideas` (which sharpens a seed or a set of source ideas), this reads
    the topics themselves and sketches nearby directions — including simple, business-focused
    ones a normal person could use."""
    system = prompt_lib.read("ideation/prompts/related_ideas.md")
    listing = "\n".join(
        f"- {t.get('name', '')}: {t.get('description', '')}" for t in topics
    ) or "(no topics yet)"
    user = f"TOPICS:\n{listing}\n\nProduce the ideas now."
    obj, res = _run(openrouter.chat_json(
        model, [{"role": "system", "content": system}, {"role": "user", "content": user}],
        _key(), validate=validate_generation, max_tokens=2000,
        reasoning_effort=_effort(thinking), budget=budget))
    if not isinstance(obj, dict):
        raise openrouter.OpenRouterError("related-idea generator returned no JSON object")
    return {
        "subject": obj.get("subject", ""),
        "ideas": obj.get("ideas", []),
        "model": model,
        "cost": res.cost,
    }


# ------------------------------------------------------------ topic drafting
def validate_topic(obj: Any) -> Optional[str]:
    if not isinstance(obj, dict):
        return "reply must be a JSON object"
    if not str(obj.get("name", "")).strip():
        return "name is required"
    if not str(obj.get("description", "")).strip():
        return "description is required"
    if not isinstance(obj.get("tags"), list):
        return "tags must be a list"
    return None


def draft_topic(description: str, *, model: str, thinking: bool = True,
                budget: openrouter.RunBudget) -> Dict[str, Any]:
    """Turn a short description into a watchlist topic: a name, a summary, tags and keywords."""
    system = prompt_lib.read("ideation/prompts/topic.md")
    user = f"TOPIC IDEA: {description}\n\nDraft the topic now."
    obj, res = _run(openrouter.chat_json(
        model, [{"role": "system", "content": system}, {"role": "user", "content": user}],
        _key(), validate=validate_topic, max_tokens=900,
        reasoning_effort=_effort(thinking), budget=budget))
    if not isinstance(obj, dict):
        raise openrouter.OpenRouterError("topic drafter returned no JSON object")
    return {
        "name": str(obj.get("name", "")).strip(),
        "description": str(obj.get("description", "")).strip(),
        "tags": [str(t).strip() for t in obj.get("tags", []) if str(t).strip()][:6],
        "keywords": [str(k).strip() for k in obj.get("keywords", []) if str(k).strip()][:8],
        "model": model,
        "cost": res.cost,
    }


# ------------------------------------------------------------- topic finder
def format_material(recent: List[Dict[str, Any]], trending: List[Dict[str, Any]],
                    text_limit: int = 400) -> str:
    """What the topic finder reads: the signals the team has already seen, plus a broad
    'what is happening right now' fetch. Each signal's text is trimmed so the prompt stays small."""
    def block(title: str, signals: List[Dict[str, Any]]) -> str:
        if not signals:
            return ""
        lines = []
        for i, s in enumerate(signals, 1):
            text = (s.get("text") or "").strip()
            if len(text) > text_limit:
                text = text[:text_limit].rstrip() + "…"
            lines.append(f"[{i}] {s.get('title', '')}  ({s.get('source', '')})\n    {text}")
        return f"{title}\n" + "\n".join(lines)

    parts = [block("RECENT SIGNALS THE TEAM HAS ALREADY SEEN:", recent),
             block("WHAT IS TRENDING ON THE INTERNET RIGHT NOW:", trending)]
    return "\n\n".join(p for p in parts if p) or "(no material was available)"


def validate_topics(obj: Any) -> Optional[str]:
    if not isinstance(obj, dict):
        return "reply must be a JSON object"
    topics = obj.get("topics")
    if not isinstance(topics, list) or not topics:
        return "topics must be a non-empty list"
    for t in topics:
        if not isinstance(t, dict) or not str(t.get("name", "")).strip():
            return "each topic needs a name"
        if not str(t.get("description", "")).strip():
            return "each topic needs a description"
        if not isinstance(t.get("keywords"), list):
            return "each topic needs a keywords list"
    return None


def find_topics(material: str, existing: List[Dict[str, Any]], *, model: str,
                thinking: bool = True, budget: openrouter.RunBudget) -> Dict[str, Any]:
    """The topic finder: read the internet material and propose new watchlist topics.

    Topics combine one or two things and do not need to be small (see the prompt)."""
    system = prompt_lib.read("ideation/prompts/topic_finder.md")
    names = "\n".join(f"- {t.get('name', '')}: {t.get('description', '')}" for t in existing) or "(none yet)"
    user = (f"EXISTING TOPICS (do not repeat these):\n{names}\n\n"
            f"WHAT IS HAPPENING ON THE INTERNET RIGHT NOW:\n{material}\n\n"
            "Propose the topics now.")
    obj, res = _run(openrouter.chat_json(
        model, [{"role": "system", "content": system}, {"role": "user", "content": user}],
        _key(), validate=validate_topics, max_tokens=2200,
        reasoning_effort=_effort(thinking), budget=budget))
    if not isinstance(obj, dict):
        raise openrouter.OpenRouterError("topic finder returned no JSON object")
    return {"topics": obj.get("topics", []), "model": model, "cost": res.cost}
