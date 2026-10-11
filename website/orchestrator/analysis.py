"""Disagreement analysis for the report: one summarizer-model call, then every quote is checked against what
the cited agent actually said. Unverifiable quotes are dropped and counted, so the report never shows an
invented quote."""
import re

from deliberation import openrouter as orr
from deliberation import prompts, settings


def _norm(s: str) -> str:
    s = s.replace("**", "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().strip('"\'.,;:').lower()


def record_text(events: list[dict]) -> tuple[str, dict[str, str], dict[str, str]]:
    """Readable record for the prompt, plus each agent's full text (for quote checks) and agent->group."""
    start = next(e for e in events if e["kind"] == "run_start")
    group_of = {a["id"]: g["id"] for g in start["groups"] for a in g["agents"]}
    said: dict[str, str] = {}
    lines = []
    for e in events:
        if e["kind"] == "stage_start" and e.get("group") and str(e["stage"]).startswith("deliberation"):
            lines.append(f"\n## {e['group']} {e['stage'].replace('_', ' ')}")
        if e["kind"] == "turn":
            lines.append(f"[{e['agent']}] {e['text']}")
            said[e["agent"]] = said.get(e["agent"], "") + " " + e["text"]
        if e["kind"] == "eval":
            said[e["agent"]] = said.get(e["agent"], "") + " " + e["text"]
            verdicts = [l.strip() for l in e["text"].splitlines() if re.search(r"verdict|recommendation|decision|reaction", l, re.I)][:2]
            if verdicts:
                lines.append(f"[{e['agent']}] ({e['stage'].replace('_', ' ')}) {' / '.join(verdicts)}")
        if e["kind"] == "summary":
            lines.append(f"SUMMARY {e['group']} {e['stage'].replace('_', ' ')}: {e['text'][:2500]}")
    return "\n".join(lines), {k: _norm(v) for k, v in said.items()}, group_of


def verify(obj: dict, said: dict[str, str], group_of: dict[str, str]) -> tuple[dict, int, int, int]:
    """Keep only valid ids and quotes that really appear in the cited agent's words."""
    kept_q = dropped_q = dropped_items = 0

    def clean_item(item: dict, cross: bool) -> dict | None:
        nonlocal kept_q, dropped_q
        sides = []
        for s in item.get("sides", []):
            ids = [i for i in s.get("agent_ids", []) if i in group_of]
            if cross and s.get("group_id") not in set(group_of.values()):
                continue
            if ids or cross:
                sides.append({**({"group_id": s["group_id"]} if cross else {}), "agent_ids": ids, "position": str(s.get("position", ""))})
        ev = []
        for q in item.get("evidence", []):
            a, quote = q.get("agent_id"), str(q.get("quote", ""))
            if a in said and len(_norm(quote)) >= 12 and _norm(quote) in said[a]:
                ev.append({"agent_id": a, "group_id": group_of[a], "quote": quote.strip()})
                kept_q += 1
            else:
                dropped_q += 1
        if len(sides) < 2:
            return None
        out = {"topic": str(item.get("topic", "")), "sides": sides, "status": item.get("status") if item.get("status") in ("resolved", "open") else "open",
               "evidence": ev, "evidence_verified": bool(ev)}
        if not cross:
            out["round"] = item.get("round") if isinstance(item.get("round"), int) else None
            out["resolution"] = str(item.get("resolution") or "") or None
        return out

    within = {}
    for gid in set(group_of.values()):
        items = []
        for it in (obj.get("within_group") or {}).get(gid, []):
            c = clean_item(it, cross=False)
            if c:
                items.append(c)
            else:
                dropped_items += 1
        within[gid] = items
    cross = []
    for it in obj.get("cross_group") or []:
        c = clean_item(it, cross=True)
        if c:
            cross.append(c)
        else:
            dropped_items += 1
    agreements = [{"topic": str(a.get("topic", "")), "group_ids": [g for g in a.get("group_ids", []) if g in set(group_of.values())],
                   "summary": str(a.get("summary", ""))} for a in obj.get("agreements") or []]
    return {"within_group": within, "cross_group": cross, "agreements": [a for a in agreements if len(a["group_ids"]) >= 2]}, kept_q, dropped_q, dropped_items


async def analyze(events: list[dict], s: dict, budget: orr.RunBudget | None = None) -> dict:
    start = next(e for e in events if e["kind"] == "run_start")
    text, said, group_of = record_text(events)
    roster = "\n".join(f"- {a['id']} ({a['name']}) in group {g['id']} ({g['name']})" for g in start["groups"] for a in g["agents"])
    gids = [g["id"] for g in start["groups"]]
    prompt = prompts.system("analysis", IDEA=start["idea"], ROSTER=roster, RECORD=text, GROUP_IDS=", ".join(gids))
    cfg = s["stages"]["summarizer"]

    def validate(o):
        if not isinstance(o.get("within_group"), dict) or not isinstance(o.get("cross_group"), list):
            return "need within_group (object) and cross_group (list)"
        return None
    obj, res = await orr.chat_json(cfg["model"], [{"role": "user", "content": prompt}], settings.resolve_key(cfg.get("api_key", ""), s),
                                   validate, max_tokens=6000, reasoning_effort=s["reasoning_effort"]["summarize"], budget=budget)
    clean, kept, dropped, dropped_items = verify(obj, said, group_of)
    return {**clean, "model": res.model, "verified_quotes": kept, "dropped_quotes": dropped, "dropped_items": dropped_items}
