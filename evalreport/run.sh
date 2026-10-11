#!/bin/sh
# Run the Outshift Research Intelligence Streamlit app.
#
#   ./run.sh                      # uses the uv-managed ./.venv (created on first run)
#   OPENAI_API_KEY=sk-... ./run.sh
#
# Extra args are passed through to `streamlit run`, e.g.:
#   ./run.sh --server.port 8502
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
  exec uv run streamlit run app.py "$@"
fi

# Fallback: an existing ./.venv, then plain python3.
if [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python -m streamlit run app.py "$@"
fi
exec python3 -m streamlit run app.py "$@"
