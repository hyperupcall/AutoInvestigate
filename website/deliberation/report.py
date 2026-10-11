"""Turn a run's event log into the evaluation report (schema/evaluation-report.schema.json).

Everything here is deterministic: it only reshapes and parses what the agents wrote. The one model-made part,
the disagreement analysis, is read from the run's "analysis" event (see orchestrator/analysis.py)."""
import os
import re
import statistics
from datetime import datetime

from deliberation.defaults import archetype_library
from deliberation.prompts import ROOT

SCHEMA_VERSION = "1.0"
TEMPLATE_METRICS = ["Feasibility", "Technical risk", "Market demand", "Differentiation",
                    "Time to first value", "Cost to build and run", "Adoption likelihood"]
TEMPLATE_VERDICTS = ["Go with changes", "Go", "Hold", "No-go"]
ROLE_VERDICT_LABELS = ["Final verdict", "Verdict", "Recommendation", "Decision", "Reaction",
                       "Overall technical risk", "Recommended approach"]
SUMMARY_SECTIONS = {"PROS": "pros", "CONS": "cons", "WHERE THEY DISAGREED": "disagreements",
                    "SCORES AND VERDICTS": "scores_and_verdicts", "OPEN QUESTIONS": "open_questions"}


def _clean(line: str) -> str:
    return re.sub(r"^[\s>*#\-•]+", "", line.replace("**", "").replace("__", "")).strip()


def _metric(label: str) -> str | None:
    l = re.sub(r"\(.*?\)", "", label).strip().lower()
    for m in TEMPLATE_METRICS:
        if l.startswith(m.lower()):
            return m
    return None


