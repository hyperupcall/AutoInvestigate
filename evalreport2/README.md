# evalreport2 — Outshift Research Intelligence (CLI)

A streamlined take on `evalreport/`. Same evaluation logic, different interface:

- **Runs in the terminal.** No Streamlit, no server. It prints progress as it works.
- **Writes one self-contained `index.html`** with all of the data inlined (CSS + JSON),
  plus Chart.js from a CDN for the charts.
- Styling matches the `website/frontend/` directory: light mode, system font, thin borders,
  HTML5 named colors only.

## What it evaluates

Three weighted specialist perspectives, each with named criteria and 1–10 scores:

| Perspective | Weight |
| --- | --- |
| Business | 30% |
| Venture Capital | 25% |
| Technical | 45% |

Rubric weights are enforced locally (not trusted from the model). An independent
red-team critic then reviews the three analyses and recommends a decision
(`Reject` / `Research more` / `Prototype` / `Advance`). With `--compare`, a
general-purpose single-pass baseline runs too, and a heuristic dimension comparison
is charted.

> This is an evaluation *system* built around an LLM API, not a trained model. It does
> not claim to beat ChatGPT without running the benchmark. The baseline comparison is
> rubric-based and explicitly not objective truth.

## Usage

```sh
# Default example idea
./run.sh

# Your own idea
./run.sh "Evaluate homomorphic encryption for privacy-preserving enterprise AI analytics"

# Also run the general-purpose baseline
./run.sh --compare "Some idea"

# Offline deterministic run — no API key needed (for testing the report)
./run.sh --demo "Some idea"

# Options
./run.sh --help
```

`run.sh` bootstraps a uv-managed `.venv` on first run and then uses it by default.

### Options

| Flag | Meaning |
| --- | --- |
| `--model ID` | Model id (default `meta-llama/llama-3.1-8b-instruct`). |
| `--out PATH` | Output HTML path (default `index.html`). |
| `--compare` | Also run the general-purpose baseline. |
| `--demo` | Offline deterministic run; no API key required. |
| `--open` | Open the report in a browser when done. |
| `--idea-file PATH` | Read the idea text from a file. |

## Configuration

The API key comes from the single root `.env` (`../.env`): `OPENROUTER_API_KEY`
(falling back to `OPENAI_API_KEY`). All calls go through OpenRouter.

The model is a global in `evaluate.py` (`MODEL = "meta-llama/llama-3.1-8b-instruct"`,
OpenRouter's "Meta: Llama 3.1 8B Instruct") — it is **not** read from `.env`. Override
it per-run with `--model`.

## Output

`index.html` contains: the idea, combined score and a radar chart of the three
perspectives, one card per perspective (summary, criteria table, strengths/risks,
unknowns, validation experiment), the critic's recommendation, the optional baseline
comparison, and a collapsible raw JSON view.

## Files

| File | Purpose |
| --- | --- |
| `evaluate.py` | CLI entry point: evaluation logic + HTML generator. |
| `run.sh` | uv-based launcher. |
| `requirements.txt` | `openai`, `python-dotenv`. |
