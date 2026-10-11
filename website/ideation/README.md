# Ideation Collective

A long-running daemon that watches the internet for a **tagged watchlist of topics**
and turns what it finds into ideas. It is the real backend for the frontend's first
column ("Idea Generation") and the third collective in the repo, alongside the
deliberation collective (`orchestrator/` + `agent_host/`) and the Artifact Factory
(`artifactfactory/`).

Unlike deliberation — one idea in, one report out, driven by a click — ideation runs
unattended: it polls sources on a schedule, a small team of agents works **together**
to refine what it finds into ideas, and the ideas land in the same store the frontend
renders.

## Running

From `website/`:

```bash
python -m ideation.daemon
```

or from the repo root:

```bash
python website/ideation/daemon.py
```

Both print the listening URL (default `http://127.0.0.1:8091`). Open it for the
**Ideation View** — the topics, the sessions, the ideas and the memory. The page is a
frontend page (`website/frontend/ideation.html`), so all frontend code lives in one
place; the daemon serves it at `GET /`. The frontend's header has a **Research and Ideation** link
that opens the same page.

The view is three columns: **Topics** and **Sessions** side by side (each scrolls on
its own), and the **main view** to their right. Clicking a session shows it in the
main view. At the end of the topics list is a long **+ Add Topic** button: describe a
topic and the AI fills in the name, description, tags and keywords for you (editable
before you add it).

In Docker it is the `ideation` service (built from `./website`, command
`python -m ideation.daemon`, port `8091`). Its SQLite database lives on the
`./_ideation-data` volume, so it survives a rebuild.

**Volume ownership.** Docker creates a missing bind-mount directory as `root`, so a
container running as your user cannot write to it. The service therefore starts as
root and runs `website/docker-entrypoint.py`, which chowns `_ideation-data` to
`HOST_UID:HOST_GID` and then drops to that user — so the database ends up owned by
you on the host. If you already have a root-owned `_ideation-data/` from an earlier
run, either rebuild (`docker compose up --build ideation`) or fix it once with
`sudo chown -R "$(id -u):$(id -g)" _ideation-data`.

## How it works

```
scheduler ──► cycle ──► poll sources (arXiv · HN · Reddit · news) ──► new signals
                                                                          │
                                          session ◄───────────────────────┘
                                             │
   Idea Generator ──► Builder ──► Analyzer
        │               │            │
        └───────────────┴────────────┴──► idea + build score + analysis + memory
```

- **A cycle** polls every enabled topic's sources and stores the new signals
  (deduplicated by a hash of the URL/title). A topic that found something new gets a
  session. The scheduler runs a cycle every `ID_POLL_INTERVAL` seconds (default 900).
- **A session** is the team working together. Three agents speak in a fixed order, round
  by round, each building on what the others said — they collaborate, they do not compete:
  - **Idea Generator** — given a description of the idea, does extra research and
    produces a more finalized idea, or a completely different one.
  - **Builder** — scores how well the idea can be built as an MVP or artifact.
  - **Analyzer** — researches the idea and judges whether it makes sense or is nonsense.

The final idea is the generator's latest; the build score and the analysis come from
last round's Builder and Analyzer.

## The message format

Every message an agent sends has the same shape (enforced in `agents.py`):

| Field | What it is |
| --- | --- |
| `context` | **Large** text: the background, the reasoning, and the text of the websites/signals that were read. |
| `idea` | The idea itself — **one sentence** only. |
| `justification` | **3-4** bullet points on why it is a good idea. |
| `sources` | The links the message drew on. |

The **Builder** adds a `build` score (`mvp`, `artifact`, `effort`, `blockers`); the
**Analyzer** adds an `analysis` verdict (`makes_sense` / `questionable` / `nonsense`,
with `confidence`, `findings` and `blockers`). Any agent may add `memory` proposals;
only those with importance ≥ 7 are promoted — the "VERY IMPORTANT" filter.

## Storage

SQLite (`_ideation-data/ideation.db`) — one file, on a Docker volume. Collections:
`topics`, `signals`, `ideas`, `sessions`, `events`, `memory`. SQLite is used because
the signal firehose is append-heavy and needs cheap dedup, and because the daemon is
multi-threaded (the HTTP server and the scheduler both touch it).

## Configuration

| Env var | CLI flag | Default | Meaning |
| --- | --- | --- | --- |
| `ID_HOST` | `--host` | `127.0.0.1` | Bind host |
| `ID_PORT` | `--port` | `8091` | Bind port |
| `ID_DATA_DIR` | `--data-dir` | `<repo>/_ideation-data` | Where `ideation.db` lives |
| `ID_FRONTEND_DIR` | `--frontend-dir` | `<repo>/website/frontend` | Where the Ideation View page lives |
| `ID_POLL_INTERVAL` | `--poll-interval` | `900` | Seconds between cycles |
| `ID_MAX_COST` | | `0.50` | Per-session / per-cycle cost cap |
| `ID_AUTOSTART` | `--no-autostart` | `1` | Start the scheduler with the daemon |
| `ID_MODEL` | | `openai/gpt-oss-120b` | Default model for the agents |
| `ID_ROUNDS` | | `2` | Refinement rounds per session |
| `ID_SIGNALS_PER_TOPIC` | | `12` | Newest signals fed to a session |

Model calls use `OPENROUTER_API_KEY` from the root `.env` (the same single key every
service uses). Without a key, the daemon still runs — sessions record the failure and
carry on.

## Settings

The **Settings** button in the Ideation View opens the daemon's settings, saved with
`PUT /api/settings` and persisted to `_ideation-data/settings.json`:

- **Models** — a **default model** for the agents, a **per-agent model** for each of the
  three agents (Idea Generator, Builder, Analyzer), and the **topic drafting model** used
  by **+ Add Topic**. A per-agent choice overrides the default; the default is used for any
  agent without its own. Each model has a **Thinking** toggle (reasoning on/off). The models
  offered come from `website/frontend/js/model-info.js`.
- **Daemon** — the poll interval, the per-session cost cap, the refinement rounds, the
  signals fed to a session, and whether the scheduler starts with the daemon.

The same values are available over the API: `GET /api/settings` returns the settings
plus the resolved agent roster; `PUT /api/settings` accepts any subset (an
`agent_models` map of agent id → model).

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | The Ideation View page |
| GET | `/info`, `/health` | Service info; health |
| GET/POST | `/api/topics` | List / create topics |
| POST | `/api/topics/draft` | Draft a topic (name, description, tags, keywords) from a description |
| PUT/DELETE | `/api/topics/{id}` | Update / delete a topic |
| GET | `/api/ideas`, `/api/ideas/{id}` | Generated ideas |
| GET | `/api/tree` | The ideas as the frontend's level tree (abstract at 1, concrete at 2) |
| GET | `/api/signals`, `/api/memory` | The raw feed; the memory |
| GET/POST | `/api/sessions` | List / start a session |
| GET | `/api/sessions/{id}` | One session |
| GET | `/api/sessions/{id}/events?since=N` | The live event stream |
| GET | `/api/sessions/{id}/report` | The session report |
| POST | `/api/generate` | The Part 1 generation contract |
| POST | `/api/poll` | Run a cycle now |
| GET | `/api/status` | Daemon + scheduler status |
| GET/PUT | `/api/settings` | The daemon's settings |

Errors are JSON: `{"error": "..."}` with `400` (bad input), `404` (missing),
`500` (unexpected).

## Tests

From `website/`:

```bash
uv run --no-project --python 3.13 --with httpx==0.28.1 --with python-dotenv --with pytest \
  python -m pytest tests/test_ideation.py -q
```
