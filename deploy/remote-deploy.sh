#!/usr/bin/env bash
#
# Deploy the AutoInvestigate stack on the Vultr droplet.
#
# This script runs ON the server. GitHub Actions copies it over SSH and runs it
# (see .github/workflows/deploy.yml); you can also run it by hand from the repo:
#
#   ./deploy/remote-deploy.sh [ref] [--force] [--reset-state]
#
#   ref            commit SHA, branch, or tag to deploy (empty = origin/<BRANCH>)
#   --force        rebuild images and recreate containers even if nothing changed
#   --reset-state  wipe the server's runtime state (runs, artifacts, logs,
#                  settings) before starting; .env is kept. Server-only: nothing
#                  on your machine or in the repo is touched.
#
# Environment variables (all optional):
#   APP_DIR     repo location on the server   (default: /opt/autoinvestigate)
#   BRANCH      branch to track               (default: main)
#   APP_REPO    git remote to clone from      (default: the GitHub repo)
#   ENV_FILE    path to the .env              (default: $APP_DIR/.env)
#   COMPOSE_FILE path to docker-compose.yml   (default: $APP_DIR/docker-compose.yml)
#   BOOTSTRAP   .env bootstrap file pushed by CI
#               (default: /tmp/autoinvestigate-bootstrap.env)
#
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/autoinvestigate}"
BRANCH="${BRANCH:-main}"
APP_REPO="${APP_REPO:-https://github.com/hyperupcall/AutoInvestigate.git}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$APP_DIR/docker-compose.yml}"
BOOTSTRAP="${BOOTSTRAP:-/tmp/autoinvestigate-bootstrap.env}"

FORCE=0
RESET_STATE=0
REF=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --force)       FORCE=1; shift ;;
    --reset-state) RESET_STATE=1; shift ;;
    -h|--help)     sed -n '2,23p' "$0"; exit 0 ;;
    --)            shift; break ;;
    *)             REF="$1"; shift ;;
  esac
done

log()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[33mwarning: %s\033[0m\n' "$*" >&2; }
die()  { printf '\n\033[31merror: %s\033[0m\n' "$*" >&2; exit 1; }

# The bootstrap file carries the API key, so never leave it behind.
trap 'rm -f "$BOOTSTRAP"' EXIT

command -v git    >/dev/null 2>&1 || die "git is not installed on the server"
command -v docker >/dev/null 2>&1 || die "docker is not installed on the server"
docker compose version >/dev/null 2>&1 || die "the docker compose plugin is missing on the server"

# ---------------------------------------------------------------- 1. the repo
if [ ! -d "$APP_DIR/.git" ]; then
  if [ -e "$APP_DIR" ] && [ -n "$(ls -A "$APP_DIR" 2>/dev/null)" ]; then
    die "$APP_DIR exists but is not a git checkout; move it aside or set APP_DIR"
  fi
  log "cloning $APP_REPO into $APP_DIR"
  mkdir -p "$(dirname "$APP_DIR")"
  git clone "$APP_REPO" "$APP_DIR"
fi
cd "$APP_DIR"

log "fetching from origin"
git fetch --prune --tags origin

# ------------------------------------------------------------- 2. the commit
if [ -n "$REF" ]; then
  TARGET="$REF"
  # A bare SHA that is not present locally needs an explicit fetch.
  if ! git rev-parse --verify --quiet "$TARGET^{commit}" >/dev/null 2>&1; then
    log "fetching '$REF' from origin"
    git fetch origin "$REF" || die "cannot fetch '$REF' from origin"
  fi
else
  TARGET="origin/$BRANCH"
fi

COMMIT="$(git rev-parse --verify "$TARGET^{commit}")" || die "cannot resolve '$TARGET' to a commit"
SHORT="$(git rev-parse --short "$COMMIT")"
log "deploying $TARGET ($SHORT)"

git checkout --force --detach "$COMMIT" >/dev/null 2>&1

# ---------------------------------------------------------------- 3. the .env
if [ ! -f "$ENV_FILE" ]; then
  if [ -f "$BOOTSTRAP" ] && grep -q '^OPENROUTER_API_KEY=sk-or-' "$BOOTSTRAP" 2>/dev/null; then
    log "creating $ENV_FILE from the CI bootstrap"
    umask 077
    cp "$BOOTSTRAP" "$ENV_FILE"
    if ! grep -q '^SLIM_SERVER=' "$ENV_FILE" 2>/dev/null; then
      printf 'SLIM_SERVER=slim:46357\n' >> "$ENV_FILE"
    fi
    printf 'HOST_UID=%s\nHOST_GID=%s\n' "$(id -u)" "$(id -g)" >> "$ENV_FILE"
  else
    die "$ENV_FILE is missing. Create it first (see deploy/README.md), or set the OPENROUTER_API_KEY and SLIM_SHARED_SECRET GitHub secrets so CI can bootstrap it."
  fi
fi

# ------------------------------------------------------- 3b. optional state reset
COMPOSE=(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE")

if [ "$RESET_STATE" = 1 ]; then
  log "resetting server state (containers + runtime data; .env is kept)"
  "${COMPOSE[@]}" down --remove-orphans --volumes 2>/dev/null || true
  rm -rf "$APP_DIR/_artifacts" "$APP_DIR/_artifactfactory-data" \
         "$APP_DIR/logs" "$APP_DIR/website/data" "$APP_DIR/website/council_results"
  mkdir -p "$APP_DIR/_artifacts" "$APP_DIR/_artifactfactory-data" \
           "$APP_DIR/logs" "$APP_DIR/website/data" "$APP_DIR/website/council_results"
fi

# ------------------------------------------------------------- 4. build & up
if [ "$FORCE" = 1 ]; then
  log "building images (--pull)"
  "${COMPOSE[@]}" build --pull
else
  log "building images"
  "${COMPOSE[@]}" build
fi

log "starting containers"
UP_ARGS=(-d --remove-orphans)
if [ "$FORCE" = 1 ]; then UP_ARGS+=(--force-recreate); fi
"${COMPOSE[@]}" up "${UP_ARGS[@]}"

# ------------------------------------------------------------ 5. health checks
log "waiting for the stack to become healthy"
FAILED=0
wait_for() {  # name url
  local name="$1" url="$2"
  for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "$url" 2>/dev/null; then printf '  ok    %s\n' "$name"; return 0; fi
    sleep 2
  done
  printf '  FAIL  %s (%s)\n' "$name" "$url" >&2
  return 1
}

wait_for_caddy() {  # Caddy is up and enforcing auth when / answers 401
  local code
  for _ in $(seq 1 60); do
    code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/ 2>/dev/null || echo 000)"
    if [ "$code" = "401" ]; then printf '  ok    %s\n' "caddy (auth enforced)"; return 0; fi
    sleep 2
  done
  printf '  FAIL  caddy (expected 401, got %s)\n' "$code" >&2
  return 1
}

wait_for "artifactfactory" "http://127.0.0.1:8080/health"      || FAILED=1
wait_for "web"             "http://127.0.0.1:8090/api/status"  || FAILED=1
wait_for "frontend"        "http://127.0.0.1:8000/"             || FAILED=1
wait_for_caddy                                                   || FAILED=1

if [ "$FAILED" = 1 ]; then
  log "recent logs"
  "${COMPOSE[@]}" logs --tail=40 web artifactfactory caddy 2>/dev/null || true
  die "one or more services did not become healthy"
fi

log "done — deployed $SHORT"
"${COMPOSE[@]}" ps
