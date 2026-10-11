"""Write council_results/<run_id>.json (and council_results/index.json) from a run's event log.

  python -m orchestrator.export 20261011-014311-b2e9      # one run (adds the disagreement analysis if missing)
  python -m orchestrator.export --all --no-analysis        # every finished run, deterministic parts only"""
import argparse
import asyncio
import json
import os
from datetime import datetime, timezone

from council import report, settings
from council.openrouter import RunBudget

RESULTS = "council_results"
RUNS = "logs/runs"


def events_of(run_id: str) -> list[dict]:
    with open(os.path.join(RUNS, f"{run_id}.jsonl")) as f:
        return [json.loads(l) for l in f if l.strip()]


def write(run_id: str) -> str:
    rep = report.build(events_of(run_id))
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, f"{run_id}.json")
    with open(path, "w") as f:
        json.dump(rep, f, indent=2, ensure_ascii=False)
    write_index()
    return path


def write_index() -> None:
    rows = []
    for name in sorted(os.listdir(RESULTS), reverse=True):
        if not name.endswith(".json") or name == "index.json":
            continue
        with open(os.path.join(RESULTS, name)) as f:
            r = json.load(f)
        rows.append({"id": r["run"]["id"], "idea": r["run"]["idea"], "status": r["run"]["status"],
                     "started_at": r["run"]["started_at"], "headline": (r.get("verdict") or {}).get("headline"),
                     "stop_go_decision": r["pipeline"]["stop_go_decision"], "file": name})
    with open(os.path.join(RESULTS, "index.json"), "w") as f:
        json.dump({"schema_version": report.SCHEMA_VERSION, "runs": rows}, f, indent=2, ensure_ascii=False)


async def add_analysis(run_id: str) -> None:
    """Backfill the analysis event for a run that finished before analysis existed."""
    from orchestrator.analysis import analyze
    ev = events_of(run_id)
    if any(e["kind"] == "analysis" for e in ev):
        return
    s = settings.load()
    result = await analyze(ev, s, RunBudget(0.25))
    with open(os.path.join(RUNS, f"{run_id}.jsonl"), "a") as f:
        f.write(json.dumps({"t": datetime.now(timezone.utc).isoformat(), "kind": "analysis",
                            "spent": ev[-1].get("spent", 0), **result}) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-analysis", action="store_true")
    a = ap.parse_args()
    ids = [n[:-6] for n in sorted(os.listdir(RUNS)) if n.endswith(".jsonl")] if a.all else [a.run_id]
    for run_id in ids:
        ev = events_of(run_id)
        if not any(e["kind"] == "run_end" for e in ev):
            continue
        if not a.no_analysis:
            asyncio.run(add_analysis(run_id))
        print("wrote", write(run_id))


if __name__ == "__main__":
    main()
