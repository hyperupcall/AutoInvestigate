# Evaluation backend (Part 2: idea evaluation over AGNTCY)

Give it one idea as a string. Three groups of AI agents evaluate it and reach a verdict. Every agent is its own
**AGNTCY/SLIM** endpoint (`deliberation/agents/<id>`), and every model call goes through **OpenRouter**.

| Group | Default members | Style |
|---|---|---|
| Professional Research Group | Feasibility Scientist, Systems Architect, AI Systems Researcher, Critical Reviewer | aims for a shared view |
| Private Equity and Business | Technical Risk, Market and Revenue, Competitive Strategy, Horizon and Returns partners | aims for a shared view |
| Market Reaction | Power User, Enterprise Decision-Maker, Skeptical Critic, Startup Builder, Free-Tier Maximizer (+11 archetypes) | not expected to agree |

## Setup (one command)

Needs Docker (Desktop on Mac/Windows, Engine + compose plugin on Linux) and an OpenRouter API key.

```bash
cd website
./setup.sh
```

It checks Docker, writes the single root `.env` (`../.env`; asks for the OpenRouter key once, generates the SLIM
secret), checks the key and ports, builds and starts the SLIM bus + one agent process per evaluator + the web app,
waits until every agent is registered on SLIM, then sends one tiny call to each model (well under $0.001). Run it
again any time. All keys and settings come from that one file (see `../.env.example`).

Then open:

| URL | What |
|---|---|
| http://localhost:8090/ | the AutoInvestigate frontend (`frontend/`), with real evaluations |
| http://localhost:8090/live | three live chat columns, stage tracker, replay (good for demos) |

`../run.sh` (frontend on port 8000) also works: the frontend finds this backend at `localhost:8090`.

Stop: `docker compose down` (from the repo root). Logs: `docker compose logs -f agent_host web`.

## Quick and Deep mode

| | Quick (default) | Deep |
|---|---|---|
| Time | about 75 seconds | about 7 minutes |
| Discussion | everyone speaks at once each round; round 2 answers round 1 | timed round-robin, everyone hears everything |
| Write-ups | short (scores, verdict, 3 reasons) | full role format and evaluation template |
| Slow members | skipped after 18-20 s (logged) | retried |
| Web search | none (arXiv list only) | `:online` models search the web |
| Cost | about $0.03 | about $0.15 |

Switch in the frontend's settings popup, or per run: `POST /api/evaluate {"idea": "...", "overrides": {"mode": "deep"}}`.

## arXiv sources

The research and private-equity groups get 6-8 relevant arXiv papers (title, authors, year, link, abstract) and cite
them as `[arXiv:ID]`. A cheap model writes 3 keyword queries, the papers come from OpenAlex restricted to arXiv
(the arXiv API itself rate-limits shared networks hard, so it is only the fallback), a cheap model keeps the most
relevant, and results are cached per idea in `data/sources_cache.json`. The report's `sources` section lists the
papers, who cited each, and any citation of an id that was not in the list. Toggle per group in the settings popup.

## MCP servers (agents can use tools)

