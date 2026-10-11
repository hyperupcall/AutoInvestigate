"""Benchmark: the multi-agent deliberation vs. one plain model call, same model everywhere.

Track A (deliberation): every agent, the summarizer, the judge, the reality check and the arXiv source picker run on
BASE_MODEL. The idea goes through the normal pipeline over AGNTCY/SLIM and we take its final report.
Track B (baseline): the idea is pasted into BASE_MODEL with one plain request to evaluate it.

Both reports are then graded blind by JUDGE (labels "Report 1"/"Report 2" in random order): plausibility,
actionability and specificity, 1-5 each, plus the concrete errors it found in each report. It does not rate how
good or bad the idea is.

Needs the stack running (docker compose up -d) and OPENROUTER_API_KEY in the environment or the root .env.
The deliberation settings are changed for the run and reset to the repo defaults at the end.

  python3 scripts/benchmark_vs_baseline.py                          # the default ideas, Quick mode
  python3 scripts/benchmark_vs_baseline.py "idea one" "idea two"
  MODE=deep PARALLEL=2 python3 scripts/benchmark_vs_baseline.py ...  # Deep mode, two deliberations at a time
  REUSE_AFTER=<run id> ...       # reuse finished deliberation runs of the same ideas started at or after that run id
  ... --blind                    # no judge: a page with the two reports as "Report A"/"Report B" plus a key file
  python3 scripts/benchmark_vs_baseline.py --reformat results/benchmark/<stamp>-KEY.json
                                 # rewrite both reports of a --blind run into one identical plain layout
Writes results/benchmark/<timestamp>.json and .html (or -blind.html and -KEY.json).
"""
import concurrent.futures as cf
import html
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.request
from datetime import datetime

API = os.environ.get("EVAL_API", "http://localhost:8090")
BASE_MODEL = "openai/gpt-oss-120b"
JUDGE = "deepseek/deepseek-v4-pro"
OUT = os.path.join(os.path.dirname(__file__), "..", "results", "benchmark")
IDEAS = [
    "Homomorphic encryption for privacy-preserving analytics on enterprise customer data, so a cloud provider can run reports without ever seeing the raw data.",
    "Quantum-safe key exchange for enterprise routers, rolled out as a firmware update that adds post-quantum algorithms to existing VPN tunnels.",
    "An AI fridge that tracks when ingredients inside it expire and alerts the household before they go bad.",
    "A browser extension that uses an on-device LLM to flag dark patterns (fake countdown timers, hidden fees, confirmshaming) on e-commerce checkout pages and explains them to the shopper.",
    "A neighborhood tool-lending library run out of a converted shipping container, funded by a 10 dollar monthly membership, so renters can borrow drills, ladders and pressure washers instead of buying them.",
]
BASELINE_PROMPT = "Please evaluate this idea and write me a report on whether it is worth pursuing.\n\nIdea: {idea}"


# ---------------------------------------------------------------- plumbing
def _key() -> str:
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    env = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    for line in open(env):
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"\'')
    sys.exit("OPENROUTER_API_KEY not found")


def http(method: str, url: str, body=None, headers=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def chat(model: str, prompt: str, max_tokens: int, timeout=300, json_mode=False) -> tuple[str, float]:
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
            "usage": {"include": True}}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    err = "empty reply"
    for attempt in range(3):
        try:
            r = http("POST", "https://openrouter.ai/api/v1/chat/completions", body,
                     {"Authorization": f"Bearer {KEY}"}, timeout=timeout)
            text = (r["choices"][0]["message"].get("content") or "").strip()
            if text:
                return text, float((r.get("usage") or {}).get("cost") or 0)
        except Exception as e:  # retry transient failures
            err = e
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"{model} gave no answer: {err}")


# ---------------------------------------------------------------- track A: the deliberation
def deliberation_settings_all_base_model():
    s = http("GET", f"{API}/api/settings")
    s.pop("archetype_library", None)
    s["mode"] = MODE
    s["sources"]["model"] = BASE_MODEL
    # gpt-oss cannot turn reasoning off ("Reasoning is mandatory"); asking for "none" costs a rejected call and
    # a retry per reply, which makes agents miss their turn deadline. Use its lowest allowed effort everywhere.
    s["reasoning_effort"] = {k: "low" for k in s["reasoning_effort"]}
    for stage in s["stages"].values():
        stage["model"] = BASE_MODEL
    for g in s["groups"]:
        for a in g["agents"]:
            a["model"] = BASE_MODEL  # also drops ":online" web search, so both tracks use the bare model
    r = http("PUT", f"{API}/api/settings", s)
    if not r.get("ok"):
        sys.exit(f"could not save deliberation settings: {r}")


