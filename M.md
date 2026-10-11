# MCP server setup — self-hosting analysis & hookup notes

Notes on the current MCP server setup in this repo: what it is, whether the servers
can be self-hosted, and how to hook up the Smithery API key.

## 1. What the current setup is

Every server in the catalog is **remote and hosted by Smithery**. The `url` field is
the only thing that decides where the client connects, and they are all
`https://server.smithery.ai/<owner>/<server>/mcp`.

- **Catalog (source of truth):** `website/deliberation/defaults.py` → `MCP_CATALOG`
  (mirrored for display in `website/frontend/js/mcp-servers.js`; the backend serves it
  in `/api/settings` as `mcp_catalog`).
- **Client:** `website/deliberation/mcp.py` — a ~170-line JSON-RPC 2.0 client
  (`MCPSession` / `MCPToolbox`) that does `initialize` → `tools/list` → `tools/call`.
  **Streamable HTTP only — there is no stdio transport.**
- **Auth:** the key from `SMITH_API_KEY` in the root `.env`
  (`website/deliberation/settings.py` → `mcp_key()`), with a stored `mcp.api_key` as
  fallback. Smithery's hosted endpoints take it as an **`?api_key=` query parameter**
  (a `Bearer` header alone is rejected with `401 invalid_token`); see §6.
- **Call site:** `website/agent_host/executor.py` (`_answer`, L93-117). MCP is used
  only when the agent has `mcp_servers`, `mcp.enabled` is true, the run is **not**
  quick mode, and the stage is `evaluate` / `cross_review`.
- **Behavior:** fail-safe — a server that is down just contributes no tools and the
  agent answers without them.
- **Deployment:** `agent_host` and `web` run as containers (`docker-compose.yml`) and
  reach Smithery over the network.

## 2. Can the MCP servers be self-hosted?

**Yes, and the plumbing already supports it** — the client connects to whatever HTTP
URL is in the catalog, so self-hosting is essentially "point `url` at your own
endpoint." Two real constraints:

1. **HTTP-only client.** The normal way to run an MCP server locally is stdio
   (`npx` / `uvx`). `website/deliberation/mcp.py` cannot do that. So self-hosting means
   either:
   - running each server as an HTTP service (FastMCP's HTTP transport, or a bridge
     like `mcp-proxy` / `supergateway`) and pointing `url` at it, or
   - adding a stdio transport to the client (the `Server` / `MCPClient` abstraction
     in `website/MCP_IMPROVEMENTS.md` §5.1 already sketches this).
2. **You need the server's code.** The catalog splits cleanly:

| Group | Examples | Self-hostable? |
|---|---|---|
| Thin wrappers over **free public APIs** | arXiv, Crossref, OpenAlex, Semantic Scholar, PubMed, DataCite, CiteMe, citation checkers, calculators | **Yes, easily.** Upstream APIs are free/public; run an existing OSS MCP server or write a small one. |
| **Proprietary SaaS / vendor logic** | Thoughtbox, Flatland, PreReason, Invinoveritas, Decide Runtime, Quorum, mumo, SecureLend, Arcadia | **No** — it is the vendor's product. Only if they publish source. |

Docker-wise it is fine: self-hosted servers as compose services are reachable by
service name from `agent_host`.

## 3. Is self-hosting reasonable?

**Broadly, no — but a targeted subset, yes.**

- **Not worth it for the whole catalog.** 30+ servers to run, update, monitor, and
  key-manage is real ops overhead. Smithery gives one key and zero maintenance, and
  the fail-safe design means an outage degrades gracefully rather than breaking a
  run. For a hackathon demo, self-hosting everything trades a working setup for a lot
  of yak-shaving.
- **Reasonable for the academic subset.** The servers the agents lean on most (arXiv,
  Crossref, OpenAlex, Semantic Scholar, PubMed) are wrappers over free public APIs.
  Self-hosting just those is small, high-value work: it removes the Smithery key
  dependency and its rate limits, and makes demos deterministic / offline-friendly.
  You would own the (mostly free) upstream keys.
- **Reasonable if you have a specific driver:** no external key, offline/deterministic
  demos, latency, or Smithery-availability concerns. Otherwise it solves a problem you
  do not have.
- **Not reasonable for the proprietary reasoning/finance servers** — you do not have
  their code, so "self-host" is not an option there regardless.

**Caveat:** the client currently sends a Bearer token to *every* server. A self-hosted
server that does not expect auth would still receive the Smithery key header —
harmless for your own servers, but worth being deliberate about if you mix hosted and
self-hosted endpoints.

## 4. Hooking up the Smithery API key

- Put `SMITH_API_KEY=...` in the root `.env` (template: `.env.example`).
  `settings.mcp_key()` reads it; a stored `mcp.api_key` is only the fallback. The
  frontend Settings popup shows this as "set in .env (SMITH_API_KEY)" when the env
  supplies it.
- **Auth mechanism:** Smithery's hosted endpoints authenticate with an **`?api_key=`
  query parameter**, not a `Bearer` header. `MCPSession` now appends the key to the
  URL (`_request_url()` in `website/deliberation/mcp.py`) and keeps the `Bearer`
  header for servers that use it — both together are accepted.
- `mcp.enabled` must be `true`, and MCP only fires in **deep mode** for the
  `evaluate` / `cross_review` stages (`website/agent_host/executor.py` L96-99).
- **Gotcha:** `.env` is loaded at process start via `load_dotenv`, so after editing it
  you must restart the `agent_host` / `web` containers — unlike settings changes,
  which apply per-command without a restart.

## 5. Smoke test

`website/scripts/mcp_smoke.py` connects to each catalog server, lists its tools, and
reports which are reachable (read-only; it never calls a tool):

```
uv run --no-project --python 3.13 --with httpx==0.28.1 python -m scripts.mcp_smoke [server_id ...]
```

Run it after any catalog or auth change to confirm tools actually come back before
relying on them in a run.

## 6. Findings (smoke test, current catalog)

**28 / 42 servers reachable, 239 tools total.** The 14 failures fall into buckets:

| Status | Servers | Meaning |
|---|---|---|
| `404` | semantic-scholar, logic-verifier, decide-runtime, math-logic, gitwhy | Path wrong or server removed from Smithery. |
| `401` | consensus, wealthtools, unl, deepseek | Server needs its **own** upstream key configured in Smithery; the Smithery key alone is not enough. |
| `403` | academic-research, finance-mcp | Vendor (`nexgendata-apify`) requires config / paid access. |
| `410` | flatland | Gone. |
| `530` / `526` | thoughtbox, agent-dilemma | Server-side error. |

Because MCP is fail-safe, all of these simply contribute no tools — a run still
completes. But the dead entries are noise: consider pruning the `404`/`410` ids from
`MCP_CATALOG` (and the mirror in `website/frontend/js/mcp-servers.js`), and noting the
`401` servers as "needs its own key".

## 7. Possible next steps

- Prune dead catalog entries (see §6) and flag servers that need their own keys.
- Add stdio support to `website/deliberation/mcp.py` (or a small HTTP bridge) so
  standard `npx` / `uvx` MCP servers can be run locally.
- Split `MCP_CATALOG` so a subset (the academic servers) points at local endpoints.