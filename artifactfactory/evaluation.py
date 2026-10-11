"""Real artifact content from the idea's evaluation report.

When an idea arrives with metadata.evaluation_run_id, the builders fetch that run's report from the evaluation
backend (GET {AF_EVAL_API}/api/runs/<id>/report, schema: backend/schema/evaluation-report.schema.json) and use
it instead of placeholders:

  literature_review   assembled from the report: the arXiv papers the agents were given (with who cited each),
                      every group's verdict, scores, pros and cons, verified disagreement quotes, open questions,
                      plus a short related-work synthesis whose citations are checked against the paper list.
  source_repository   a README with the experiment the groups asked for (goal, method, success and stop
                      criteria) and a starter script for it, syntax-checked before it is saved.

Standard library only, like the rest of the factory. Every step degrades: no run id, no backend, no
OPENROUTER_API_KEY or a model error -> the builders' placeholder output, so building never fails because of this.
"""
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

EVAL_API = os.environ.get("AF_EVAL_API", "http://localhost:8090").rstrip("/")
MODEL = os.environ.get("AF_MODEL", "anthropic/claude-haiku-5.5")
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
CITE = re.compile(r"\[arXiv:([^\]\s]+)\]")
OUTCOME = {
    ("stop", True): "Stopped: the evidence was enough to conclude.",
    ("go", True): "Ran one extra round to settle an open question, then finished.",
    ("stop", False): "Disagreement kept: the groups cannot converge, so a person should decide.",
    ("go", False): "Ran one extra round; the groups still cannot converge, so a person should decide.",
}


def run_id_of(idea: Dict[str, Any]) -> Optional[str]:
    rid = (idea.get("metadata") or {}).get("evaluation_run_id")
    return rid if isinstance(rid, str) and re.fullmatch(r"[\w-]{6,64}", rid) else None