def earlier_run(idea: str) -> str | None:
    """A deliberation run of this idea from this benchmark (id at or after REUSE_AFTER), finished or still running."""
    if not REUSE_AFTER:
        return None
    for r in http("GET", f"{API}/api/runs"):
        if r["id"] >= REUSE_AFTER and r["idea"] == idea and r["status"] in ("done", "running"):
            return r["id"]
    return None


def run_deliberation(idea: str) -> dict:
    t0 = time.time()
    rid = earlier_run(idea)
    while not rid:
        try:
            rid = http("POST", f"{API}/api/evaluate", {"idea": idea, "overrides": {"mode": MODE}})["run_id"]
        except urllib.error.HTTPError as e:
            if e.code != 409:
                raise
            time.sleep(10)  # another evaluation is running
    while True:
        time.sleep(5)
        try:
            if not http("GET", f"{API}/api/ui/runs/{rid}/events?since=0").get("running"):
                break
        except Exception:  # the backend restarting or busy: keep waiting
            continue
    rep = http("GET", f"{API}/api/runs/{rid}/report", timeout=300)
    ev = http("GET", f"{API}/api/ui/runs/{rid}/events?since=0").get("events", [])
    missed = sum(1 for e in ev if e.get("kind") in ("missed", "failed"))
    models = {a["model"] for g in rep.get("groups", []) for a in g.get("agents", [])}
    if models != {BASE_MODEL}:
        sys.exit(f"run {rid} did not use {BASE_MODEL} for every agent: {models}")
    secs = (rep.get("run") or {}).get("duration_seconds") or round(time.time() - t0)
    return {"run_id": rid, "text": deliberation_text(rep), "seconds": round(secs),
            "cost_usd": (rep.get("run") or {}).get("cost_usd"), "missed_replies": missed}


def deliberation_text(r: dict) -> str:
    """The deliberation's final report as plain text: what a user reads, without internal ids."""
    out = []
    v = r.get("verdict") or {}
    out += ["FINAL VERDICT", v.get("headline", ""), v.get("conclusion", ""), ""]
    rc = r.get("reality_check") or {}
    if rc:
        out += ["REALITY CHECK", f"Verdict: {rc.get('verdict')}. {rc.get('summary', '')}"]
        out += [f"- Assumption: {x}" for x in rc.get("assumptions", [])] + [f"- Blocker: {x}" for x in rc.get("blockers", [])] + [""]
    names = {g["id"]: g["name"] for g in r.get("groups", [])}
    for g in r.get("groups", []):
        gv = g.get("verdict") or {}
        out += [g["name"].upper(), gv.get("headline", ""), gv.get("conclusion", "")]
        out += ["Strengths:"] + [f"- {x}" for x in gv.get("pros", [])] + ["Weaknesses:"] + [f"- {x}" for x in gv.get("cons", [])]
        sc = ", ".join(f"{k} {v['median']}/10" for k, v in (g.get("scores") or {}).items())
        if sc:
            out.append(f"Scores (median): {sc}")
        out.append("")
    dis = (r.get("cross_group") or {}).get("disagreements") or []
    if dis:
        out.append("WHERE THE GROUPS DISAGREE")
        for d in dis:
            sides = "; ".join(f"{names.get(s.get('group_id'), s.get('group_id'))}: {s.get('position')}" for s in d.get("sides", []))
            out.append(f"- {d.get('topic')}: {sides}")
        out.append("")
    sg = r.get("stop_go") or {}
    if sg.get("rationale"):
        out += ["DELIBERATION OUTCOME", sg["rationale"], ""]
    papers = (r.get("sources") or {}).get("papers") or []
    if papers:
        out += ["SOURCES"] + [f"- arXiv:{p['id']} {p['title']} ({p.get('year', '')})" for p in papers]
    return "\n".join(x for x in out if x is not None).strip()