Each agent carries `mcp_servers`: ids from `MCP_CATALOG` in `deliberation/defaults.py`, curated from
[Smithery](https://smithery.ai/servers) across three categories — Academic Research, Finance and Reasoning. The
mapping is by role: researchers get arXiv / Semantic Scholar / Crossref / citation checkers; the private-equity
partners get finance data and reasoning servers; the market archetypes get calculators and decision servers.

During the `evaluate` / `cross_review` stages (deep mode) the agent host connects to the agent's servers over
Streamable HTTP (`deliberation/mcp.py`), lists their tools and offers them to the model via OpenRouter tool-calling
(`deliberation/openrouter.py`, `chat_with_tools`). Tool names are prefixed with the server id (`arxiv__search`) so two
servers can expose the same name. It is bounded by `mcp.max_tool_calls` and **fail-safe**: if a server is down or a
call fails, the agent answers without tools. The Smithery key comes from `SMITH_API_KEY` in the root `.env`
(see `../.env.example`); a stored `mcp.api_key` is only a fallback. Other settings: `mcp.enabled`,
`mcp.timeout_seconds`, `mcp.max_tool_calls`. The frontend shows the same catalog in the Settings popup.

Add or remove a server for any agent in the settings popup: each agent row has an "MCP servers" line with a chip
per server (✕ to remove) and a dropdown to add another. Save, and the next run uses it.

## What happens in an evaluation

0. A reality check runs first: one outside call (`prompts/system/reality_check.md`, stage `reality_check`) judges
   whether the idea makes sense in the real world at all and returns `grounded` / `questionable` / `nonsense` with a
   category, a summary, real-world blockers and shaky assumptions. It is advisory (a failed call does not stop the
   run) and is fed into the stop-or-go and final prompts, so a `nonsense` idea cannot get a plain "Go".
1. Each group discusses the idea for a set time (round-robin, everyone hears everything).
2. Every member writes an evaluation in its own format (`prompts/<group>/<agent>.md`).
3. A summarizer writes each group's pros and cons.
4. Second discussion after every group read every group's summary.
5. Re-evaluation with the template (`prompts/system/evaluation_template.md`): pros, cons, scores.
6. Summaries again.
7. Stop or go. This decides whether to keep deliberating, not whether the idea is good: stop, or run one
   extra round and then always finish. If a consensus across groups is not feasible, the disagreement is kept.
8. The final report (`prompts/system/final.md`, stage `final`): the comprehensive verdict written for the person
   who submitted the idea. It is fed the raw material (each group's latest evaluations in full, the latest
   discussion, the arXiv papers, the stop-or-go decision and the reality check), not just the summaries, and
   returns a structured report: headline, recommendation, a multi-paragraph executive summary, the idea as
   evaluated, the case for and against, an ordered action plan (timeframe/cost/owner), implementation options
   (each with how it would be validated and the result that counts as success) and a validation note, kill
   criteria, risks with mitigations, open questions, and what would change the verdict, plus a per-group verdict
   with findings and scores. Then a disagreement analysis (quotes are checked word for word) and the JSON report in
   `council_results/<run_id>.json` (the reality check lands in its `reality_check` field).

The orchestrator only opens SLIM groups, relays commands and records events; it decides nothing.

## Routes

| Route | |
|---|---|
| `POST /api/evaluate` `{"idea": "...", "overrides": {"deliberation_seconds": 20, "summarizer_model": "...", "group_ids": ["research"]}}` | start (up to 3 at once) |
| `POST /api/stop` `{"run_id": "..."}` | cancel |
| `GET /api/status`, `GET /api/runs` | what is running, past runs |
| `GET /api/ui/runs/<id>/events?since=N` | live events in the frontend's shape (`orchestrator/compat.py`) |
| `GET /api/runs/<id>/report` | the report, `schema/evaluation-report.schema.json` |
| `GET /api/runs/<id>/events?since=N` | raw event log |
| `GET /api/results` | index of exported reports |
| `GET`/`PUT /api/settings`, `POST /api/settings/reset` | settings (keys masked) |
| `GET /api/models` | OpenRouter models with prices |

Examples of finished reports: `examples/`.

## Layout

```
setup.sh, Dockerfile, Makefile   (the services are defined in the root ../docker-compose.yml)
frontend/       the three-column app (static, no build step)
deliberation/   settings, prompts loader, OpenRouter client, MCP client, report builder, SLIM glue
agent_host/     one process per agent (each a SLIM endpoint)
orchestrator/   pipeline, run, SLIM bus client, web routes, frontend compatibility, live view (static/)
prompts/        every agent's role and the system prompts (markdown, editable, mounted live)
schema/         evaluation-report.schema.json
examples/       two finished reports
tests/          `make test` (needs uv)
```

## Cost

Quick: about $0.03 per evaluation. Deep: about $0.10 to $0.15. Each run has a cost cap (default $1).
