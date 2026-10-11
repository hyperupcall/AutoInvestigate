"""The idea-evaluation pipeline:

  0. a reality check: does the idea make sense in the real world at all?
  1. every group discusses the idea (timed round-robin)        5. re-evaluate with all summaries + template
  2. every agent writes its evaluation                         6. summarize again
  3. the summarizer writes each group's pros and cons          7. stop or go?  go -> one more discuss/evaluate/summarize
  4. a second discussion, with every group's summary shared    8. final conclusions for each group (always)

The orchestrator only relays and records; agents and the summarizer/judge models do the thinking."""
import asyncio

from deliberation import openrouter as orr
from deliberation import prompts, settings
from deliberation.openrouter import BudgetExceeded
from orchestrator.complex import Complex
from orchestrator.run import Run, transcript_text


def summaries_block(groups: list[dict], summaries: dict[str, str]) -> str:
    return "\n\n".join(f"=== {g['name']} ===\n{summaries.get(g['id'], '(no summary)')}" for g in groups)


def _clip(text: str, n: int) -> str:
    """One-line, length-capped text for the final writer's dossier."""
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n].rstrip() + " ..."


def evaluations_block(groups: list[dict], evals: dict[str, dict[str, str]]) -> str:
    """Each group's latest evaluations in full (capped per agent). This is the richest material: the concrete
    numbers, named competitors, cost figures and experiments the summaries squeeze out."""
    names = {a["id"]: a["name"] for g in groups for a in g["agents"]}
    out = []
    for g in groups:
        ev = evals.get(g["id"]) or {}
        if not ev:
            continue
        out.append(f"=== {g['name']} ===")
        out += [f"--- {names.get(aid, aid)} ---\n{_clip(text, 1800)}" for aid, text in ev.items()]
    return "\n\n".join(out) or "(no evaluations)"


def discussion_block(run: "Run", groups: list[dict]) -> str:
    """Each group's latest discussion, capped per turn."""
    out = []
    for g in groups:
        turns = run.transcripts.get(g["id"]) or []
        if not turns:
            continue
        names = {a["id"]: a["name"] for a in g["agents"]}
        out.append(f"=== {g['name']} ===")
        out.append("\n".join(f"{names.get(t['agent'], t['agent'])}: {_clip(t['text'], 700)}" for t in turns))
    return "\n\n".join(out) or "(no discussion)"


def sources_block(run: "Run") -> str:
    """The arXiv papers the groups were given, title plus a capped abstract."""
    papers = (run.sources or {}).get("papers") or []
    if not papers:
        return "No sources were fetched."
    return "\n\n".join(f"[{p['id']}] {p['title']} ({p.get('year', '')})\n{_clip(p.get('abstract', ''), 500)}" for p in papers)


def reality_block(rc: dict | None) -> str:
    """The reality check as text for the stop-or-go and final prompts."""
    if not rc:
        return "No reality check was run."
    lines = [f"Verdict: {rc.get('verdict', '?')} (confidence {rc.get('confidence', '?')}, category {rc.get('category', 'none')}).",
             rc.get("summary", "")]
    if rc.get("blockers"):
        lines.append("Real-world blockers: " + "; ".join(rc["blockers"]))
    if rc.get("assumptions"):
        lines.append("Assumptions that may be false: " + "; ".join(rc["assumptions"]))
    return "\n".join(lines)


def complex_block(run: "Run") -> str:
    """The Evaluation Complex's verdicts as text for the final prompt."""
    cx = getattr(run, "complex", None)
    rep = cx.report if cx else None
    if not rep:
        return "The Evaluation Complex did not run."
    lines = [f"Decision: {rep.get('decision') or 'none'} (stopped by {rep.get('stopped_by') or 'n/a'}, "
             f"{rep.get('rounds', 0)} assessment(s))."]
    for s in rep.get("stewards", []):
        lines.append(f"- {s.get('name', s.get('id'))} ({s.get('objective', '')}): "
                     f"{s.get('decision') or 'no vote'} — {s.get('reason') or ''}")
    return "\n".join(lines)


