# DELIBERATION.md

Working notes on the **"council"** naming across the repository.

> Context: a search was requested for `"counsil"` (a typo). The intended term is
> **"council"** — the `website/council/` Python package and the "multi-agent council"
> concept. This document records where that term appears and what each use means.

---

## Search method

Case-insensitive recursive search, excluding the vendored virtualenv and the
unreadable settings file:

```sh
grep -rni "council" . \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude=settings.json
```

**Result: 178 matches across 30 files** (excluding `.venv`, `.results/`, and
`examples/`). The literal string `"counsil"` does **not** appear anywhere.

---

## Where "council" appears

### 1. The package itself — `website/council/`

The name is the Python package, referenced internally:

| File | What it is |
| --- | --- |
| `website/council/defaults.py` | `from council.prompts import ROOT, role_name` |
| `website/council/settings.py` | `from council.defaults import ...`, `from council.prompts import ROOT` |
| `website/council/report.py` | `from council.defaults import archetype_library`, `council/agents/<id>` endpoints |
| `website/council/slim.py` | `NAMESPACE, GROUP = "council", "agents"` — the AGNTCY/SLIM namespace is literally `"council"` |

### 2. Importers of the package

- `website/agent_host/executor.py` (8) — `from council import openrouter`, logger `"council.agent"`
- `website/agent_host/main.py` (2) — logger `"council.host"`
- `website/agent_host/single.py` (3) — `AgntcyFactory(f"council.{agent_id}")`
- `website/orchestrator/` — `analysis.py`, `bus.py`, `compat.py`, `export.py`, `pipeline.py`, `run.py`, `sources.py`, `web.py`
- `website/tests/test_core.py`, `website/tests/test_report.py`
- `website/scripts/live_smoke.py`

### 3. Config / build / docs

- `docker-compose.yml` (5) — `x-council: &council` anchor, `container_name: council-slim`
- `website/Dockerfile:6` — `COPY council ./council`
- `website/pyproject.toml:2` + `website/uv.lock:2305` — package name `research-council`
- `website/schema/evaluation-report.schema.json:3` and `website/frontend/evaluation-report.schema.json:3` — `$id` URL `.../research-council/...`
- `website/setup.sh` (2), `website/README.md` (5), `CLAUDE.md` (4)
- `website/MCP_IMPROVEMENTS.md` (19), `website/PROMPT_IMPROVEMENTS.md` (2)

### 4. Frontend

- `website/frontend/js/api-backend.js:61` — `council/agents/${a.id}` endpoints
- `website/frontend/js/util.js:167` — same endpoint construction
- `website/frontend/js/mock-report.js` (13) — `council/agents/<id>` strings in the fixture
- `website/frontend/js/mcp-servers.js:6` — comment referencing `website/council/mcp.py`
- `website/frontend/20261011-014311-b2e9.json` (13) — a saved report fixture

### 5. Benchmark — the word used as a noun

`bench/benchmark_vs_baseline.py` (57) uses "council" as a **concept**, not the package:
"the multi-agent council vs. one plain model call", `run_council()`, `council_text()`,
`S['council_wins']`, `Council vs Baseline` report title, etc.

### 6. Data files (excluded from the counts above)

- `website/.results/*.json` — 5 files × 13 matches (same `council/agents/...` strings)
- `website/examples/*.json` — 2 files × 13 matches

---

## Not covered

- `website/data/settings.json` — owned by `root`, mode `600`, so it is **not readable**
  by the current user, and `sudo` requires interactive authentication. It is the
  persisted settings file, so it likely holds group/agent data but probably not the
  literal word "council". To check it:

  ```sh
  sudo grep -ni council website/data/settings.json
  ```

  or fix ownership first:

  ```sh
  sudo chown "$USER" website/data/settings.json
  ```

---

## Summary

| Category | Files | Nature of use |
| --- | --- | --- |
| Package internals | 4 | Package name / imports / SLIM namespace |
| Importers | ~13 | `from council import ...` |
| Config / build / docs | 9 | Docker anchor, package name, schema `$id`, prose |
| Frontend | 5 | `council/agents/<id>` endpoint strings |
| Benchmark | 1 | "council" as a noun (the multi-agent system) |
| Data fixtures | 7 | `council/agents/...` in saved reports |

The term is consistent throughout: **`council`** (never `counsil`).
