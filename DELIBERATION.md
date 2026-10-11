# DELIBERATION.md

Working notes on the **"deliberation"** naming across the repository.

> Context: the multi-agent system is called **"deliberation"** — the
> `website/deliberation/` Python package and the "multi-agent deliberation"
> concept. This document records where that term appears and what each use means.

---

## Search method

Case-insensitive recursive search, excluding the vendored virtualenv and the
unreadable settings file:

```sh
grep -rni "deliberation" . \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude=settings.json
```

**Result: 482 matches across 55 files** (excluding `.git`, `.venv`, `__pycache__`
and this file).

---

## Where "deliberation" appears

### 1. The package itself — `website/deliberation/`

The name is the Python package, referenced internally:

| File | What it is |
| --- | --- |
| `website/deliberation/defaults.py` | `from deliberation.prompts import ROOT, role_name` |
| `website/deliberation/settings.py` | `from deliberation.defaults import ...`, `from deliberation.prompts import ROOT` |
| `website/deliberation/report.py` | `from deliberation.defaults import archetype_library`, `deliberation/agents/<id>` endpoints |
| `website/deliberation/slim.py` | `NAMESPACE, GROUP = "deliberation", "agents"` — the AGNTCY/SLIM namespace is literally `"deliberation"` |

### 2. Importers of the package

- `website/agent_host/executor.py` (8) — `from deliberation import openrouter`, logger `"deliberation.agent"`
- `website/agent_host/main.py` (2) — logger `"deliberation.host"`
- `website/agent_host/single.py` (3) — `AgntcyFactory(f"deliberation.{agent_id}")`
- `website/orchestrator/` — `analysis.py`, `bus.py`, `compat.py`, `export.py`, `pipeline.py`, `run.py`, `sources.py`, `web.py`
- `website/tests/test_core.py`, `website/tests/test_report.py`
- `website/scripts/live_smoke.py`

### 3. Config / build / docs

- `docker-compose.yml` (5) — `x-deliberation: &deliberation` anchor, `container_name: deliberation-slim`
- `website/Dockerfile:6` — `COPY deliberation ./deliberation`
- `website/pyproject.toml:2` + `website/uv.lock:2305` — package name `research-deliberation`
- `website/schema/evaluation-report.schema.json:3` and `website/frontend/evaluation-report.schema.json:3` — `$id` URL `.../research-deliberation/...`
- `website/setup.sh` (2), `website/README.md` (7), `CLAUDE.md` (9)

### 4. Frontend

- `website/frontend/js/api-backend.js` — `deliberation/agents/${a.id}` endpoints
- `website/frontend/js/util.js` — same endpoint construction
- `website/frontend/js/mock-report.js` (13) — `deliberation/agents/<id>` strings in the fixture
- `website/frontend/js/mcp-servers.js` — comment referencing `website/deliberation/mcp.py`
- `website/frontend/20261011-014311-b2e9.json` (13) — a saved report fixture

### 5. Benchmark — the word used as a noun

`website/scripts/benchmark_vs_baseline.py` (59) uses "deliberation" as a **concept**, not the package:
"the multi-agent deliberation vs. one plain model call", `run_deliberation()`, `deliberation_text()`,
`S['deliberation_wins']`, `Deliberation vs Baseline` report title, etc.

### 6. Data files (excluded from the counts above)

- `website/examples/*.json` — 2 files × 13 matches (same `deliberation/agents/...` strings)
- `website/frontend/20261011-014311-b2e9.json` — 13 matches

---

## Not covered

- `website/data/settings.json` — the persisted settings file. It does not exist in
  this checkout; if it is created at runtime it may hold group/agent data. To check it:

  ```sh
  grep -ni deliberation website/data/settings.json
  ```

---

## Summary

| Category | Files | Nature of use |
| --- | --- | --- |
| Package internals | 4 | Package name / imports / SLIM namespace |
| Importers | ~13 | `from deliberation import ...` |
| Config / build / docs | 9 | Docker anchor, package name, schema `$id`, prose |
| Frontend | 5 | `deliberation/agents/<id>` endpoint strings |
| Benchmark | 1 | "deliberation" as a noun (the multi-agent system) |
| Data fixtures | 7 | `deliberation/agents/...` in saved reports |

The term is consistent throughout: **`deliberation`**.
