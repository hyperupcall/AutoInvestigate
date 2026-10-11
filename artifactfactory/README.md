# Artifact Factory

A small, self-contained Python daemon that turns a **validated research idea**
into a set of tangible implementation artifacts. It is the backend for the
frontend's third column ("Idea Execution").

> **Execute → builds an interactive prototype (`mvp_prototype`): one self-contained HTML file.** The frontend asks
> for `options.artifacts = ["mvp_prototype"]`, so the artifact is exactly one `index.html` and the download is that
> file (not a zip or tarball). One self-contained HTML page (`mvp.py`): a clickable product screen for the idea's
> narrow first version, with demo data, a step-through workflow, live SVG/canvas visualizations and the evaluation
> panel's concerns built in (approval steps, cost, privacy...). It is generated from the idea and, when
> `metadata.evaluation_run_id` is set, from that run's report. External resources and network APIs are stripped, a
> strict Content-Security-Policy is injected, and `GET /artifacts/{id}/view` serves it with the same policy plus
> `sandbox allow-scripts`; the frontend shows it in a sandboxed iframe. Model: `AF_MVP_MODEL` (default
> `anthropic/claude-haiku-5.5`, about 40 s and under a cent). If generation fails, a plain page with the idea and
> verdict is built instead, so the build still yields a single HTML file. The API's default plan is unchanged.
>
> **Two artifact types are real when the idea comes from an evaluation run.** If the idea's
> `metadata.evaluation_run_id` is set (the frontend's **Execute →** sends it), `evaluation.py` fetches that
> run's report from the evaluation backend (`AF_EVAL_API`, default `http://localhost:8090`; `http://web:8090`
> in docker compose) and builds:
>
> - `literature_review` — the arXiv papers the agents were given (and who cited each), every group's verdict,
>   scores, pros and cons, verified disagreement quotes, open questions, and a short related-work synthesis
>   whose citations are checked against the paper list.
> - `source_repository` (Python) — a README with the experiment the panel asked for (goal, hypothesis,
>   method, success and stop criteria) and a starter `experiment.py` (synthetic data, TODOs where real systems
>   plug in), syntax-checked before it is saved.
>
> Model calls use `OPENROUTER_API_KEY` (model: `AF_MODEL`, default `anthropic/claude-haiku-5.5`). Without a run
> id, the backend, or a key, every builder falls back to the deterministic placeholders below. The other types
> (npm package, Docker image, tarball) are still placeholders.

- **Python 3.9+, standard library only.** No third-party dependencies.
- HTTP server built on `http.server.ThreadingHTTPServer`.
- Pluggable storage (`local` default, `s3` skeleton).
- Pluggable artifact builders (registry keyed by artifact type).
- Ideas / plans / artifacts persisted to a single JSON file; jobs are in-memory.

## Running

From the repo root:

```bash
python3 -m artifactfactory.daemon
```

or, equivalently:

```bash
python3 artifactfactory/daemon.py
```

Both print the listening URL (default `http://127.0.0.1:8080`).

Open that URL in a browser for a dashboard listing every evaluation (idea) the
factory has been given, with its plan and artifact status. The dashboard is a
frontend page (`website/frontend/artifactfactory.html`) that talks to this daemon's JSON
API, so all frontend code lives in one place; the daemon serves it at `GET /`
(and its css/js from the frontend directory). The frontend's header has an
**Artifact Factory** button that opens the same page.

## Configuration

| Env var | CLI flag | Default | Meaning |
| --- | --- | --- | --- |
| `AF_HOST` | `--host` | `127.0.0.1` | Bind host |
| `AF_PORT` | `--port` | `8080` | Bind port |
| `AF_DATA_DIR` | `--data-dir` | `<repo>/_artifactfactory-data` | Where `state.json` lives |
| `AF_ARTIFACTS_DIR` | `--artifacts-dir` | `<repo>/_artifacts` | Where generated artifacts are written |
| `AF_STORAGE` | `--storage` | `local` | `local` or `s3` |
| `AF_S3_BUCKET` | `--s3-bucket` | `` | S3 bucket (s3 backend) |
| `AF_S3_PREFIX` | `--s3-prefix` | `` | Key prefix (s3 backend) |
| `AF_FRONTEND_DIR` | `--frontend-dir` | `<repo>/website/frontend` | Where the dashboard page + assets live |
| `AF_RUN_HOST` | — | `127.0.0.1` | Bind host for a run artifact server (see below) |

CLI flags override environment variables. The defaults are anchored to the
project root (the directory containing the `artifactfactory` package), so they
do not depend on the current working directory.

## Where artifacts are stored

With the default `local` backend, artifacts are written under the project's
`_artifacts/` directory, laid out as:

```
_artifacts/
  plans/
    <plan-id>/
      source_repository/<name>/...
      npm_package/<name>/...
      docker_image/<name>/...
      literature_review/<name>/...
      tarball/<name>/<name>.tar.gz
```