# ---------------------------------------------------------------- track B: the baseline
def run_baseline(idea: str) -> dict:
    t0 = time.time()
    text, cost = chat(BASE_MODEL, BASELINE_PROMPT.format(idea=idea), max_tokens=8000)
    return {"text": text, "seconds": round(time.time() - t0), "cost_usd": cost}


# ---------------------------------------------------------------- judging
JUDGE_PROMPT = """You are an expert reviewer grading two independent evaluation reports about the same idea. Grade
each report on its own merits. Judge correctness and usefulness, not length, formatting or tone; a longer report
earns nothing for length, and every extra claim is one more chance to be wrong.

IDEA:
\"\"\"{idea}\"\"\"

=== REPORT 1 ===
{r1}

=== REPORT 2 ===
{r2}

Note on sources: any arXiv papers listed in either report were retrieved live from arXiv for this evaluation and do
exist, including ones dated after your training data. Do not treat a paper as fabricated because you do not know it;
judge whether it is relevant to the idea and whether the report uses it correctly.

Score each report from 1 to 5 on:
- plausibility: does the idea, as the report presents it, make sense? Even if it is far-fetched, does the report
  back its claims and recommended actions with evidence? Rate the report's grounding, not whether the idea is good.
- actionability: could a concrete plan be built from this idea using the hints in the report, and an artifact then
  be built from that plan?
- specificity: are the details specific (concrete risks, alternatives, numbers, tests) rather than generic advice?

Do not rate how good or bad the idea is, and do not reward length, formatting or tone; a longer report earns
nothing for length, and every extra claim is one more chance to be wrong.

Then list the concrete factual errors or unsupported claims you found in each (quote briefly; empty list if none).

Reply with JSON only:
{{"report_1": {{"plausibility": n, "actionability": n, "specificity": n, "errors": ["..."]}},
 "report_2": {{"plausibility": n, "actionability": n, "specificity": n, "errors": ["..."]}},
 "better": 1 or 2, "why": "two sentences"}}"""
METRICS = ["plausibility", "actionability", "specificity"]


def judge(idea: str, deliberation: str, baseline: str) -> dict:
    """One blind grading of both reports; which one is shown first is random."""
    deliberation_first = random.random() < 0.5
    r1, r2 = (deliberation, baseline) if deliberation_first else (baseline, deliberation)
    text, cost = chat(JUDGE, JUDGE_PROMPT.format(idea=idea, r1=r1, r2=r2), max_tokens=6000, json_mode=True)
    o = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    c, b = (o["report_1"], o["report_2"]) if deliberation_first else (o["report_2"], o["report_1"])
    better = "deliberation" if (o.get("better") == 1) == deliberation_first else "baseline"
    return {"deliberation_first": deliberation_first, "deliberation": c, "baseline": b, "better": better,
            "why": o.get("why", ""), "cost_usd": cost}


# ---------------------------------------------------------------- report
def summarize(items: list[dict]) -> dict:
    graded = [it for it in items if it.get("grade")]
    s = {side: {k: round(statistics.mean(float(it["grade"][side][k]) for it in graded), 2) for k in METRICS}
         for side in ("deliberation", "baseline")}
    s["deliberation_wins"] = sum(it["grade"]["better"] == "deliberation" for it in graded)
    s["graded"] = len(graded)
    return s