def fetch_report(run_id: str) -> Optional[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(f"{EVAL_API}/api/runs/{run_id}/report", timeout=10) as r:
            rep = json.load(r)
        return rep if isinstance(rep, dict) and rep.get("groups") and rep.get("run") else None
    except (urllib.error.URLError, ValueError, OSError):
        return None


def report_for(ctx) -> Optional[Dict[str, Any]]:
    """The report for this build, fetched once per job and shared by every builder."""
    if not hasattr(ctx, "_evaluation_report"):
        rid = run_id_of(ctx.idea)
        ctx._evaluation_report = fetch_report(rid) if rid else None
    return ctx._evaluation_report


def chat(prompt: str, max_tokens: int = 1500, model: Optional[str] = None, timeout: int = 90) -> Optional[str]:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return None
    body = {"model": model or MODEL, "max_tokens": max_tokens, "reasoning": {"effort": "none"},
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(OPENROUTER, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "Artifact Factory"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        return (data["choices"][0]["message"].get("content") or "").strip() or None
    except (urllib.error.URLError, KeyError, ValueError, OSError):
        return None


def _json_in(text: Optional[str]) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[start:end + 1]) if start != -1 and end > start else None
    except ValueError:
        return None


def _papers(rep: Dict[str, Any]) -> List[Dict[str, Any]]:
    return ((rep.get("sources") or {}).get("papers")) or []


def _outcome(rep: Dict[str, Any]) -> str:
    sg = rep.get("stop_go") or {}
    return OUTCOME.get((sg.get("decision"), bool(sg.get("consensus_feasible"))), "")


def _agent_names(rep: Dict[str, Any]) -> Dict[str, str]:
    return {a["id"]: a["name"] for g in rep["groups"] for a in g["agents"]}


# ----------------------------------------------------------------------------------------- literature review
def _synthesis(rep: Dict[str, Any], idea: str) -> str:
    """Two short related-work paragraphs; sentences citing anything not in the paper list are removed."""
    papers = _papers(rep)
    if not papers:
        return ""
    listing = "\n".join(f"[arXiv:{p['id']}] {p['title']} ({p['year']}): {p.get('abstract', '')[:500]}" for p in papers)
    text = chat(
        "Write the related-work section of a literature review for this idea, using ONLY these arXiv papers.\n"
        f'Idea: """{idea}"""\n\nPapers:\n{listing}\n\n'
        "Two paragraphs, at most 220 words in total. Group the papers by what they show; say what they establish and "
        "what they leave open for this idea. Cite as [arXiv:ID] using only the ids above. Plain prose, no headings, "
        "no bullet points, do not invent results that are not in the abstracts.", max_tokens=900)
    if not text:
        return ""
    known = {p["id"] for p in papers}
    kept = [s for s in re.split(r"(?<=[.!?])\s+", text) if all(c in known for c in CITE.findall(s))]
    out = " ".join(kept).strip()
    return out if CITE.search(out) else ""


def literature_review_md(rep: Dict[str, Any], title: str, idea: str) -> str:
    run = rep["run"]
    names = _agent_names(rep)
    verdict = rep.get("verdict") or {}
    lines = [
        f"# Literature review: {title}", "",
        f"_Generated from evaluation run `{run['id']}` ({run.get('mode', 'deep')} mode, {run.get('finished_at') or run['started_at']}). "
        "Every paper below comes from arXiv, and every quote was checked word for word against the agent who said it._", "",
        "## The idea", "", f"> {idea}", "",
        "## Verdict", "", f"**{verdict.get('headline') or 'No verdict recorded.'}** {verdict.get('conclusion') or ''}".strip(), "",
    ]
    if _outcome(rep):
        lines += [f"Deliberation: {_outcome(rep)}", ""]

    papers = _papers(rep)
    if papers:
        lines += ["## Related work", ""]
        synthesis = _synthesis(rep, idea)
        if synthesis:
            lines += [synthesis, ""]
        for p in papers:
            cited = ", ".join(names.get(a, a) for a in p.get("cited_by", [])) or "not cited in the discussion"
            authors = ", ".join(p.get("authors") or []) + (" et al." if len(p.get("authors") or []) >= 3 else "")
            lines += [f"### [{p['title']}]({p['url']})", f"{authors} ({p['year']}) · arXiv:{p['id']} · cited by: {cited}", ""]
            if p.get("abstract"):
                lines += [f"> {p['abstract'][:600]}{'…' if len(p['abstract']) > 600 else ''}", ""]

    lines += ["## What each group concluded", ""]
    for g in rep["groups"]:
        v = g.get("verdict") or {}
        lines += [f"### {g['name']}", ""]
        if v.get("headline"):
            lines += [f"**{v['headline']}** {v.get('conclusion') or ''}".strip(), ""]
        if g.get("scores"):
            lines += ["| Metric | Median | Range | Members |", "|---|---|---|---|"]
            lines += [f"| {m} | {s['median']} | {s['min']}-{s['max']} | {s['n']} |" for m, s in g["scores"].items()]
            lines += [""]
        for label, items in (("Pros", v.get("pros")), ("Cons", v.get("cons"))):
            if items:
                lines += [f"**{label}**", ""] + [f"- {x}" for x in items] + [""]

    cross = (rep.get("cross_group") or {}).get("disagreements") or []
    within = [(g["name"], d) for g in rep["groups"] for d in (g.get("disagreements") or [])[:2]]
    if cross or within:
        lines += ["## Where they disagreed", ""]
        for d in cross:
            sides = "; ".join(f"{s['group_id']}: {s['position']}" for s in d.get("sides", []))
            lines += [f"- **{d['topic']}** ({d.get('status', 'open')}). {sides}"]
            lines += [f"  - \"{q['quote']}\" ({names.get(q['agent_id'], q['agent_id'])})" for q in d.get("evidence", [])]
        for gname, d in within:
            sides = "; ".join(f"{', '.join(names.get(a, a) for a in s['agent_ids'])}: {s['position']}" for s in d.get("sides", []))
            lines += [f"- **{d['topic']}** within {gname} ({d.get('status', 'open')}). {sides}"]
        lines += [""]

    questions = []
    for g in rep["groups"]:
        last = next((r for r in reversed(g.get("rounds") or []) if r.get("summary")), None)
        for q in ((last or {}).get("summary") or {}).get("open_questions") or []:
            if q not in questions:
                questions.append(q)
    if questions:
        lines += ["## Open questions", ""] + [f"- {q}" for q in questions[:10]] + [""]

    if papers:
        lines += ["## References", ""]
        for i, p in enumerate(papers, 1):
            authors = ", ".join(p.get("authors") or []) + (" et al." if len(p.get("authors") or []) >= 3 else "")
            lines += [f"{i}. {authors} ({p['year']}). {p['title']}. arXiv:{p['id']}. {p['url']}"]
        lines += [""]
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------- source repository
def _experiment_context(rep: Dict[str, Any]) -> str:
    parts = []
    for g in rep["groups"]:
        v = g.get("verdict") or {}
        parts.append(f"{g['name']}: {v.get('headline', '')} {v.get('conclusion', '')}")
        last = next((r for r in reversed(g.get("rounds") or []) if r.get("summary")), None)
        oq = ((last or {}).get("summary") or {}).get("open_questions") or []
        if oq:
            parts.append(f"  open questions: {'; '.join(oq[:4])}")
    for g in rep["groups"]:  # the research group's own experiment proposals, if it wrote any
        for r in g.get("rounds") or []:
            for ev in r.get("evaluations") or []:
                m = re.search(r"(?is)experiments? needed[^\n]*\n(.{0,700})", ev.get("text", ""))
                if m:
                    parts.append(f"  proposed experiment ({ev['agent_id']}): {m.group(1).strip()}")
    sg = rep.get("stop_go") or {}
    if sg.get("resolve_next"):
        parts.append(f"Still to settle: {sg['resolve_next']}")
    return "\n".join(parts)[:6000]


def source_repo(rep: Dict[str, Any], title: str, idea: str) -> Optional[Dict[str, Any]]:
    """{'readme': str, 'files': {path: content}} for a Python experiment repo, or None (placeholders are used)."""
    obj = _json_in(chat(
        "You are setting up the first experiment for an idea after an evaluation panel reviewed it.\n"
        f'Idea: """{idea}"""\n\nWhat the panel concluded:\n{_experiment_context(rep)}\n\n'
        "Design the single cheapest experiment that would settle the panel's main open question, then write a starter "
        "Python script for it. Reply with JSON only:\n"
        '{"goal": "one sentence", "hypothesis": "one sentence", "method": ["step", "step", "step"], '
        '"success_criteria": ["measurable threshold"], "stop_criteria": ["measurable threshold"], '
        '"experiment_py": "the full script", "requirements": ["package", ...]}\n'
        "The script must run as-is with `python experiment.py`: standard library plus the listed packages only, "
        "synthetic or clearly marked sample data (never pretend data is real), a main() that runs the measurement and "
        "prints results against the success criteria, and TODO comments where real systems must be plugged in. "
        "Under 150 lines.", max_tokens=4000))
    if not obj or not isinstance(obj.get("experiment_py"), str):
        return None
    code = obj["experiment_py"].strip() + "\n"
    try:
        compile(code, "experiment.py", "exec")
    except SyntaxError:
        return None
    reqs = [r for r in obj.get("requirements") or [] if isinstance(r, str) and re.fullmatch(r"[A-Za-z0-9_.\-\[\]=<>~!]+", r)][:10]
    run = rep["run"]
    verdict = rep.get("verdict") or {}
    bullet = lambda xs: "\n".join(f"- {x}" for x in xs if isinstance(x, str)) or "- (none given)"
    papers = _papers(rep)
    readme = "\n".join([
        f"# {title}", "",
        f"First experiment for this idea, set up from evaluation run `{run['id']}`.", "",
        "## Why this experiment", "",
        f"**Panel verdict:** {verdict.get('headline') or 'not recorded'}", "",
        f"{_outcome(rep)}".strip(), "",
        f"**Goal:** {obj.get('goal', '')}", "",
        f"**Hypothesis:** {obj.get('hypothesis', '')}", "",
        "## Method", "", "\n".join(f"{i}. {s}" for i, s in enumerate(obj.get("method") or [], 1) if isinstance(s, str)), "",
        "## Success criteria", "", bullet(obj.get("success_criteria") or []), "",
        "## Stop criteria", "", bullet(obj.get("stop_criteria") or []), "",
        "## Run it", "", "```bash",
        *(["pip install -r requirements.txt"] if reqs else []), "python experiment.py", "```", "",
        "`experiment.py` is a starter: it uses synthetic or sample data and marks with TODO where real systems plug in.",
        *(["", "## Read first", ""] + [f"- [{p['title']}]({p['url']}) ({p['year']})" for p in papers[:5]] if papers else []), "",
    ])
    files = {"experiment.py": code}
    if reqs:
        files["requirements.txt"] = "\n".join(reqs) + "\n"
    return {"readme": readme, "files": files}
