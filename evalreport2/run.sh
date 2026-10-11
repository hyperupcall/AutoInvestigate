#!/bin/sh
# Run the Outshift Research Intelligence CLI.
#
#   ./run.sh "Evaluate homomorphic encryption for enterprise analytics"
#   ./run.sh --compare "Some idea"
#   ./run.sh --demo "Some idea"          # no API key needed
#
# Defaults to the uv-managed ./.venv (created on first run). Extra args are
# passed straight through to the Python entry point.
set -e

DIR=$(cd "$(dirname "$0")" && pwd)
cd "$DIR"

# Default to the uv-managed environment in ./.venv.
if command -v uv >/dev/null 2>&1; then
  if [ ! -x ".venv/bin/python" ]; then
    echo "Creating uv environment in .venv ..." >&2
    uv venv >&2
    uv pip install -r requirements.txt >&2
  fi
  exec uv run python evaluate.py "$@"
fi

# Fallback: an existing ./.venv, then plain python3.
if [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python evaluate.py "$@"
fi
exec python3 evaluate.py "$@"