def write_html(res: dict, path: str):
    e = html.escape
    S = res["summary"]
    rows = "".join(f"<tr><td>{k.capitalize()}</td><td><b>{S['deliberation'][k]}</b></td><td>{S['baseline'][k]}</td>"
                   f"<td class=\"{'ok' if S['deliberation'][k] > S['baseline'][k] else 'bad'}\">{S['deliberation'][k] - S['baseline'][k]:+.2f}</td></tr>"
                   for k in METRICS)
    idea_rows, per = "", ""
    for n, it in enumerate(res["items"], 1):
        g = it.get("grade")
        if not g:
            continue
        gc, gb = g["deliberation"], g["baseline"]
        idea_rows += (f"<tr><td>{n}. {e(it['idea'][:70])}{'…' if len(it['idea']) > 70 else ''}</td>"
                      + "".join(f"<td><b>{gc[k]}</b></td><td>{gb[k]}</td>" for k in METRICS)
                      + f"<td class=\"{'ok' if g['better'] == 'deliberation' else 'bad'}\">{g['better']}</td></tr>")
        per += (f"<div class=\"card\"><h3>{n}. {e(it['idea'])}</h3>"
                f"<p class=\"small\">Judge prefers <b>{g['better']}</b>. {e(g['why'])}</p>"
                f"<table><tr><th></th>{''.join(f'<th>{k.capitalize()}</th>' for k in METRICS)}</tr>"
                f"<tr><td>Deliberation</td>{''.join(f'<td>{gc[k]}</td>' for k in METRICS)}</tr>"
                f"<tr><td>Baseline</td>{''.join(f'<td>{gb[k]}</td>' for k in METRICS)}</tr></table>"
                f"<p class=\"small muted\">Errors the judge found in the deliberation report: {e('; '.join(g['deliberation'].get('errors') or []) or 'none')}</p>"
                f"<p class=\"small muted\">Errors the judge found in the baseline report: {e('; '.join(g['baseline'].get('errors') or []) or 'none')}</p>"
                f"<p class=\"small muted\">Deliberation: {it['deliberation']['seconds']} s, ${it['deliberation']['cost_usd'] or 0:.3f}, "
                f"{it['deliberation'].get('missed_replies', 0)} missed replies. Baseline: {it['baseline']['seconds']} s, ${it['baseline']['cost_usd']:.4f}.</p>"
                f"<details><summary>Deliberation final report</summary><pre>{e(it['deliberation']['text'])}</pre></details>"
                f"<details><summary>Baseline report</summary><pre>{e(it['baseline']['text'])}</pre></details></div>")
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Deliberation vs Baseline</title><style>
*{{box-sizing:border-box}}body{{margin:0;font-family:system-ui,sans-serif;font-size:14px;line-height:1.5;color:black;background:white}}
header{{padding:8px 12px;border-bottom:1px solid silver}}header h1{{font-size:15px;margin:0}}header p{{font-size:12px;color:gray;margin:0}}
main{{max-width:1000px;margin:0 auto;padding:10px 12px}}h2{{font-size:14px;margin:14px 0 6px}}h3{{font-size:13px;margin:0 0 4px}}
.card{{border:1px solid silver;padding:8px 10px;margin-bottom:8px}}.muted{{color:gray}}.small{{font-size:12px}}p{{margin:4px 0}}
table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid gainsboro;padding:4px 6px;text-align:left}}th{{font-size:12px;color:gray}}
.ok{{color:green}}.bad{{color:red}}details{{border:1px solid silver;padding:4px 8px;margin-top:6px}}summary{{cursor:pointer;font-size:12px;color:gray}}
pre{{white-space:pre-wrap;font-size:12px;background:whitesmoke;padding:6px}}</style></head><body>
<header><h1>Multi-agent deliberation vs single-model baseline</h1>
<p>Same model ({e(res['base_model'])}) on both sides &middot; {len(res['items'])} ideas &middot; graded blind by {e(res['judge'])} &middot; {e(res['finished_at'])}</p></header>
<main>
<h2>Result</h2>
<div class="card"><p>The judge preferred the <b>deliberation</b> report for <b>{S['deliberation_wins']} of {S['graded']}</b> ideas.</p>
<table><tr><th>Score (1-5, mean over ideas)</th><th>Deliberation (13 agents)</th><th>Baseline (one call)</th><th>Difference</th></tr>{rows}</table></div>
<div class="card"><table><tr><th>Idea</th>{''.join(f'<th>Deliberation {k}</th><th>Baseline {k}</th>' for k in METRICS)}<th>Preferred</th></tr>{idea_rows}</table></div>
<h2>Method</h2>
<div class="card small"><p><b>Deliberation:</b> the AutoInvestigate pipeline in {e(res.get('mode', 'quick').capitalize())} mode. 13 agents in three groups (research, private equity,
market), each with its own persona and question, each its own AGNTCY/SLIM endpoint; reality check, deliberation, evaluations,
group summaries, cross-group review, stop-or-go and a final verdict. arXiv papers are retrieved for two groups. Every model call uses
{e(res['base_model'])} at its lowest reasoning effort (it cannot run with reasoning off).</p>
<p><b>Baseline:</b> one call to {e(res['base_model'])} with the prompt <i>"{e(BASELINE_PROMPT.split(chr(10))[0])}"</i> followed by the idea.</p>
<p><b>Grading:</b> {e(res['judge'])} reads both reports, labeled only "Report 1" and "Report 2" in random order, scores each 1-5 on
plausibility, actionability and specificity, and lists the factual errors it finds. It is told not to reward length and not to
rate how good or bad the idea is.</p></div>
<h2>Per idea</h2>{per}
</main></body></html>"""
    open(path, "w").write(doc)


FORMAT_MODEL = "anthropic/claude-haiku-5.5"
FORMAT_PROMPT = """Reformat the report below into a fixed plain-text layout. This is formatting only.

