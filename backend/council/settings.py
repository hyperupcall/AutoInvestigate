"""Settings storage. Keys live in data/settings.json (gitignored, mode 600) and are masked in public views."""
import copy
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from council.defaults import MCP_CATALOG, MCP_CATEGORIES, archetype_library, default_settings
from council.prompts import ROOT

# The single root .env holds every key (see ../.env.example). docker compose injects it via
# env_file; loading it here too means a plain `python -m orchestrator.web` also sees it.
load_dotenv(Path(ROOT).parent / ".env")

MASK = "********"
EFFORTS = {None, "none", "minimal", "low", "medium", "high"}
MCP_KEY_ENV = "SMITH_API_KEY"  # the Smithery key for MCP servers lives in .env


def path() -> str:
    return os.getenv("SETTINGS_PATH", os.path.join(ROOT, "data", "settings.json"))


def load() -> dict:
    s = default_settings()
    defaults = {(g["id"], a["id"]): a.get("mcp_servers", []) for g in s["groups"] for a in g["agents"]}
    try:
        with open(path()) as f:
            stored = json.load(f)
    except FileNotFoundError:
        return s
    for k, v in stored.items():
        if k in ("max_tokens", "reasoning_effort", "stages", "sources") and isinstance(v, dict):
            for kk, vv in v.items():
                s[k][kk] = {**(s[k].get(kk) or {}), **vv} if isinstance(vv, dict) else vv
        else:
            s[k] = v
    # Backfill MCP servers for agents saved before the catalog existed.
    for g in s.get("groups", []):
        for a in g.get("agents", []):
            a.setdefault("mcp_servers", defaults.get((g["id"], a["id"]), []))
    return s


def validate(s: dict) -> list[str]:
    errs = []
    if s.get("mode") not in ("quick", "deep"):
        errs.append("mode must be quick or deep")
    src = s.get("sources") or {}
    if not isinstance(src.get("enabled"), bool) or not 1 <= int(src.get("max_papers") or 0) <= 15 or not str(src.get("model", "")).strip():
        errs.append("sources needs enabled (true/false), max_papers 1-15 and a model")
    if not 5 <= s.get("deliberation_seconds", 0) <= 900:
        errs.append("deliberation_seconds must be between 5 and 900")
    if not 0.05 <= s.get("max_cost_usd", 0) <= 50:
        errs.append("max_cost_usd must be between 0.05 and 50")
    if not 0 <= s.get("web_search_results", -1) <= 10:
        errs.append("web_search_results must be between 0 and 10")
    for stage in ("summarizer", "judge", "final", "reality_check"):
        if not str(s.get("stages", {}).get(stage, {}).get("model", "")).strip():
            errs.append(f"stages.{stage}.model is required")
    for k, v in s.get("reasoning_effort", {}).items():
        if v not in EFFORTS:
            errs.append(f"reasoning_effort.{k} must be one of none/minimal/low/medium/high")
    mcp = s.get("mcp") or {}
    if not isinstance(mcp.get("enabled"), bool):
        errs.append("mcp.enabled must be true/false")
    if not 1 <= int(mcp.get("timeout_seconds") or 0) <= 120:
        errs.append("mcp.timeout_seconds must be between 1 and 120")
    if not 0 <= int(mcp.get("max_tool_calls") or 0) <= 8:
        errs.append("mcp.max_tool_calls must be between 0 and 8")
    known_mcp = {m["id"] for m in MCP_CATALOG}
    ids = set()
    if not s.get("groups"):
        errs.append("at least one group is required")
    for g in s.get("groups", []):
        if g["id"] in ids:
            errs.append(f"duplicate group id {g['id']}")
        ids.add(g["id"])
        if g.get("consensus") not in ("converge", "diverge", "auto"):
            errs.append(f"group {g['id']}: consensus must be converge, diverge or auto")
        if not 1 <= len(g.get("agents", [])) <= 12:
            errs.append(f"group {g['id']}: needs 1 to 12 agents")
        aids = set()
        for a in g.get("agents", []):
            if a["id"] in aids:
                errs.append(f"group {g['id']}: duplicate agent id {a['id']}")
            aids.add(a["id"])
            if not str(a.get("model", "")).strip():
                errs.append(f"{g['id']}/{a['id']}: model is required")
            if a.get("reasoning_effort") not in EFFORTS:
                errs.append(f"{g['id']}/{a['id']}: invalid reasoning_effort")
            if not os.path.isfile(os.path.join(ROOT, a.get("prompt", ""))):
                errs.append(f"{g['id']}/{a['id']}: prompt file not found")
            for mid in a.get("mcp_servers", []):
                if mid not in known_mcp:
                    errs.append(f"{g['id']}/{a['id']}: unknown mcp server {mid}")
    return errs


