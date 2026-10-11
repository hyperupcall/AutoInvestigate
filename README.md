# Outshift Research Intelligence

A runnable Streamlit MVP for specialist emerging-technology analysis with Business, Venture Capital, and Technical perspectives, an independent critic, and a general-purpose baseline comparison.

## Requirements
- Python 3.10+
- An OpenAI API key with access to the model you select

## Run everything with Docker Compose

A single `docker-compose.yml` at the repo root builds and starts every service:

| Service | Host URL | What it is |
| --- | --- | --- |
| `artifactfactory` | http://localhost:8080 | Artifact Factory REST API (idea → plan → artifacts) |
| `frontend` | http://localhost:8000 | Static three-column workspace (no build step) |
| `evalreport` | http://localhost:8501 | Streamlit "Outshift Research Intelligence" app |

```bash
cp .env.example .env      # then set OPENAI_API_KEY (used by evalreport)
docker compose up --build
```

Then open http://localhost:8000 (frontend) and http://localhost:8501 (evalreport).
Generated artifacts and daemon state persist to `./_artifacts` and
`./_artifactfactory-data` on the host. Stop with `docker compose down`.

Each service also has its own Dockerfile (`artifactfactory/`, `frontend/`,
`evalreport/`) if you want to build or run one on its own.

## Run on macOS/Linux
```bash
cd outshift_research_intelligence
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
export OPENAI_API_KEY="your-api-key"
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