Layout rules:
- Plain text. No markdown: no #, *, **, backticks, tables or horizontal rules.
- Section headings in CAPITALS on their own line, with a blank line before each.
- Lists as lines starting with "- ". Turn any table into "- " lines, one per row.
- Start with a section called SUMMARY using the report's own opening verdict or summary.

Content rules (strict):
- Keep every claim, number, source, risk, recommendation and conclusion, in the report's own wording where possible.
- Do not add anything, do not drop anything, do not fix or soften anything, even if you think it is wrong.
- Keep sub-labels such as "Strengths:" and "Weaknesses:" so it stays clear which points are which.
- Remove only references to how the report was produced (named groups, agents, panels, personas, rounds,
  deliberation, researchers/investors/customers/the team "found" or "recommend"): state those
  conclusions directly, keeping what they say about the idea.
- Section headings name the topic, not who wrote it (for example TECHNICAL ASSESSMENT, INVESTMENT ASSESSMENT,
  MARKET ASSESSMENT, RISKS, NEXT STEPS, SOURCES).

Reply with the reformatted report only.

REPORT:
{text}"""


def reformat(key_path: str):
    """Rewrite both reports of every idea into the same plain layout, then rebuild the blind page with the same
    A/B assignment. The original texts stay in the key file."""
    data = json.load(open(key_path))

    for it in data["items"]:  # re-render the deliberation text from its report with the current deliberation_text()
        it["deliberation"]["text"] = deliberation_text(http("GET", f"{API}/api/runs/{it['deliberation']['run_id']}/report", timeout=300))

    def one(text):
        return chat(FORMAT_MODEL, FORMAT_PROMPT.format(text=text), max_tokens=12000)[0]

    with cf.ThreadPoolExecutor(10) as pool:
        jobs = {(i, side): pool.submit(one, it[side]["text"]) for i, it in enumerate(data["items"])
                for side in ("deliberation", "baseline")}
        for (i, side), f in jobs.items():
            data["items"][i][side]["plain_text"] = f.result()
    json.dump(data, open(key_path, "w"), indent=2, ensure_ascii=False)
    stamp = os.path.basename(key_path).replace("-KEY.json", "")
    items = [{**it, "deliberation": {**it["deliberation"], "text": it["deliberation"]["plain_text"]},
              "baseline": {**it["baseline"], "text": it["baseline"]["plain_text"]}} for it in data["items"]]
    write_blind(items, stamp + "-plain", order=[k["A"] == "deliberation" for k in data["key"]], key_extra=data)


def write_blind(items: list[dict], stamp: str, order: list[bool] | None = None, key_extra: dict | None = None):
    """For people to judge: per idea, the two reports as "Report A" and "Report B" in random order, nothing else.
    Which is which goes to a separate key file."""
    e = html.escape
    key, cards = [], ""
    for n, it in enumerate(items, 1):
        deliberation_is_a = order[n - 1] if order else random.random() < 0.5
        a, b = (it["deliberation"], it["baseline"]) if deliberation_is_a else (it["baseline"], it["deliberation"])
        key.append({"idea": it["idea"], "A": "deliberation" if deliberation_is_a else "baseline",
                    "B": "baseline" if deliberation_is_a else "deliberation", "deliberation_run_id": it["deliberation"]["run_id"],
                    "deliberation_missed_replies": it["deliberation"].get("missed_replies")})
        cards += (f"<section><h2>Idea {n}</h2><p class=\"idea\">{e(it['idea'])}</p><div class=\"pair\">"
                  f"<div class=\"card\"><h3>Report A</h3><pre>{e(a['text'])}</pre></div>"
                  f"<div class=\"card\"><h3>Report B</h3><pre>{e(b['text'])}</pre></div></div></section>")
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Idea Evaluation Reports</title><style>
*{{box-sizing:border-box}}body{{margin:0;font-family:system-ui,sans-serif;font-size:14px;line-height:1.5;color:black;background:white}}
header{{padding:8px 12px;border-bottom:1px solid silver}}header h1{{font-size:15px;margin:0}}header p{{font-size:12px;color:gray;margin:0}}
main{{max-width:1400px;margin:0 auto;padding:10px 12px}}h2{{font-size:14px;margin:16px 0 2px}}h3{{font-size:13px;margin:0 0 6px}}
.idea{{margin:0 0 8px;color:gray}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
.card{{border:1px solid silver;padding:8px 10px}}pre{{white-space:pre-wrap;font-family:inherit;font-size:13px;margin:0}}
@media (max-width:800px){{.pair{{grid-template-columns:1fr}}}}</style></head><body>
<header><h1>Idea evaluation reports</h1><p>{len(items)} ideas, two reports each. Read both and decide which evaluates the idea better.</p></header>
<main>{cards}</main></body></html>"""
    hpath = os.path.join(OUT, f"{stamp}-blind.html")
    open(hpath, "w").write(doc)
    print(f"\n{os.path.abspath(hpath)}")
    if key_extra is None:  # a reformat keeps the original key file
        kpath = os.path.join(OUT, f"{stamp}-KEY.json")
        json.dump({"base_model": BASE_MODEL, "baseline_prompt": BASELINE_PROMPT, "items": items, "key": key},
                  open(kpath, "w"), indent=2, ensure_ascii=False)
        print(f"key: {os.path.abspath(kpath)}")


