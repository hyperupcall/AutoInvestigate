#!/bin/sh
# Run the Artifact Factory daemon.
#
#   ./run.sh                 # http://127.0.0.1:8080
#   ./run.sh --port 9000     # extra args are passed to the daemon
#
# All AF_* environment variables and CLI flags documented in README.md work here.
set -e

DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$DIR")

# Load the single root .env (all API keys live there), if present.
if [ -f "$ROOT/.env" ]; then
  set -a
  . "$ROOT/.env"
  set +a
fi

cd "$ROOT"
exec python3 -m artifactfactory.daemon "$@"