async def stage_call(run: Run, stage_cfg: str, budget_key: str, prompt: str, validate=None):
    """Summarizer or judge call made directly by the orchestrator (these are not deliberating agents)."""
    s = run.s
    cfg = s["stages"][stage_cfg]
    quick_tokens = {"summarize": 900, "judge": 2400, "final": 3200, "reality_check": 900}
    kw = dict(max_tokens=quick_tokens[budget_key] if run.quick else s["max_tokens"][budget_key],
              reasoning_effort="none" if run.quick else s["reasoning_effort"][budget_key],
              budget=run.budget, web_results=s["web_search_results"])
    key = settings.resolve_key()
    if validate is None:
        res = await orr.chat(cfg["model"], [{"role": "user", "content": prompt}], key, **kw)
        return res.text, res
    return await orr.chat_json(cfg["model"], [{"role": "user", "content": prompt}], key, validate, **kw)


async def summarize(run: Run, group: dict, stage: str, transcript: list[dict], evals: dict[str, str]) -> str:
    names = {a["id"]: a["name"] for a in group["agents"]}
    run.log("stage_start", stage=stage, group=group["id"])
    prompt = prompts.system("summarize_quick" if run.quick else "summarize", GROUP_NAME=group["name"], IDEA=run.idea,
                            TRANSCRIPT=transcript_text(transcript, names) or "(no discussion)",
                            EVALUATIONS="\n\n".join(f"--- {names[a]} ---\n{t}" for a, t in evals.items()) or "(none)")
    text, res = await stage_call(run, "summarizer", "summarize", prompt)
    run.log("summary", stage=stage, group=group["id"], text=text, model=res.model, cost=res.cost,
            truncated=res.finish_reason == "length")
    return text


def _check_groups(obj: dict, ids: list[str], fields: tuple) -> str | None:
    groups = obj.get("groups")
    if not isinstance(groups, dict) or any(i not in groups for i in ids):
        return f"'groups' must contain every group id: {ids}"
    for i in ids:
        if any(f not in groups[i] for f in fields):
            return f"group {i} needs {list(fields)}"
    return None


async def reality_check(run: Run) -> dict | None:
    """One outside call, before any group deliberates: does this idea make sense in the real world at all?
    Advisory only: if the call fails, the run continues without it."""
    run.log("stage_start", stage="reality_check")
    prompt = prompts.system("reality_check", IDEA=run.idea)

    def validate(o):
        if o.get("verdict") not in ("grounded", "questionable", "nonsense"):
            return "verdict must be grounded, questionable or nonsense"
        if not isinstance(o.get("summary"), str) or not o["summary"].strip():
            return "summary is required"
        return None
    try:
        obj, res = await stage_call(run, "reality_check", "reality_check", prompt, validate)
    except BudgetExceeded:
        raise
    except Exception as e:  # never let the reality check break an evaluation
        run.log("note", text=f"Reality check skipped: {type(e).__name__}: {e}"[:300])
        return None
    run.log("reality_check", verdict=obj["verdict"], confidence=obj.get("confidence"),
            category=obj.get("category", "none"), summary=obj["summary"],
            blockers=obj.get("blockers", []), assumptions=obj.get("assumptions", []),
            model=res.model, cost=res.cost)
    return obj


async def stop_or_go(run: Run, groups: list[dict], summaries: dict[str, str]) -> dict:
    ids = [g["id"] for g in groups]
    run.log("stage_start", stage="stop_go")
    prompt = prompts.system("stop_go", IDEA=run.idea, SUMMARIES=summaries_block(groups, summaries),
                            REALITY_CHECK=reality_block(getattr(run, "reality_check", None)),
                            GROUP_IDS='", "'.join(ids))

    def validate(o):
        if o.get("decision") not in ("stop", "go"):
            return "decision must be 'stop' or 'go'"
        if not isinstance(o.get("overall"), dict):
            return "overall is required"
        return _check_groups(o, ids, ("pros", "cons", "rationale"))
    obj, res = await stage_call(run, "judge", "judge", prompt, validate)
    if isinstance(obj.get("if_go_resolve"), list):  # some models return the questions as a list
        obj["if_go_resolve"] = "; ".join(str(x) for x in obj["if_go_resolve"])
    run.log("stop_go", decision=obj["decision"], consensus_feasible=bool(obj.get("consensus_feasible")),
            overall=obj["overall"], groups=obj["groups"], if_go_resolve=obj.get("if_go_resolve", ""),
            model=res.model, cost=res.cost)
    return obj


