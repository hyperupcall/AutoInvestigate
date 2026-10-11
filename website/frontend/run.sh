#!/bin/sh
# Serve the frontend (no build step).
#
#   ./run.sh          # http://127.0.0.1:8000/
#   PORT=9000 ./run.sh
set -e

DIR=$(cd "$(dirname "$0")" && pwd)
PORT=${PORT:-8000}

cd "$DIR"
echo "frontend: http://127.0.0.1:$PORT/"
exec python3 -m http.server "$PORT"
