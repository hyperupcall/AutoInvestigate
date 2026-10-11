"""Default settings: three group perspectives, each an object with an `agents` array.
Models are restricted to the cheap set in ../CHEAP_MODELS.md (OpenRouter ids)."""
import copy
import glob
import os

from council.prompts import ROOT, role_name


def _agent(slug: str, prompt: str, model: str, effort: str | None = None) -> dict:
    return {"id": slug, "name": role_name(prompt), "prompt": prompt, "model": model,
            "api_key": "", "reasoning_effort": effort}  # None = use the stage default


def _groups() -> list[dict]:
    return [
        {"id": "research", "name": "Professional Research Group",
         "description": "Researchers judging feasibility, architecture, whether an LLM is needed, and prior art.",
         "consensus": "converge", "use_sources": True,
         "agents": [
             _agent("feasibility_scientist", "prompts/research/feasibility_scientist.md", "meta-llama/llama-3.1-8b-instruct"),
             _agent("systems_architect", "prompts/research/systems_architect.md", "openai/gpt-oss-120b"),
             _agent("ai_systems_researcher", "prompts/research/ai_systems_researcher.md", "google/gemma-3-4b-it"),
             _agent("critical_reviewer", "prompts/research/critical_reviewer.md", "meta-llama/llama-3.1-8b-instruct:online"),
         ]},
        {"id": "private_equity", "name": "Private Equity and Business",
         "description": "Four partners judging technical risk, market size, competitive position, and returns.",
         "consensus": "converge", "use_sources": True,
         "agents": [
             _agent("technical_risk_partner", "prompts/private_equity/technical_risk_partner.md", "openai/gpt-oss-120b"),
             _agent("market_revenue_partner", "prompts/private_equity/market_revenue_partner.md", "google/gemma-3-4b-it:online"),
             _agent("competitive_strategy_partner", "prompts/private_equity/competitive_strategy_partner.md", "meta-llama/llama-3.1-8b-instruct"),
             _agent("horizon_returns_partner", "prompts/private_equity/horizon_returns_partner.md", "openai/gpt-oss-120b"),
         ]},
        {"id": "market", "name": "Market Reaction",
         "description": "Customer archetypes reacting to the idea. They are not expected to agree.",
         "consensus": "diverge", "use_sources": False,
         "agents": [
             _agent("power_user", "prompts/market/power_user.md", "meta-llama/llama-3.1-8b-instruct"),
             _agent("enterprise_decision_maker", "prompts/market/enterprise_decision_maker.md", "google/gemma-3-4b-it"),
             _agent("skeptical_technical_critic", "prompts/market/skeptical_technical_critic.md", "openai/gpt-oss-120b"),
             _agent("startup_builder", "prompts/market/startup_builder.md", "meta-llama/llama-3.1-8b-instruct"),
             _agent("free_tier_maximizer", "prompts/market/free_tier_maximizer.md", "google/gemma-3-4b-it"),
         ]},
    ]


# Only these models may be used (see ../CHEAP_MODELS.md). OpenRouter ids.
LIBRARY_MODELS = ["meta-llama/llama-3.1-8b-instruct", "google/gemma-3-4b-it", "openai/gpt-oss-120b"]


def archetype_library() -> list[dict]:
    """Extra customer archetypes that can be added to the market group from /settings."""
    out = []
    for i, path in enumerate(sorted(glob.glob(os.path.join(ROOT, "prompts/market/archetypes/*.md")))):
        rel = os.path.relpath(path, ROOT)
        out.append(_agent(os.path.basename(path)[:-3], rel, LIBRARY_MODELS[i % len(LIBRARY_MODELS)]))
    return out


DEFAULT_SETTINGS = {
    "mode": "quick",                     # quick: about a minute (one pass per round, short write-ups) | deep: about 7 minutes
    "sources": {"enabled": True, "max_papers": 8, "model": "google/gemma-3-4b-it"},  # arXiv papers for groups with use_sources
    "openrouter_api_key": "",            # default key; blank per-agent keys fall back to this, then to $OPENROUTER_API_KEY
    "deliberation_seconds": 60,          # per deliberation round, per group
    "max_cost_usd": 1.0,                 # a run stops when this is spent
    "web_search_results": 3,             # per search for ":online" models
    "max_tokens": {"deliberate": 500, "evaluate": 4500, "summarize": 5000, "judge": 4000},
    "reasoning_effort": {"deliberate": "none", "evaluate": "low", "summarize": "none", "judge": "low"},
    "stages": {
        "summarizer": {"model": "openai/gpt-oss-120b", "api_key": ""},
        "judge": {"model": "openai/gpt-oss-120b", "api_key": ""},
    },
    "groups": _groups(),
}


def default_settings() -> dict:
    return copy.deepcopy(DEFAULT_SETTINGS)