`state.json` (ideas, plans, artifact metadata) lives in `_artifactfactory-data/`.
Override either location with `--artifacts-dir` / `--data-dir` (or the matching
env vars). Switching to the `s3` backend replaces `_artifacts/` with the
configured bucket/prefix.

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | Dashboard page (from the frontend): every evaluation the factory was given |
| GET | `/info` | Service info + route list (JSON) |
| GET | `/health` | `{"status": "ok"}` |
| POST | `/ideas` | Create an idea (and a plan if validated) |
| GET | `/ideas` | List ideas |
| GET | `/ideas/{id}` | Get one idea |
| GET | `/plans` | List plans |
| GET | `/plans/{id}` | Get a plan with joined `artifacts` |
| POST | `/plans/{id}/implement` | Start async implementation → `202` job |
| GET | `/jobs` | List jobs |
| GET | `/jobs/{id}` | Get one job |
| GET | `/artifacts/{id}` | Artifact metadata |
| GET | `/artifacts/{id}/download` | Download artifact (raw `.tar.gz`, else a zip) |
| POST | `/artifacts/{id}/run` | Run the artifact as a local server → `201` `{server}` |
| GET | `/servers` | List running artifact servers |
| GET | `/servers/{id}` | One running artifact server |
| POST | `/servers/{id}/stop` | Stop a running artifact server |
| GET | `/run/{id}/...` | The running artifact, proxied through the factory's port |

Errors are JSON: `{"error": "..."}` with `400` (bad input), `404` (missing),
`500` (unexpected).

### Example: create an idea

```bash
curl -s -X POST http://127.0.0.1:8080/ideas \
  -H 'Content-Type: application/json' \
  -d '{"text": "A homomorphic encryption toolkit for cloud analytics."}'
```

Returns `201` with `{"idea": {...}, "plan": {...}}`. The plan has an id like
`plan-9f8e7d6c5b4a` and `artifact_specs` for `source_repository`, `npm_package`,
`docker_image`, `literature_review`, and `tarball`.

### Example: implement a plan

```bash
curl -s -X POST http://127.0.0.1:8080/plans/plan-9f8e7d6c5b4a/implement
```

Returns `202` with a job. Poll `GET /jobs/{id}` until `status` is `succeeded`
or `failed`.

## Artifact types

| Type | Produces |
| --- | --- |
| `source_repository` | A source repo scaffold (default `python`; also `javascript`, `typescript`, `go`, `rust`) |
| `npm_package` | `package.json`, `index.js`, `README.md`, `.npmignore` |
| `docker_image` | `Dockerfile`, `manifest.json`, placeholder `image.tar` |
| `tarball` | A `.tar.gz` of every artifact built so far |
| `literature_review` | A markdown review (Abstract / Background / Related Work / Methods / Findings / Open Questions / References) |

Default plan order: `source_repository` → `npm_package` → `docker_image` →
`literature_review` → `tarball`.

## Running a built artifact

`POST /artifacts/{id}/run` starts the artifact as a real HTTP server (`runtime.py`): a `ThreadingHTTPServer` on an
ephemeral port bound to `AF_RUN_HOST` (default `127.0.0.1`) that serves the artifact's files from storage — the
entry page (`index.html`) at `/` and every other file at its path relative to the artifact's key. Only files that
belong to the artifact are served. The response is `{ "server": { id, url, path, port, status, ... } }`.

Because a container's ephemeral port is not published, the factory also exposes each run through its **own** port at
`/run/{server-id}/` (the `path` field), proxying to the run server. The frontend opens that URL, so it works whether
the factory runs locally or in Docker. `POST /servers/{id}/stop` shuts the server down, after which the URL returns
`409`. Runs are in-memory and stop with the process.

```bash
curl -s -X POST http://127.0.0.1:8080/artifacts/artifact-abc123/run
# {"server": {"id": "server-...", "url": "http://127.0.0.1:54321/", "path": "/run/server-.../", "status": "running", ...}}
curl -s -X POST http://127.0.0.1:8080/servers/server-.../stop
```

## How to plug in S3 / AI later

**S3:** set `AF_STORAGE=s3` and `AF_S3_BUCKET` (and optionally `AF_S3_PREFIX`).
`S3Storage` imports `boto3` lazily and raises a clear `RuntimeError` if it is
not installed. No other code changes are needed — the builders only talk to the
`StorageBackend` interface.

**AI:** each artifact type maps to a builder in `artifacts.BUILDERS`. To make a
builder real, replace its `build()` body with a call to your model and write the
generated files through `ctx.storage`. The REST API, planner, storage, and
persistence layers stay exactly the same.

## Tests

From the repo root:

```bash
python3 -m unittest discover -s artifactfactory -t . -v
```