async def conclude(run: Run, groups: list[dict], summaries: dict[str, str], sg: dict | None, log: bool = True) -> dict:
    ids = [g["id"] for g in groups]
    if log:
        run.log("stage_start", stage="final")
    sg_text = (f"Decision: {sg['decision']}. Consensus feasible: {sg.get('consensus_feasible')}. "
               f"{sg['overall'].get('rationale', '')}") if sg else "The groups' latest positions above are final."
    # The final writer gets the raw material, not just the twice-squeezed summaries: the latest evaluations
    # (numbers, named competitors, costs, experiments), the discussion, and the papers the groups were given.
    prompt = prompts.system("final", IDEA=run.idea, SUMMARIES=summaries_block(groups, summaries),
                            EVALUATIONS=evaluations_block(groups, getattr(run, "latest_evals", {})),
                            DISCUSSION=discussion_block(run, groups), SOURCES=sources_block(run),
                            STOP_GO=sg_text, REALITY_CHECK=reality_block(getattr(run, "reality_check", None)),
                            COMPLEX=complex_block(run), GROUP_IDS='", "'.join(ids))

    def validate(o):
        if not isinstance(o.get("overall"), dict) or "headline" not in o["overall"]:
            return "overall.headline is required"
        return _check_groups(o, ids, ("headline", "conclusion"))
    obj, res = await stage_call(run, "final", "final", prompt, validate)
    if log:
        run.log("final", overall=obj["overall"], groups=obj["groups"], model=res.model, cost=res.cost)
    return {**obj, "_model": res.model, "_cost": res.cost}


async def round_(run: Run, groups: list[dict], n: int, prior: str, summaries_text: str) -> dict[str, str]:
    """One discuss -> evaluate -> summarize pass for every group (groups run concurrently)."""
    secs = run.s["deliberation_seconds"]

    async def discuss(g):
        if g.get("use_sources") and run.s["sources"]["enabled"]:
            await run.ensure_sources()  # groups without sources start right away
        before = run.transcripts.get(g["id"])
        p = prior + (f"\n\nYour group's previous discussion:\n{transcript_text(before, {a['id']: a['name'] for a in g['agents']})}"
                     if before else "")
        t = await run.deliberate(g, secs, p, f"deliberation_{n}")
        run.transcripts[g["id"]] = t
        return t
    ts = await asyncio.gather(*[discuss(g) for g in groups])
    if n == 1:
        es = await asyncio.gather(*[run.evaluate(g, "evaluation_1", "evaluate", t) for g, t in zip(groups, ts)])
    else:  # later rounds: re-evaluate with every group's summaries and the evaluation template
        es = await asyncio.gather(*[run.evaluate(
            g, f"evaluation_{n}", "cross_review", t, summaries=summaries_text,
            prior_context=f"Your group's latest discussion:\n{transcript_text(t, {a['id']: a['name'] for a in g['agents']})}")
            for g, t in zip(groups, ts)])
    ss = await asyncio.gather(*[summarize(run, g, f"summary_{n}", t, e) for g, t, e in zip(groups, ts, es)])
    run.latest_evals = {g["id"]: e for g, e in zip(groups, es)}  # the final writer reads these (see conclude)
    run.summaries = {g["id"]: s for g, s in zip(groups, ss)}  # the Evaluation Complex reads these
    if run.complex:
        run.complex.note_round()  # a swarm round landed: the stewards assess again
    return run.summaries