def _keep_masked(new: dict, old: dict) -> None:
    """A masked key coming back from the settings page means 'unchanged'."""
    if new.get("api_key") == MASK:
        new["api_key"] = old.get("api_key", "")


def save(new: dict) -> list[str]:
    """Validate and store. Returns a list of errors (nothing is written if non-empty)."""
    old = load()
    new = copy.deepcopy(new)
    for derived in ("archetype_library", "mcp_catalog", "mcp_categories"):  # display-only, not stored
        new.pop(derived, None)
    (new.get("mcp") or {}).pop("api_key_env", None)  # display-only: whether .env supplies the key
    if new.get("openrouter_api_key") == MASK:
        new["openrouter_api_key"] = old.get("openrouter_api_key", "")
    if (new.get("mcp") or {}).get("api_key") == MASK:
        new.setdefault("mcp", {})["api_key"] = old.get("mcp", {}).get("api_key", "")
    for stage, cfg in new.get("stages", {}).items():
        _keep_masked(cfg, old.get("stages", {}).get(stage, {}))
    old_agents = {(g["id"], a["id"]): a for g in old["groups"] for a in g["agents"]}
    for g in new.get("groups", []):
        for a in g.get("agents", []):
            _keep_masked(a, old_agents.get((g["id"], a["id"]), {}))
            a["name"] = a.get("name") or a["id"]
    errs = validate(new)
    if errs:
        return errs
    os.makedirs(os.path.dirname(path()), exist_ok=True)
    tmp = path() + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(new, f, indent=1)
    os.replace(tmp, path())
    return []


def _mask(key: str) -> str:
    return MASK if key else ""


def public_view(s: dict) -> dict:
    """Settings safe to send to a browser: keys replaced by a mask, plus the archetype library."""
    v = copy.deepcopy(s)
    v["openrouter_api_key"] = _mask(v.get("openrouter_api_key") or os.getenv("OPENROUTER_API_KEY", ""))
    v.setdefault("mcp", {})["api_key"] = _mask(mcp_key(s))
    v["mcp"]["api_key_env"] = bool(os.getenv(MCP_KEY_ENV, "").strip())  # the key comes from .env
    for cfg in v["stages"].values():
        cfg["api_key"] = _mask(cfg.get("api_key", ""))
    for g in v["groups"]:
        for a in g["agents"]:
            a["api_key"] = _mask(a.get("api_key", ""))
    from council.report import _prompt_info  # role question for display (e.g. the AutoInvestigate frontend)
    for g in v["groups"]:
        for a in g["agents"]:
            a["question"] = _prompt_info(a).get("question")
    v["archetype_library"] = [{"id": a["id"], "name": a["name"], "prompt": a["prompt"], "model": a["model"]}
                              for a in archetype_library()]
    v["mcp_catalog"] = copy.deepcopy(MCP_CATALOG)
    v["mcp_categories"] = copy.deepcopy(MCP_CATEGORIES)
    return v


def resolve_key(own: str, s: dict) -> str:
    """Per-agent key, else the default key, else the environment."""
    return own or s.get("openrouter_api_key") or os.getenv("OPENROUTER_API_KEY", "")


def mcp_key(s: dict) -> str:
    """The Smithery key for MCP servers: the environment (.env) wins, then the stored setting."""
    return os.getenv(MCP_KEY_ENV, "").strip() or (s.get("mcp") or {}).get("api_key", "")