def _num(s: str) -> float | None:
    m = re.match(r"\s*(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    v = float(m.group(1))
    return int(v) if v.is_integer() else v


def parse_evaluation(text: str, expect_template: bool = True) -> dict:
    """Verdicts and scores an agent wrote. Part 1 is the role's own format, part 2 the evaluation template."""
    split = re.split(r"(?im)^[\s*#]*PART 2\b.*$", text, maxsplit=1)
    part1, part2 = split[0], (split[1] if len(split) > 1 else "")
    template_scores, role_scores = {}, []
    role_verdict, template_verdict = None, None
    for raw in text.splitlines():
        if raw.strip().startswith("|"):
            cells = [c.strip() for c in raw.strip().strip("|").split("|")]
            if len(cells) >= 2 and (m := _metric(cells[0].replace("**", ""))) and (v := _num(cells[1])) is not None and v <= 10:
                template_scores.setdefault(m, v)
    for raw in (part2 or text).splitlines():
        line = _clean(raw)
        if (m := re.match(r"(.{3,60}?)\s*[:\-–]\s*(\d+(?:\.\d+)?)\s*(?:/\s*10)?\s*$", line)) and (k := _metric(m.group(1))):
            template_scores.setdefault(k, _num(m.group(2)))
        if template_verdict is None and (m := re.match(r"verdict\s*[:\-–]\s*(go with changes|go|hold|no[\s-]?go)\b", line, re.I)):
            v = m.group(1).lower().replace(" ", "-") if "no" in m.group(1).lower() else m.group(1).lower()
            template_verdict = {"go with changes": "Go with changes", "go": "Go", "hold": "Hold"}.get(v, "No-go")
    for raw in part1.splitlines():
        line = _clean(raw)
        m = re.match(r"([A-Za-z][A-Za-z ,/\-]{2,60}?(?:score|confidence|likelihood[A-Za-z ]*))\s*[:\-–]\s*(\d+(?:\.\d+)?)\s*(%|/\s*10|out of 10)?", line, re.I)
        if m:
            v = _num(m.group(2))
            mx = 100 if (m.group(3) == "%" or v > 10) else 10
            role_scores.append({"label": m.group(1).strip(), "value": v, "max": mx})
        if role_verdict is None:
            for label in ROLE_VERDICT_LABELS:
                if (m := re.match(rf"{label}\s*[:\-–]\s*(.+)", line, re.I)):
                    role_verdict = {"label": label, "value": m.group(1).strip()[:200]}
                    break
    return {"role_verdict": role_verdict, "role_scores": role_scores, "template_verdict": template_verdict,
            "template_scores": template_scores,
            "complete": (bool(part2.strip()) or bool(template_scores)) if expect_template else True}


def _items(lines: list[str]) -> list[str]:
    out = []
    for raw in lines:
        if not raw.strip():
            continue
        if re.match(r"^\s*([-*•]|\d+[.)])\s+", raw) or not out:
            out.append(_clean(re.sub(r"^\s*\d+[.)]\s+", "", raw)))
        else:
            out[-1] += " " + raw.strip()
    return [o for o in out if o]


def parse_summary(text: str) -> dict:
    sec, cur = {}, None
    for raw in text.splitlines():
        head = re.sub(r"[*#:]", "", raw).strip().upper()
        if head in SUMMARY_SECTIONS:
            cur = SUMMARY_SECTIONS[head]
            sec[cur] = []
            continue
        if cur:
            sec[cur].append(raw)
    return {"text": text, "pros": _items(sec.get("pros", [])), "cons": _items(sec.get("cons", [])),
            "disagreements": "\n".join(sec.get("disagreements", [])).strip(),
            "scores_and_verdicts": "\n".join(sec.get("scores_and_verdicts", [])).strip(),
            "open_questions": _items(sec.get("open_questions", []))}


def _summary_complete(ev: dict) -> bool:
    t = ev["text"].rstrip()
    sections = sum(1 for s in SUMMARY_SECTIONS if re.search(rf"(?m)^[*#\s]*{s}[*:\s]*$", t))
    return not ev.get("truncated") and sections == len(SUMMARY_SECTIONS) and t.endswith((".", "?", "!", ")", '"'))


def _prompt_info(agent: dict) -> dict:
    path = agent.get("prompt")
    if not path:
        from deliberation import settings
        s = settings.load()
        found = next((a for g in s["groups"] for a in g["agents"] if a["id"] == agent["id"]), None) or \
            next((a for a in archetype_library() if a["id"] == agent["id"]), None)
        path = found["prompt"] if found else None
    if not path or not os.path.isfile(os.path.join(ROOT, path)):
        return {"question": None, "who_they_are": None}
    text = open(os.path.join(ROOT, path)).read()
    q = re.search(r"\*\*Question this agent answers:\*\*\s*(.+)", text)
    w = re.search(r"## Who they are\s*\n(.+?)(?:\n\n|\n##)", text, re.S)
    return {"question": q.group(1).strip() if q else None, "who_they_are": w.group(1).strip() if w else None}


def _round(stage: str) -> int | None:
    m = re.search(r"_(\d+)$", stage or "")
    return int(m.group(1)) if m else None


FINAL_OVERALL_FIELDS = ("headline", "recommendation", "summary", "the_idea", "case_for", "case_against",
                        "plan", "kill_criteria", "risks", "open_questions", "what_would_change_the_verdict", "scores")


def _final_overall(fin: dict) -> dict:
    """The final report's overall block, keeping only the fields the writer actually returned."""
    o = fin.get("overall") or {}
    return {k: o[k] for k in FINAL_OVERALL_FIELDS if o.get(k) is not None}


def build(events: list[dict]) -> dict:
    start = next(e for e in events if e["kind"] == "run_start")
    end = next((e for e in reversed(events) if e["kind"] == "run_end"), None)
    sg = next((e for e in events if e["kind"] == "stop_go"), None)
    rc = next((e for e in events if e["kind"] == "reality_check"), None)
    fin = next((e for e in events if e["kind"] == "final"), None)
    analysis = next((e for e in reversed(events) if e["kind"] == "analysis"), None)
    groups_meta = start.get("groups") or []
    rounds_seen = sorted({_round(e["stage"]) for e in events if str(e.get("stage", "")).startswith("deliberation")} - {None})
    groups = []
    for g in groups_meta:
        gid = g["id"]
        agents = [{"id": a["id"], "name": a["name"], "model": a["model"], **_prompt_info(a)} for a in g["agents"]]
        rounds = []
        for n in rounds_seen:
            turns = [e for e in events if e["kind"] == "turn" and e["group"] == gid and _round(e["stage"]) == n]
            missed = [e for e in events if e["kind"] == "turn_failed" and e["group"] == gid and _round(e["stage"]) == n]
            evals = [e for e in events if e["kind"] == "eval" and e["group"] == gid and _round(e["stage"]) == n]
            failed = [e for e in events if e["kind"] == "eval_failed" and e["group"] == gid and _round(e["stage"]) == n]
            summ = next((e for e in events if e["kind"] == "summary" and e["group"] == gid and _round(e["stage"]) == n), None)
            parsed = []
            for e in evals:
                p = parse_evaluation(e["text"], expect_template=n > 1)
                if e.get("truncated"):
                    p["complete"] = False
                parsed.append({"agent_id": e["agent"], "model": e["model"], "text": e["text"], **p})
            rounds.append({
                "round": n, "label": "Extra round" if n == 3 else f"Round {n}",
                "shared_summaries_before": n > 1,
                "discussion": [{"turn": i + 1, "agent_id": e["agent"], "model": e["model"], "text": e["text"],
                                "at": e["t"], "elapsed_seconds": e.get("elapsed")} for i, e in enumerate(turns)],
                "missed_turns": [{"agent_id": e["agent"], "reason": e.get("error", "")} for e in missed],
                "evaluations": parsed,
                "failed_evaluations": [{"agent_id": e["agent"], "reason": e.get("error", "")} for e in failed],
                "summary": {**parse_summary(summ["text"]), "complete": _summary_complete(summ)} if summ else None})
        latest = next((r for r in reversed(rounds) if r["evaluations"]), None)
        scores, verdicts = {}, {}
        if latest:
            for m in TEMPLATE_METRICS:
                vals = [ev["template_scores"][m] for ev in latest["evaluations"] if m in ev["template_scores"]]
                if vals:
                    med = statistics.median(vals)
                    scores[m] = {"median": int(med) if float(med).is_integer() else med, "min": min(vals), "max": max(vals), "n": len(vals)}
            for ev in latest["evaluations"]:
                if ev["template_verdict"]:
                    verdicts[ev["template_verdict"]] = verdicts.get(ev["template_verdict"], 0) + 1
            for a in agents:
                ev = next((x for x in latest["evaluations"] if x["agent_id"] == a["id"]), None)
                a["final_position"] = {"round": latest["round"], "template_verdict": ev["template_verdict"],
                                       "role_verdict": ev["role_verdict"], "template_scores": ev["template_scores"]} if ev else None
        fg = (fin or {}).get("groups", {}).get(gid, {})
        groups.append({
            "id": gid, "name": g["name"], "style": g.get("consensus", "converge"), "agents": agents, "rounds": rounds,
            "scores": scores, "verdict_counts": verdicts,
            "disagreements": ((analysis or {}).get("within_group") or {}).get(gid, []),
            "stop_go": (sg or {}).get("groups", {}).get(gid),
            "verdict": {"headline": fg.get("headline"), "conclusion": fg.get("conclusion"),
                        "findings": fg.get("findings", []), "pros": fg.get("pros", []),
                        "cons": fg.get("cons", []), "scores": fg.get("scores", {})} if fg else None})
    src_ev = next((e for e in events if e["kind"] == "sources"), None)
    sources = None
    if src_ev:
        from orchestrator.sources import citations
        known = {p["id"] for p in src_ev.get("papers", [])}
        cited_by: dict[str, set] = {}
        unknown = []
        for e in events:
            if e["kind"] in ("turn", "eval"):
                for cid in citations(e.get("text", "")):
                    if cid in known:
                        cited_by.setdefault(cid, set()).add(e["agent"])
                    elif {"agent_id": e["agent"], "id": cid} not in unknown:
                        unknown.append({"agent_id": e["agent"], "id": cid})
        sources = {"provider": "arXiv", "queries": src_ev.get("queries", []), "candidates": src_ev.get("candidates", 0),
                   "used_by_groups": [g["id"] for g in groups_meta if g.get("use_sources")],
                   "papers": [{**{k: p[k] for k in ("id", "title", "authors", "year", "url", "category")},
                               "abstract": p.get("abstract", "")[:600], "cited_by": sorted(cited_by.get(p["id"], []))}
                              for p in src_ev.get("papers", [])],
                   "unknown_citations": unknown, "error": src_ev.get("error")}
    t0 = datetime.fromisoformat(start["t"])
    t1 = datetime.fromisoformat((end or events[-1])["t"])
    slim = [e for e in events if e["kind"] == "slim_group"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "run": {"id": start["run"], "idea": start["idea"], "status": (end or {}).get("status", "incomplete"),
                "started_at": start["t"], "finished_at": (end or {}).get("t"),
                "duration_seconds": round((t1 - t0).total_seconds()), "cost_usd": round(events[-1].get("spent", 0), 5),
                "llm_calls": (end or {}).get("calls"), "max_cost_usd": start.get("max_cost"), "mode": start.get("mode", "deep")},
        "pipeline": {"rounds": len(rounds_seen), "extra_round": 3 in rounds_seen,
                     "stop_go_decision": (sg or {}).get("decision")},
        "groups": groups,
        "cross_group": {"disagreements": (analysis or {}).get("cross_group", []),
                        "agreements": (analysis or {}).get("agreements", [])},
        "stop_go": {"decision": sg["decision"], "consensus_feasible": sg["consensus_feasible"],
                    "rationale": sg["overall"].get("rationale"), "pros": sg["overall"].get("pros", []),
                    "cons": sg["overall"].get("cons", []), "resolve_next": sg.get("if_go_resolve") or None} if sg else None,
        "verdict": _final_overall(fin) if fin else None,
        "reality_check": {"verdict": rc["verdict"], "confidence": rc.get("confidence"), "category": rc.get("category", "none"),
                          "summary": rc["summary"], "blockers": rc.get("blockers", []),
                          "assumptions": rc.get("assumptions", []), "model": rc.get("model")} if rc else None,
        "agntcy": {"transport": "SLIM", "protocol": "A2A", "slim_groups_opened": sum(1 for _ in slim),
                   "endpoints": [f"deliberation/agents/{a['id']}" for g in groups_meta for a in g["agents"]]},
        "analysis": {k: analysis.get(k) for k in ("model", "verified_quotes", "dropped_quotes", "dropped_items")} if analysis else None,
        "sources": sources,
    }
