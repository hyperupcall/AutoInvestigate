# AutoInvestigate

| Folder | What | Run |
|---|---|---|
| `frontend/` | the three-column app (no build step) | served by the backend at http://localhost:8090/, or `frontend/run.sh` |
| `backend/` | Part 2, idea evaluation: 13 agents on AGNTCY/SLIM, models via OpenRouter | `cd backend && ./setup.sh` (see `backend/README.md`) |
| `artifactfactory/` | artifact factory service | `./run.sh` |
| `evalreport/` | report viewer | see the folder |

Quick start for the evaluation backend: install Docker, get an OpenRouter key, then `cd backend && ./setup.sh` and
open http://localhost:8090/.

---

# Outshift Research Intelligence

A runnable Streamlit MVP for specialist emerging-technology analysis with Business, Venture Capital, and Technical perspectives, an independent critic, and a general-purpose baseline comparison.

## Requirements
- Python 3.10+
- An OpenAI API key with access to the model you select

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
