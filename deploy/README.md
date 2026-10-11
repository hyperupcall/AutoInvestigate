# Deploying to Vultr

`deploy/remote-deploy.sh` runs on the Vultr droplet and does the actual work:
it fetches the repo, checks out the requested commit, builds the images with
Docker Compose, starts the stack and waits for the health checks. GitHub Actions
(`.github/workflows/deploy.yml`) just copies that script over SSH and runs it.

Nothing is built on the GitHub runner — the droplet's 16 vCPUs and 64 GB of RAM
do the building, so there is no registry to manage and no image to push.

## What it deploys

The root `docker-compose.yml` stack:

| Service | Host URL | Health check |
| --- | --- | --- |
| `frontend` | http://localhost:8000 | `GET /` |
| `artifactfactory` | http://localhost:8080 | `GET /health` |
| `web` (+ `slim`, `agent_host`) | http://localhost:8090 | `GET /api/status` |

`orchestrator` is behind the `run` profile and is not started by a deploy.

## Triggers

- **Push to `main`** → automatic "pull latest" deploy.
- **Actions ▸ Deploy to Vultr ▸ Run workflow** → deploy a specific commit, or
  force a rebuild. Two inputs:
  - `ref` — a commit SHA, branch, or tag. Empty means "latest `main`".
  - `force` — rebuild images and recreate containers even if nothing changed.

## Force-deploy a particular commit

From the Actions UI: **Run workflow**, put the SHA in `ref`, tick `force`.

From the command line with the GitHub CLI:

```bash
gh workflow run deploy.yml -f ref=<commit-sha> -f force=true
```

You can also run the script directly on the server:

```bash
ssh deploy@<droplet> 'cd /opt/autoinvestigate && ./deploy/remote-deploy.sh <commit-sha> --force'
```

## Required GitHub secrets

Set these in **Settings ▸ Secrets and variables ▸ Actions ▸ Secrets**:

| Secret | Purpose |
| --- | --- |
| `VULTR_HOST` | droplet IP or hostname |
| `VULTR_USER` | SSH user on the droplet |
| `VULTR_SSH_KEY` | that user's private key (full PEM/OpenSSH text) |

Optional:

| Secret | Purpose |
| --- | --- |
| `VULTR_PORT` | SSH port (default `22`) |
| `VULTR_KNOWN_HOSTS` | pinned host key(s); if absent, `ssh-keyscan` is used |
| `OPENROUTER_API_KEY` | only to bootstrap `.env` on a brand-new server |
| `SLIM_SHARED_SECRET` | only to bootstrap `.env` on a brand-new server |

Optional repository **variable** (**Settings ▸ Secrets and variables ▸ Actions ▸
Variables**):

| Variable | Purpose |
| --- | --- |
| `APP_DIR` | repo location on the server (default `/opt/autoinvestigate`) |

## One-time server setup

The workflow assumes Docker and the Compose plugin are installed and that the
deploy user can run them. On a fresh droplet:

```bash
# as root
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy        # or whichever user VULTR_USER names
```

The `.env` file is **not** committed (it is gitignored). You can either:

- let CI create it — set the `OPENROUTER_API_KEY` and `SLIM_SHARED_SECRET`
  secrets and the first deploy writes `/opt/autoinvestigate/.env` for you
  (adding `SLIM_SERVER`, `HOST_UID` and `HOST_GID` on the server); or
- create it yourself on the server, e.g. `cd /opt/autoinvestigate && cd website && ./setup.sh`.

CI only uses the bootstrap when the server has no `.env`; an existing file is
never overwritten. The bootstrap file is removed from the server on every run.

## How the deploy script behaves

`deploy/remote-deploy.sh [ref] [--force]`

1. Clones the repo into `APP_DIR` if it is not there yet, then `git fetch --prune --tags origin`.
2. Resolves `ref` (fetching it explicitly if it is a SHA that is not present) or
   falls back to `origin/<BRANCH>`, and checks it out **detached** with `--force`.
   Untracked files such as `.env`, `_artifacts/` and `_artifactfactory-data/` are
   left alone.
3. Ensures `.env` exists (bootstrapping it from CI if needed).
4. `docker compose build` (with `--pull` when forced) and
   `docker compose up -d --remove-orphans` (adding `--force-recreate` when forced).
5. Waits up to two minutes for the three health endpoints and prints the logs if
   any of them fail.

## Troubleshooting

- **`Permission denied (publickey)`** — `VULTR_SSH_KEY` is not the matching
  private key for `VULTR_USER`, or the key needs a trailing newline (the workflow
  adds one).
- **`Host key verification failed`** — set `VULTR_KNOWN_HOSTS` to the droplet's
  `known_hosts` line (`ssh-keyscan <host>`).
- **`.env is missing`** — the server has no `.env` and no `OPENROUTER_API_KEY`
  secret was provided; create it on the server or add the secret.
- **A service never becomes healthy** — the workflow prints the last 40 log lines
  for `web` and `artifactfactory`; run `docker compose logs -f` on the server.
