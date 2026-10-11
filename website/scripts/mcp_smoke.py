"""Smoke-test the MCP servers: connect to each catalog server, list its tools, and report
   which are reachable and how many tools each exposes. Uses the real settings and the
   SMITH_API_KEY from the root .env. Read-only: it lists tools but never calls them.

   uv run --no-project --python 3.13 --with httpx==0.28.1 python -m scripts.mcp_smoke [server_id ...]

   With no arguments it checks every server in MCP_CATALOG; pass ids (e.g. arxiv crossref)
   to check a subset."""
import asyncio
import os
import sys

from deliberation import settings
from deliberation.defaults import MCP_CATALOG
from deliberation.mcp import MCPSession


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


async def check(srv: dict, key: str, timeout: float) -> tuple[str, str, int, str]:
    """Return (id, status, tool_count, detail) for one server."""
    try:
        async with MCPSession(srv["url"], key, timeout) as sess:
            names = [t.get("name", "?") for t in sess.tools]
            detail = ", ".join(names[:6]) + (" …" if len(names) > 6 else "")
            return srv["id"], "ok", len(names), detail
    except Exception as e:
        return srv["id"], "FAIL", 0, f"{type(e).__name__}: {e}"[:120]


async def main():
    load_env()
    s = settings.load()
    key = settings.mcp_key(s)
    timeout = float((s.get("mcp") or {}).get("timeout_seconds", 20))
    if not key:
        print("no SMITH_API_KEY in the environment or settings; hosted servers will likely reject the call")

    wanted = set(sys.argv[1:])
    servers = [m for m in MCP_CATALOG if not wanted or m["id"] in wanted]
    if not servers:
        print(f"no catalog servers match {sorted(wanted)}")
        return

    sem = asyncio.Semaphore(8)  # be gentle with the hosted endpoints

    async def guarded(srv):
        async with sem:
            return await check(srv, key, timeout)

    res = await asyncio.gather(*[guarded(srv) for srv in servers])
    for sid, status, count, detail in res:
        print(f"{status:4s} {sid:22s} {count:3d} tools  {detail}")
    ok = sum(r[1] == "ok" for r in res)
    print(f"\n{ok}/{len(res)} reachable; {sum(r[2] for r in res)} tools total")


if __name__ == "__main__":
    asyncio.run(main())