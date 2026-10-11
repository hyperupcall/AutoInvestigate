# Evaluation backend (Part 2: idea evaluation over AGNTCY)

Give it one idea as a string. Three groups of AI agents evaluate it and reach a verdict. Every agent is its own
**AGNTCY/SLIM** endpoint (`council/agents/<id>`), and every model call goes through **OpenRouter**.

| Group | Default members | Style |
|---|---|---|
| Professional Research Group | Feasibility Scientist, Systems Architect, AI Systems Researcher, Critical Reviewer | aims for a shared view |
| Private Equity and Business | Technical Risk, Market and Revenue, Competitive Strategy, Horizon and Returns partners | aims for a shared view |
| Market Reaction | Power User, Enterprise Decision-Maker, Skeptical Critic, Startup Builder, Free-Tier Maximizer (+11 archetypes) | not expected to agree |

## Setup (one command)

Needs Docker (Desktop on Mac/Windows, Engine + compose plugin on Linux) and an OpenRouter API key.

```bash
cd backend
./setup.sh
```

It checks Docker, writes the single root `.env` (`../.env`; asks for the OpenRouter key once, generates the SLIM
secret), checks the key and ports, builds and starts the SLIM bus + one agent process per evaluator + the web app,
waits until every agent is registered on SLIM, then sends one tiny call to each model (well under $0.001). Run it
again any time. All keys and settings come from that one file (see `../.env.example`).

Then open:

| URL | What |
|---|---|
| http://localhost:8090/ | the AutoInvestigate frontend (`../frontend`), with real evaluations |
| http://localhost:8090/live | three live chat columns, stage tracker, replay (good for demos) |
| http://localhost:8090/settings | models, keys, agents per group, deliberation time, cost cap |

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

Switch in /settings, in the frontend's settings popup, or per run: `POST /api/evaluate {"idea": "...", "overrides": {"mode": "deep"}}`.

## arXiv sources

The research and private-equity groups get 6-8 relevant arXiv papers (title, authors, year, link, abstract) and cite
them as `[arXiv:ID]`. A cheap model writes 3 keyword queries, the papers come from OpenAlex restricted to arXiv
(the arXiv API itself rate-limits shared networks hard, so it is only the fallback), a cheap model keeps the most
relevant, and results are cached per idea in `data/sources_cache.json`. The report's `sources` section lists the
papers, who cited each, and any citation of an id that was not in the list. Toggle per group in /settings.

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
8. Final conclusions per group, written for a person. Then a disagreement analysis (quotes are checked word for
   word) and the JSON report in `results/<run_id>.json` (the reality check lands in its `reality_check` field).

The orchestrator only opens SLIM groups, relays commands and records events; it decides nothing.

## Routes

| Route | |
|---|---|
| `POST /api/evaluate` `{"idea": "...", "overrides": {"deliberation_seconds": 20, "summarizer_model": "..."}}` | start (up to 3 at once) |
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
council/        settings, prompts loader, OpenRouter client, report builder, SLIM glue
agent_host/     one process per agent (each a SLIM endpoint)
orchestrator/   pipeline, run, SLIM bus client, web routes, frontend compatibility, live view (static/)
prompts/        every agent's role and the system prompts (markdown, editable, mounted live)
schema/         evaluation-report.schema.json
examples/       two finished reports
tests/          `make test` (needs uv)
legacy/         the earlier 4-agent negotiation demo (runs on its own)
```

## Cost

Quick: about $0.03 per evaluation. Deep: about $0.10 to $0.15. Each run has a cost cap (default $1).