async def pipeline(run: Run) -> str:
    """Run every stage; returns the final status. Always logs run_end."""
    status = "done"
    try:
        await run.start()
        groups = run.s["groups"]
        run.reality_check = await reality_check(run)
        # The Evaluation Complex watches the swarm in parallel for the whole run (see orchestrator/complex.py).
        run.complex = Complex(run)
        if run.complex.enabled:
            run.complex_task = asyncio.ensure_future(run.complex.run_forever())
        s1 = await round_(run, groups, 1, "", "")
        if run.complex_stop.is_set():  # the stewards stopped the swarm: write the verdict from what exists
            return await _finish_now(run, groups, s1)
        shared1 = summaries_block(groups, s1)
        prior2 = ("Every group has finished a first discussion and evaluation. Their summaries:\n\n" + shared1 +
                  "\n\nDiscuss again in light of these. Respond to the other groups' points where they bear on your role.")
        s2 = await round_(run, groups, 2, prior2, shared1)
        if run.complex_stop.is_set():
            return await _finish_now(run, groups, s2)
        latest = s2
        early = None
        if run.quick:  # write the verdict and the analysis while stop-or-go is decided; used only if it says stop
            early = (asyncio.ensure_future(conclude(run, groups, s2, None, log=False)),
                     asyncio.ensure_future(_analysis(run, log=False)))
        sg = await stop_or_go(run, groups, s2)
        if run.complex_stop.is_set():
            for t in early or ():
                t.cancel()
            return await _finish_now(run, groups, s2)
        if early and sg["decision"] == "stop":
            fin, an = await asyncio.gather(*early, return_exceptions=True)
            if isinstance(fin, BaseException):
                raise fin
            run.log("stage_start", stage="final")
            run.log("final", overall=fin["overall"], groups=fin["groups"], model=fin["_model"], cost=fin["_cost"])
            if isinstance(an, dict):
                run.log("analysis", **an)
            return await _finish(run, "done")
        for t in early or ():
            t.cancel()
        if sg["decision"] == "go":
            shared2 = summaries_block(groups, s2)
            prior3 = ("This is the final discussion round. The latest summaries from every group:\n\n" + shared2 +
                      "\n\nQuestions to settle in this round: " + (sg.get("if_go_resolve") or "the open disagreements above"))
            latest = await round_(run, groups, 3, prior3, shared2)
            if run.complex_stop.is_set():
                return await _finish_now(run, groups, latest)
        # The complex is done watching: stop it and log its report before the verdict (the final writer reads it).
        _stop_complex(run)
        _finalize_complex(run)
        # The verdict and the disagreement analysis (for the JSON report) run at the same time.
        done = await asyncio.gather(conclude(run, groups, latest, sg), _analysis(run), return_exceptions=True)
        if isinstance(done[0], BaseException):
            raise done[0]
    except BudgetExceeded as e:
        status = "budget_stopped"
        run.log("note", text=str(e))
    except asyncio.CancelledError:
        status = "cancelled"
        _stop_complex(run)
        _finalize_complex(run)
        run.log("run_end", status=status, calls=run.budget.calls)
        _export(run)
        raise
    except Exception as e:  # keep a readable record of what failed
        status = "error"
        run.log("note", text=f"Run failed: {type(e).__name__}: {e}"[:400])
    finally:
        _stop_complex(run)
        _finalize_complex(run)
    run.log("run_end", status=status, calls=run.budget.calls)
    _export(run)
    return status


async def _finish_now(run: Run, groups: list[dict], summaries: dict[str, str]) -> str:
    """The Evaluation Complex stopped the swarm: log its report and write the verdict from what exists."""
    _stop_complex(run)
    _finalize_complex(run)
    run.log("stage_start", stage="final")
    done = await asyncio.gather(conclude(run, groups, summaries, None), _analysis(run), return_exceptions=True)
    if isinstance(done[0], BaseException):
        raise done[0]
    return await _finish(run, "done")


def _stop_complex(run: Run) -> None:
    """Cancel the complex's background task (it is done watching). Safe to call more than once."""
    task = getattr(run, "complex_task", None)
    if task and not task.done():
        task.cancel()


def _finalize_complex(run: Run) -> None:
    """Log the complex's own report once (idempotent)."""
    if getattr(run, "complex", None):
        run.complex.finalize()


async def _analysis(run: Run, log: bool = True):
    """Who disagreed with whom, with quotes checked against the transcript."""
    try:
        from orchestrator.analysis import analyze
        result = await analyze(_events(run), run.s, run.budget)
        if log:
            run.log("analysis", **result)
        return result
    except Exception as e:
        run.log("note", text=f"Disagreement analysis skipped: {type(e).__name__}: {e}"[:300])
        return None


async def _finish(run: Run, status: str) -> str:
    run.log("run_end", status=status, calls=run.budget.calls)
    _export(run)
    return status


def _export(run: Run) -> None:
    """Every run, finished or not, gets council_results/<run_id>.json."""
    try:
        from orchestrator.export import write
        run.log("report", path=write(run.id))
    except Exception as e:
        run.log("note", text=f"Report not written: {type(e).__name__}: {e}"[:300])


def _events(run: Run) -> list[dict]:
    import json
    with open(run.path) as f:
        return [json.loads(l) for l in f if l.strip()]