def main():
    ideas = sys.argv[1:] or IDEAS
    os.makedirs(OUT, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    deliberation_settings_all_base_model()
    print(f"deliberation set to {BASE_MODEL} everywhere, {MODE} mode; {len(ideas)} ideas", flush=True)
    items = []
    try:
        with cf.ThreadPoolExecutor(4) as pool:
            baselines = [pool.submit(run_baseline, i) for i in ideas]
            with cf.ThreadPoolExecutor(PARALLEL) as deliberations:
                runs = [deliberations.submit(run_deliberation, i) for i in ideas]
                for idea, rf, bf in zip(ideas, runs, baselines):
                    items.append({"idea": idea, "deliberation": rf.result(), "baseline": bf.result()})
                    print(f"  done: {idea[:50]}... ({items[-1]['deliberation']['run_id']}, {items[-1]['deliberation']['seconds']} s)", flush=True)
    finally:
        http("POST", f"{API}/api/settings/reset", {})
        print("deliberation settings reset to the repo defaults", flush=True)
    if BLIND:
        return write_blind(items, stamp)
    print(f"grading with {JUDGE}...", flush=True)
    with cf.ThreadPoolExecutor(5) as pool:
        futs = {pool.submit(judge, it["idea"], it["deliberation"]["text"], it["baseline"]["text"]): it for it in items}
        for f in cf.as_completed(futs):
            try:
                futs[f]["grade"] = f.result()
            except Exception as ex:
                print(f"  grading failed for one idea: {ex}", flush=True)
    res = {"base_model": BASE_MODEL, "judge": JUDGE, "mode": MODE, "baseline_prompt": BASELINE_PROMPT,
           "finished_at": datetime.now().isoformat(timespec="seconds"), "items": items}
    res["summary"] = summarize(items)
    jpath, hpath = os.path.join(OUT, f"{stamp}.json"), os.path.join(OUT, f"{stamp}.html")
    json.dump(res, open(jpath, "w"), indent=2, ensure_ascii=False)
    write_html(res, hpath)
    S = res["summary"]
    print(f"\njudge preferred the deliberation for {S['deliberation_wins']}/{S['graded']} ideas")
    for k in METRICS:
        print(f"  {k:<14} deliberation {S['deliberation'][k]:<5}  baseline {S['baseline'][k]}")
    print(f"\n{os.path.abspath(hpath)}")


if __name__ == "__main__":
    KEY = _key()
    REUSE_AFTER = os.environ.get("REUSE_AFTER", "")
    MODE = os.environ.get("MODE", "quick")
    PARALLEL = int(os.environ.get("PARALLEL", "1"))
    BLIND = "--blind" in sys.argv
    sys.argv = [a for a in sys.argv if a != "--blind"]
    if len(sys.argv) == 3 and sys.argv[1] == "--reformat":
        reformat(sys.argv[2])
    else:
        main()
