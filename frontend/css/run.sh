#!/bin/sh
# No service lives in this directory — it holds the stylesheet that the frontend
# server (../run.sh) serves. This script sanity-checks the CSS here.
set -e

DIR=$(cd "$(dirname "$0")" && pwd)
cd "$DIR"

python3 - <<'PY'
import glob
import sys

status = 0
files = sorted(glob.glob("*.css"))
if not files:
    print("no CSS files found")
for path in files:
    text = open(path, encoding="utf-8").read()
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                break
    if depth == 0:
        print(f"ok: {path}")
    else:
        status = 1
        print(f"unbalanced braces in {path}")
sys.exit(status)
PY
