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
AGENTS: List[Dict[str, Any]] = [
    {"id": "idea_generator", "name": "Idea Generator",
     "role": "Researches the idea and finalizes it — or replaces it with a better one.",
     "prompt": "ideation/prompts/idea_generator.md", "model": None},
    {"id": "builder", "name": "Builder",
     "role": "Scores how well the idea can be built as an MVP or artifact.",
     "prompt": "ideation/prompts/builder.md", "model": None},
    {"id": "analyzer", "name": "Analyzer",
     "role": "Researches the idea and judges whether it makes sense or is nonsense.",
     "prompt": "ideation/prompts/analyzer.md", "model": None},
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
    """The agent roster the frontend draws as a graph (with each agent's resolved model and thinking)."""
    return [{"id": a["id"], "name": a["name"], "role": a["role"],
             "model": model_for(a["id"], default_model, agent_models),
             "thinking": thinking_for(a["id"], default_thinking, agent_thinking)} for a in AGENTS]


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
    return delib_settings.resolve_key("", {})


def _effort(thinking: bool) -> str:
    """Thinking mode on -> a low reasoning effort; off -> none (the client retries if a model needs some)."""
    return "low" if thinking else "none"


def _run(coro):
    return asyncio.run(coro)


def _system(agent: Dict[str, Any]) -> str:
    base = prompt_lib.read(agent["prompt"])
    fmt = prompt_lib.read("ideation/prompts/message_format.md")
    return base.rstrip() + "\n\n" + fmt


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
              thinking: bool = True, budget: openrouter.RunBudget) -> Dict[str, Any]:
    """One agent turn. Returns the parsed message (with agent_id/name/model attached)."""
    if agent is None:
        raise ValueError("unknown agent")
    messages = [{"role": "system", "content": _system(agent)},
                {"role": "user", "content": user_prompt}]
    validate = VALIDATORS.get(agent["id"], validate_message)
    obj, res = _run(openrouter.chat_json(
        model, messages, _key(), validate=validate,
        max_tokens=2200, reasoning_effort=_effort(thinking), budget=budget))
    if not isinstance(obj, dict):
        raise openrouter.OpenRouterError(f"{agent['id']}: no JSON message returned")
    obj["agent_id"] = agent["id"]
    obj["agent_name"] = agent["name"]
    obj["model"] = model
    obj["cost"] = res.cost
    obj.setdefault("justification", [])
    obj.setdefault("sources", [])
    return obj


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
