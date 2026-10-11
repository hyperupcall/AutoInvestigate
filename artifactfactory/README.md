# Artifact Factory

A small, self-contained Python daemon that turns a **validated research idea**
into a set of tangible implementation artifacts. It is the backend for the
frontend's third column ("Idea Execution").

> **All artifact content is DUMMY for now.** Builders emit deterministic
> placeholder files derived from the idea text. The API, storage, and planner
> layers are real and are designed so the dummy builders can be swapped for AI
> later without changing anything else.

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

Open that URL in a browser for a plain dashboard listing every evaluation (idea)
the factory has been given, with its plan and artifact status. The frontend's
header has an **Artifact Factory** button that opens the same page.

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
| GET | `/` | HTML dashboard: every evaluation (idea) the factory was given |
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
