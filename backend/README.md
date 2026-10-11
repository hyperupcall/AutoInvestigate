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

## What happens in an evaluation

1. Each group discusses the idea for a set time (round-robin, everyone hears everything).
2. Every member writes an evaluation in its own format (`prompts/<group>/<agent>.md`).
3. A summarizer writes each group's pros and cons.
4. Second discussion after every group read every group's summary.
5. Re-evaluation with the template (`prompts/system/evaluation_template.md`): pros, cons, scores.
6. Summaries again.
7. Stop or go. This decides whether to keep deliberating, not whether the idea is good: stop, or run one
   extra round and then always finish. If a consensus across groups is not feasible, the disagreement is kept.
8. Final conclusions per group, written for a person. Then a disagreement analysis (quotes are checked word for
   word) and the JSON report in `results/<run_id>.json`.

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

About $0.10 to $0.15 per evaluation with 60-second discussions; each run has a cost cap (default $1).
