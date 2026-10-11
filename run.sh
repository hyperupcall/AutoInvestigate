#!/bin/sh
# Run the whole stack: the Artifact Factory backend and the frontend static server.
#
#   ./run.sh                    # backend on :8080, frontend on :8000
#   AF_PORT=9000 ./run.sh       # override the backend port
#   FRONTEND_PORT=9001 ./run.sh # override the frontend port
#
# Ctrl-C stops both.
set -e

ROOT=$(cd "$(dirname "$0")" && pwd)

AF_HOST=${AF_HOST:-127.0.0.1}
AF_PORT=${AF_PORT:-8080}
FRONTEND_PORT=${FRONTEND_PORT:-8000}

cd "$ROOT"

echo "artifactfactory: http://$AF_HOST:$AF_PORT"
python3 -m artifactfactory.daemon --host "$AF_HOST" --port "$AF_PORT" &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "frontend:        http://127.0.0.1:$FRONTEND_PORT/"
cd "$ROOT/website/frontend"
python3 -m http.server "$FRONTEND_PORT"
