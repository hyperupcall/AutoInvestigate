"""One tiny real call per configured model, using the real settings. Costs a fraction of a cent.
   uv run --no-project --python 3.13 --with httpx==0.28.1 python -m scripts.live_smoke"""
import asyncio
import os

from deliberation import openrouter as orr
from deliberation import settings


def load_env():
    # Inside the container the vars are injected by compose; locally, read the
    # single root .env (../.env) or a backend-local .env if one exists.
    for path in (".env", "../.env"):
        if not os.path.exists(path):
            continue
        for line in open(path):
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)


async def main():
    load_env()
    s = settings.load()
    jobs = []
    for g in s["groups"]:
        for a in g["agents"]:
            effort = a.get("reasoning_effort") or s["reasoning_effort"]["deliberate"]
            jobs.append((f"{g['id']}/{a['id']}", a["model"], settings.resolve_key(), effort))
    for st in ("summarizer", "judge"):
        c = s["stages"][st]
        jobs.append((f"stage/{st}", c["model"], settings.resolve_key(), s["reasoning_effort"]["judge"]))
    budget = orr.RunBudget(0.25)

    async def one(name, model, key, effort):
        try:
            r = await orr.chat(model, [{"role": "user", "content": "In one sentence, name one risk of launching a new network-security product."}],
                               key, max_tokens=120, reasoning_effort=effort, web_results=1, budget=budget)
            return name, model, "ok", r.cost, r.text.replace("\n", " ")[:70]
        except Exception as e:
            return name, model, "FAIL", 0, str(e)[:100]
    res = await asyncio.gather(*[one(*j) for j in jobs])
    for name, model, st, cost, txt in res:
        print(f"{st:4s} {name:40s} {model:38s} ${cost:.5f} {txt}")
    print(f"\ntotal ${budget.spent:.5f} over {budget.calls} calls; failures: {sum(r[2] != 'ok' for r in res)}")


if __name__ == "__main__":
    asyncio.run(main())
