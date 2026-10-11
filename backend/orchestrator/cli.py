"""Run the stages built so far from the command line.
   docker compose --profile run run --rm orchestrator python -m orchestrator.cli "the idea" --seconds 30"""
import argparse
import asyncio

from orchestrator.run import Run


async def main(idea: str, seconds: float | None, only: list[str] | None) -> None:
    run = Run(idea)
    await run.start()
    groups = [g for g in run.s["groups"] if not only or g["id"] in only]
    secs = seconds or run.s["deliberation_seconds"]
    print(f"run {run.id}: {len(groups)} groups deliberating for {secs}s each (round-robin)\n")
    results = await asyncio.gather(*[run.deliberate(g, secs) for g in groups])
    for g, tr in zip(groups, results):
        print(f"=== {g['name']} ({len(tr)} turns)")
        names = {a["id"]: a["name"] for a in g["agents"]}
        for t in tr:
            print(f"[{names[t['agent']]}] {t['text']}\n")
    print(f"cost ${run.budget.spent:.4f} over {run.budget.calls} calls; by model:")
    for m, c in sorted(run.budget.by_model.items(), key=lambda x: -x[1]):
        print(f"   {m:42s} ${c:.5f}")
    print(f"log: {run.path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("idea")
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    asyncio.run(main(a.idea, a.seconds, a.only))
