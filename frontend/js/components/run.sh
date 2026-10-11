#!/bin/sh
# No service lives in this directory — it holds the browser JavaScript that the
# frontend server (../../run.sh) serves. This script syntax-checks the files here.
set -e

DIR=$(cd "$(dirname "$0")" && pwd)
cd "$DIR"

if ! command -v node >/dev/null 2>&1; then
  echo "node not found; skipping JavaScript syntax check"
  exit 0
fi

status=0
for f in *.js; do
  [ -e "$f" ] || continue
  if node --check "$f"; then
    echo "ok: $f"
  else
    status=1
  fi
done
exit "$status"
