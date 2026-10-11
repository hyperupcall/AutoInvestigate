"""The idea-evaluation pipeline:

  1. every group discusses the idea (timed round-robin)        5. re-evaluate with all summaries + template
  2. every agent writes its evaluation                         6. summarize again
  3. the summarizer writes each group's pros and cons          7. stop or go?  go -> one more discuss/evaluate/summarize
  4. a second discussion, with every group's summary shared    8. final conclusions for each group (always)

The orchestrator only relays and records; agents and the summarizer/judge models do the thinking."""
import asyncio

from council import openrouter as orr
from council import prompts, settings
from council.openrouter import BudgetExceeded
from orchestrator.run import Run, transcript_text


def summaries_block(groups: list[dict], summaries: dict[str, str]) -> str:
    return "\n\n".join(f"=== {g['name']} ===\n{summaries.get(g['id'], '(no summary)')}" for g in groups)


async def stage_call(run: Run, stage_cfg: str, budget_key: str, prompt: str, validate=None):
    """Summarizer or judge call made directly by the orchestrator (these are not deliberating agents)."""
    s = run.s
    cfg = s["stages"][stage_cfg]
    kw = dict(max_tokens=s["max_tokens"][budget_key], reasoning_effort=s["reasoning_effort"][budget_key],
              budget=run.budget, web_results=s["web_search_results"])
    key = settings.resolve_key(cfg.get("api_key", ""), s)
    if validate is None:
        res = await orr.chat(cfg["model"], [{"role": "user", "content": prompt}], key, **kw)
        return res.text, res
    return await orr.chat_json(cfg["model"], [{"role": "user", "content": prompt}], key, validate, **kw)


async def summarize(run: Run, group: dict, stage: str, transcript: list[dict], evals: dict[str, str]) -> str:
    names = {a["id"]: a["name"] for a in group["agents"]}
    run.log("stage_start", stage=stage, group=group["id"])
    prompt = prompts.system("summarize", GROUP_NAME=group["name"], IDEA=run.idea,
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


async def stop_or_go(run: Run, groups: list[dict], summaries: dict[str, str]) -> dict:
    ids = [g["id"] for g in groups]
    run.log("stage_start", stage="stop_go")
    prompt = prompts.system("stop_go", IDEA=run.idea, SUMMARIES=summaries_block(groups, summaries),
                            GROUP_IDS='", "'.join(ids))

    def validate(o):
        if o.get("decision") not in ("stop", "go"):
            return "decision must be 'stop' or 'go'"
        if not isinstance(o.get("overall"), dict):
            return "overall is required"
        return _check_groups(o, ids, ("pros", "cons", "rationale"))
    obj, res = await stage_call(run, "judge", "judge", prompt, validate)
    run.log("stop_go", decision=obj["decision"], consensus_feasible=bool(obj.get("consensus_feasible")),
            overall=obj["overall"], groups=obj["groups"], if_go_resolve=obj.get("if_go_resolve", ""),
            model=res.model, cost=res.cost)
    return obj


async def conclude(run: Run, groups: list[dict], summaries: dict[str, str], sg: dict) -> dict:
    ids = [g["id"] for g in groups]
    run.log("stage_start", stage="final")
    sg_text = (f"Decision: {sg['decision']}. Consensus feasible: {sg.get('consensus_feasible')}. "
               f"{sg['overall'].get('rationale', '')}")
    prompt = prompts.system("final", IDEA=run.idea, SUMMARIES=summaries_block(groups, summaries),
                            STOP_GO=sg_text, GROUP_IDS='", "'.join(ids))

    def validate(o):
        if not isinstance(o.get("overall"), dict) or "headline" not in o["overall"]:
            return "overall.headline is required"
        return _check_groups(o, ids, ("headline", "conclusion"))
    obj, res = await stage_call(run, "judge", "judge", prompt, validate)
    run.log("final", overall=obj["overall"], groups=obj["groups"], model=res.model, cost=res.cost)
    return obj


async def round_(run: Run, groups: list[dict], n: int, prior: str, summaries_text: str) -> dict[str, str]:
    """One discuss -> evaluate -> summarize pass for every group (groups run concurrently)."""
    secs = run.s["deliberation_seconds"]
    ts = await asyncio.gather(*[run.deliberate(g, secs, prior, f"deliberation_{n}") for g in groups])
    if n == 1:
        es = await asyncio.gather(*[run.evaluate(g, "evaluation_1", "evaluate", t) for g, t in zip(groups, ts)])
    else:  # later rounds: re-evaluate with every group's summaries and the evaluation template
        es = await asyncio.gather(*[run.evaluate(
            g, f"evaluation_{n}", "cross_review", t, summaries=summaries_text,
            prior_context=f"Your group's latest discussion:\n{transcript_text(t, {a['id']: a['name'] for a in g['agents']})}")
            for g, t in zip(groups, ts)])
    ss = await asyncio.gather(*[summarize(run, g, f"summary_{n}", t, e) for g, t, e in zip(groups, ts, es)])
    return {g["id"]: s for g, s in zip(groups, ss)}


async def pipeline(run: Run) -> str:
    """Run every stage; returns the final status. Always logs run_end."""
    status = "done"
    try:
        await run.start()
        groups = run.s["groups"]
        s1 = await round_(run, groups, 1, "", "")
        shared1 = summaries_block(groups, s1)
        prior2 = ("Every group has finished a first discussion and evaluation. Their summaries:\n\n" + shared1 +
                  "\n\nDiscuss again in light of these. Respond to the other groups' points where they bear on your role.")
        s2 = await round_(run, groups, 2, prior2, shared1)
        latest = s2
        sg = await stop_or_go(run, groups, s2)
        if sg["decision"] == "go":
            shared2 = summaries_block(groups, s2)
            prior3 = ("This is the final discussion round. The latest summaries from every group:\n\n" + shared2 +
                      "\n\nQuestions to settle in this round: " + (sg.get("if_go_resolve") or "the open disagreements above"))
            latest = await round_(run, groups, 3, prior3, shared2)
        await conclude(run, groups, latest, sg)
        try:  # who disagreed with whom, with quotes checked against the transcript (for the JSON report)
            from orchestrator.analysis import analyze
            run.log("analysis", **(await analyze(_events(run), run.s, run.budget)))
        except BudgetExceeded:
            raise
        except Exception as e:
            run.log("note", text=f"Disagreement analysis skipped: {type(e).__name__}: {e}"[:300])
    except BudgetExceeded as e:
        status = "budget_stopped"
        run.log("note", text=str(e))
    except asyncio.CancelledError:
        status = "cancelled"
        run.log("run_end", status=status, calls=run.budget.calls)
        _export(run)
        raise
    except Exception as e:  # keep a readable record of what failed
        status = "error"
        run.log("note", text=f"Run failed: {type(e).__name__}: {e}"[:400])
    run.log("run_end", status=status, calls=run.budget.calls)
    _export(run)
    return status


def _export(run: Run) -> None:
    """Every run, finished or not, gets results/<run_id>.json."""
    try:
        from orchestrator.export import write
        run.log("report", path=write(run.id))
    except Exception as e:
        run.log("note", text=f"Report not written: {type(e).__name__}: {e}"[:300])


def _events(run: Run) -> list[dict]:
    import json
    with open(run.path) as f:
        return [json.loads(l) for l in f if l.strip()]
