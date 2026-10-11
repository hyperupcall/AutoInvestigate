# AutoInvestigate

| Folder | What | Run |
|---|---|---|
| `website/frontend/` | the three-column app (no build step) | served by the backend at http://localhost:8090/, or `website/frontend/run.sh` |
| `website/` | Part 2, idea evaluation: 13 agents on AGNTCY/SLIM, models via OpenRouter | `cd website && ./setup.sh` (see `website/README.md`) |
| `artifactfactory/` | Part 3, idea execution: turns an idea into artifacts (the frontend's column 3) | `./run.sh` |
| `evalreport/` | report viewer | see the folder |

Quick start for the evaluation backend: install Docker, get an OpenRouter key, then `cd website && ./setup.sh` and
open http://localhost:8090/.

---

# Outshift Research Intelligence

A runnable Streamlit MVP for specialist emerging-technology analysis with Business, Venture Capital, and Technical perspectives, an independent critic, and a general-purpose baseline comparison.

## Requirements
- Python 3.10+
- An OpenRouter API key with access to the model you select

## Run everything with Docker Compose

A single `docker-compose.yml` at the repo root builds and starts every service:

| Service | Host URL | What it is |
| --- | --- | --- |
| `frontend` | http://localhost:8000 | Static three-column workspace (no build step) |
| `artifactfactory` | http://localhost:8080 | Artifact Factory REST API (idea → plan → artifacts) — column 3 |
| `web` (+ `slim`, `agent_host`) | http://localhost:8090 | Evaluation backend (multi-agent deliberation) — column 2 |
| `evalreport` | http://localhost:8501 | Streamlit "Outshift Research Intelligence" app |

```bash
cp .env.example .env      # then set OPENROUTER_API_KEY (and OPENAI_API_KEY for evalreport)
docker compose up --build
```

Everything runs on a **single OpenRouter key**. The root `.env` holds one
`OPENROUTER_API_KEY`, and every service reads that one file (`website/` and
`evalreport/`). The evaluation backend also needs a
`SLIM_SHARED_SECRET`; `cd website && ./setup.sh` writes both for you.

Then open http://localhost:8000 (frontend). The evaluation backend also serves the
same frontend at http://localhost:8090. Generated artifacts and daemon state persist
to `./_artifacts` and `./_artifactfactory-data` on the host. Stop with `docker compose down`.

Each service also has its own Dockerfile (`artifactfactory/`, `website/frontend/`,
`website/`, `evalreport/`) if you want to build or run one on its own.

### Permission errors

Docker creates a bind-mount source directory as `root` when it does not already exist,
so a container running as you cannot write to it. You then see errors like
`PermissionError: [Errno 13] Permission denied: 'logs/runs'` or
`sqlite3.OperationalError: unable to open database file`. The services fix this on
startup — their entrypoint chowns the mounted dirs (`logs`, `website/data`,
`website/council_results`, `_artifacts`, `_artifactfactory-data`, `_ideation-data`) to
`HOST_UID:HOST_GID` and then drops to that user — so a rebuild repairs it:

```bash
docker compose up -d --build
```

To repair the directories without rebuilding, run the helper script:

```bash
./fix-permissions.sh            # create + own every mounted directory
./fix-permissions.sh --restart  # ...and rebuild + restart the services
```

## Run on macOS/Linux
```bash
cd outshift_research_intelligence
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
# OPENROUTER_API_KEY is read from the root .env (../.env); or export it here:
export OPENROUTER_API_KEY="sk-or-..."
streamlit run app.py
```

If `streamlit: command not found`, use:
```bash
python -m streamlit run app.py
```

## How it works
- Business evaluator: customer pain, market, willingness to pay, strategic fit, adoption friction (30% total decision weight).
- Venture Capital evaluator: upside, timing, moat, capital efficiency, growth, risk-adjusted return (25%).
- Technical evaluator: feasibility, architecture, performance, security, prototype speed, operations (45%).
- Independent critic: challenges assumptions and proposes a measurable next experiment.
- Baseline: a single general-purpose analysis of the same research objective.
- Export: specialist report as JSON and comparison as CSV.

## Important limitations
This is a specialist agent workflow using an existing language model API, not a newly trained foundation model. It does not guarantee better performance than ChatGPT. The built-in comparison dimensions are only rough heuristics and are not an objective benchmark. To substantiate a performance claim, evaluate both systems on a fixed test set with blind human scoring, factual verification, and repeated trials. The current MVP does not perform web retrieval or verify citations automatically.
