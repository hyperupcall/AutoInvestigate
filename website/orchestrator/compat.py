"""Live events in the shape the AutoInvestigate frontend renders (website/frontend/js/mock-backend.js there), built from
our raw run log. The finished report needs no translation: the frontend reads schema/evaluation-report.schema.json
directly (GET /api/runs/<id>/report).

Event kinds, in order: phase, cluster, reality-check, group-start, round-start, turn, missed, evaluation, failed,
summary, cross-group, stop-go, verdict, plus the Evaluation Complex: complex-cluster, complex-turn, complex-verdict,
complex-stop, complex-final.
"""
import re
from datetime import datetime

from deliberation.report import parse_evaluation, parse_summary, _summary_complete


def _round(stage) -> int | None:
    m = re.search(r"_(\d)$", str(stage or ""))
    return int(m.group(1)) if m else None


def _ts(e: dict) -> int:
    return int(datetime.fromisoformat(e["t"]).timestamp() * 1000)


def _label(n: int) -> str:
    return "Extra round" if n == 3 else f"Round {n}"


def ui_events(events: list[dict]) -> list[dict]:
    start = next((e for e in events if e["kind"] == "run_start"), None)
    if not start:
        return []
    groups = {g["id"]: g for g in start.get("groups", [])}
    out, started, rounds, turns = [], set(), set(), {}

    def add(e, **ev):
        out.append({**ev, "ts": _ts(e)})

    for e in events:
        k, n, gid = e["kind"], _round(e.get("stage")), e.get("group")
        g = groups.get(gid, {"name": gid, "consensus": "converge"})
        common = {"group": g.get("name"), "groupId": gid}
        if k == "complex_start":
            add(e, phase="Complex", kind="complex-cluster",
                text=f"Evaluation Complex: {len(e.get('stewards', []))} stewards watching the swarm in parallel.",
                agents=[{"id": s["id"], "name": s.get("name", s["id"]), "model": s.get("model"),
                         "objective": s.get("objective", "")} for s in e.get("stewards", [])])
        elif k == "complex_assess":
            add(e, phase="Complex", kind="complex-turn", round=e.get("round"), agent_id=e.get("steward"),
                name=e.get("name"), model=e.get("model"), text=e.get("reason", ""),
                decision=e.get("decision"), confidence=e.get("confidence"),
                signals=e.get("signals", []), if_continue=e.get("if_continue", ""))
        elif k == "complex_verdict":
            add(e, phase="Complex", kind="complex-verdict", round=e.get("round"), decision=e.get("decision"),
                votes=e.get("votes"), rationale=e.get("rationale"), stewards=e.get("stewards"),
                elapsed=e.get("elapsed"), spent=e.get("spent"))
        elif k == "complex_stop":
            add(e, phase="Complex", kind="complex-stop", by=e.get("by"), reason=e.get("reason"))
        elif k == "complex_final":
            add(e, phase="Complex", kind="complex-final",
                report={key: e.get(key) for key in ("enabled", "decision", "stopped_by", "rounds",
                                                    "stop_votes", "max_seconds", "stewards", "history")})
        elif k == "run_start":
            add(e, phase="Setup", kind="phase", text="Opening SLIM groups and registering agents over A2A.")
            add(e, phase="Setup", kind="cluster",
                text=f"{len(groups)} groups · {sum(len(x['agents']) for x in groups.values())} agents · transport SLIM · protocol A2A",
                groups=[{"id": x["id"], "name": x["name"], "style": x.get("consensus", "converge"),
                         "agents": [{"id": a["id"], "name": a["name"], "model": a["model"],
                                     "mcp_servers": a.get("mcp_servers", [])} for a in x["agents"]]}
                        for x in groups.values()])
        elif k == "stage_start" and gid and str(e["stage"]).startswith("deliberation"):
            if gid not in started:
                started.add(gid)
                add(e, phase="Deliberation", kind="group-start", style=g.get("consensus", "converge"),
                    text=f"{g['name']} enters deliberation ({g.get('consensus', 'converge')}).", **common)
            if (gid, n) not in rounds:
                rounds.add((gid, n))
                add(e, phase=_label(n), kind="round-start", round=n, label=_label(n), shared_summaries_before=n > 1,
                    text=_label(n) + (" · all group summaries were shared first" if n > 1 else ""), **common)
        elif k == "turn":
            turns[(gid, n)] = turns.get((gid, n), 0) + 1
            add(e, phase=_label(n), kind="turn", round=n, agent_id=e["agent"], model=e["model"], text=e["text"],
                turn=turns[(gid, n)], elapsed_seconds=e.get("elapsed"), **common)
        elif k == "turn_failed":
            add(e, phase=_label(n), kind="missed", round=n, agent_id=e["agent"], reason=e.get("error", ""), **common)
        elif k == "eval":
            p = parse_evaluation(e["text"], expect_template=n > 1)
            if e.get("truncated"):
                p["complete"] = False
            add(e, phase=_label(n), kind="evaluation", round=n, agent_id=e["agent"], model=e["model"], text=e["text"], **p, **common)
        elif k == "eval_failed":
            add(e, phase=_label(n), kind="failed", round=n, agent_id=e["agent"], reason=e.get("error", ""), **common)
        elif k == "summary":
            add(e, phase=_label(n), kind="summary", round=n, summary={**parse_summary(e["text"]), "complete": _summary_complete(e)}, **common)
        elif k == "reality_check":
            add(e, phase="Reality check", kind="reality-check", reality_check={
                "verdict": e["verdict"], "confidence": e.get("confidence"), "category": e.get("category", "none"),
                "summary": e["summary"], "blockers": e.get("blockers", []), "assumptions": e.get("assumptions", [])})
        elif k == "stop_go":
            add(e, phase="Stop-or-Go", kind="stop-go", stop_go={
                "decision": e["decision"], "consensus_feasible": e["consensus_feasible"],
                "rationale": e["overall"].get("rationale"), "pros": e["overall"].get("pros", []),
                "cons": e["overall"].get("cons", []), "resolve_next": e.get("if_go_resolve") or None})
        elif k == "final":
            add(e, phase="Verdict", kind="verdict", verdict={"headline": e["overall"].get("headline"),
                                                             "conclusion": e["overall"].get("conclusion")})
        elif k == "analysis":
            add(e, phase="Cross-group", kind="cross-group", cross_group={"disagreements": e.get("cross_group", []),
                                                                         "agreements": e.get("agreements", [])})
        elif k == "sources":
            papers = e.get("papers", [])
            names = ", ".join(x["name"] for x in groups.values() if x.get("use_sources")) or "no group"
            add(e, phase="Setup", kind="phase", papers=papers,
                text=(f"Found {len(papers)} arXiv papers for {names}: " + "; ".join(f"{p['title']} ({p['year']})" for p in papers[:4])
                      + ("…" if len(papers) > 4 else "")) if papers else f"No arXiv papers found ({e.get('error') or 'no match'}).")
        elif k == "note":
            add(e, phase="Notes", kind="phase", text=e["text"])
    return out


def current(events: list[dict]) -> dict:
    """What is happening right now: the phase and the agent id speaking (for "<agent> is thinking…")."""
    for e in reversed(events):
        if e["kind"] == "turn_start":
            return {"phase": _label(_round(e.get("stage")) or 1), "agent_id": e["agent"]}
        if e["kind"] == "stage_start":
            st = str(e.get("stage"))
            label = {"stop_go": "Stop-or-Go", "final": "Verdict"}.get(st) or (_label(_round(st)) if _round(st) else st)
            return {"phase": label, "agent_id": ""}
    return {"phase": "Setup", "agent_id": ""}
