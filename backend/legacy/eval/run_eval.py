"""Council vs single-agent baseline. Only this package may read `planted`.

  python -m eval.run_eval --council 5 --baseline 20
"""
import argparse
import asyncio
import json
import os
import re
import shutil
from collections import Counter

from agents.common.schema import AGENT_NAMES
from baseline.agent import decide
from moderator import main as mod

EVENTS = os.getenv("EVENTS_LOG", "logs/eval_events.jsonl")
OUT = "eval"


def load_truth():
    ideas = json.load(open("data/ideas.json"))
    planted = {i["id"] for i in ideas if i.get("planted")}  # eval-only read
    truth = json.load(open(os.path.join(OUT, "planted_truth.json")))
    traps = {k for k, v in truth.items() if "trap" in v and k in planted}
    gems = {k for k, v in truth.items() if "gem" in v and k in planted}
    return traps, gems


def priorities():
    out = {}
    for a in AGENT_NAMES:
        line = next(l for l in open(f"data/private_notes/{a}.md") if "YOUR PRIORITIES" in l)
        out[a] = set(re.findall(r"idea_\d+", line))
    return out


def summarize(runs, traps, gems, prios):
    ok = [r for r in runs if r["ideas"]]
    n = len(runs)
    sat = [[len(set(r["ideas"]) & prios[a]) / 3 for a in AGENT_NAMES] for r in ok]
    sets = Counter(tuple(sorted(r["ideas"])) for r in ok)
    return {
        "runs": n,
        "consensus_rate": round(len(ok) / n, 2) if n else 0,
        "trap_rate": round(sum(bool(set(r["ideas"]) & traps) for r in ok) / len(ok), 2) if ok else None,
        "gem_rate": round(sum(bool(set(r["ideas"]) & gems) for r in ok) / len(ok), 2) if ok else None,
        "avg_agent_satisfaction": round(sum(map(sum, sat)) / (4 * len(sat)), 2) if sat else None,
        "worst_off_satisfaction": round(sum(min(s) for s in sat) / len(sat), 2) if sat else None,
        "everyone_got_a_priority": round(sum(min(s) > 0 for s in sat) / len(sat), 2) if sat else None,
        "distinct_outcomes": len(sets),
        "most_common_outcome": [list(k) + [f"{v}/{len(ok)}"] for k, v in sets.most_common(1)][0] if sets else None,
    }


async def run_council(n):
    os.makedirs(os.path.join(OUT, "runs"), exist_ok=True)
    runs = []
    for i in range(n):
        open(EVENTS, "w").close()
        try:
            await mod.negotiate(pace=0, info_round=2)
            last = dict(mod.LAST)
        except Exception as e:  # keep going; count as failed run
            print("run failed:", e)
            runs.append({"ideas": [], "status": "error"})
            continue
        ev = [json.loads(l) for l in open(EVENTS) if l.strip()]
        shutil.copy(EVENTS, os.path.join(OUT, "runs", f"council_{i}.jsonl"))
        opening = {tuple(sorted(e["idea_ids"])) for e in ev
                   if e.get("kind") == "agent_message" and e["action"] == "propose" and e["round"] == 0}
        runs.append({"ideas": last["idea_ids"] if last["status"] == "consensus" else [],
                     "status": last["status"], "rounds": last["rounds"],
                     "consulted": any(e.get("kind") == "invite" for e in ev),
                     "objections": sum(e.get("action") == "object" for e in ev if e.get("kind") == "agent_message"),
                     "specialist": any(e.get("expert") == "specialist_on_demand" for e in ev if e.get("kind") == "invite"),
                     "opening_distinct_sets": len(opening)})
        print(f"[council {i + 1}/{n}] {last['status']} {last['idea_ids']} rounds={last['rounds']}")
    return runs


async def run_baseline(m):
    runs = []
    for k in range(0, m, 5):
        res = await asyncio.gather(*[decide() for _ in range(min(5, m - k))], return_exceptions=True)
        for r in res:
            runs.append({"ideas": r["idea_ids"], "status": "decision"} if isinstance(r, dict)
                        else {"ideas": [], "status": "error"})
    print(f"[baseline] {len(runs)} runs")
    return runs


async def main(nc, nb):
    traps, gems = load_truth()
    prios = priorities()
    council = await run_council(nc) if nc else []
    base = await run_baseline(nb) if nb else []
    cs, bs = summarize(council, traps, gems, prios), summarize(base, traps, gems, prios)
    if council:
        ok = [r for r in council if r.get("status") != "error"]
        cs["escalation_rate"] = round(sum(r["status"] == "escalate" for r in ok) / max(len(ok), 1), 2)
        cs["avg_rounds_to_decide"] = round(sum(r.get("rounds", 0) for r in ok) / max(len(ok), 1), 1)
        cs["consulted_expert_rate"] = round(sum(r.get("consulted", False) for r in ok) / max(len(ok), 1), 2)
        cs["avg_objections_per_run"] = round(sum(r.get("objections", 0) for r in ok) / max(len(ok), 1), 1)
        cs["specialist_used_rate"] = round(sum(r.get("specialist", False) for r in ok) / max(len(ok), 1), 2)
        cs["avg_distinct_opening_sets"] = round(sum(r.get("opening_distinct_sets", 0) for r in ok) / max(len(ok), 1), 1)
        cs["news_reaction_rate"] = round(sum("idea_01" not in r["ideas"] for r in ok if r["ideas"]) / max(sum(bool(r["ideas"]) for r in ok), 1), 2)
    result = {"traps": sorted(traps), "gems": sorted(gems), "priorities": {a: sorted(p) for a, p in prios.items()},
              "council": cs, "baseline": bs,
              "council_runs": [{k: v for k, v in r.items()} for r in council],
              "baseline_runs": [r["ideas"] for r in base]}
    json.dump(result, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    print(json.dumps({"council": cs, "baseline": bs}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--council", type=int, default=5)
    ap.add_argument("--baseline", type=int, default=20)
    a = ap.parse_args()
    asyncio.run(main(a.council, a.baseline))
