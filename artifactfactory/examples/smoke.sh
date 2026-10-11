#!/bin/sh
# End-to-end smoke test: start the daemon, add an idea, implement it, download
# the tarball, then shut the daemon down. Run from the repo root:
#   sh artifactfactory/examples/smoke.sh
set -e

PORT=8099
DATA_DIR=$(mktemp -d)
BASE="http://127.0.0.1:$PORT"

python3 -m artifactfactory.daemon --port "$PORT" --data-dir "$DATA_DIR" --artifacts-dir "$DATA_DIR/artifacts" &
PID=$!
trap 'kill "$PID" 2>/dev/null || true; rm -rf "$DATA_DIR"' EXIT

sleep 1

echo "== health =="
curl -s "$BASE/health"
echo

echo "== create idea =="
RESP=$(curl -s -X POST "$BASE/ideas" \
  -H 'Content-Type: application/json' \
  -d '{"text": "A homomorphic encryption toolkit for cloud analytics."}')
echo "$RESP"
PLAN_ID=$(printf '%s' "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin)["plan"]["id"])')
echo "plan: $PLAN_ID"

echo "== start implementation =="
JOB_ID=$(curl -s -X POST "$BASE/plans/$PLAN_ID/implement" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "job: $JOB_ID"

echo "== poll job =="
while true; do
  STATUS=$(curl -s "$BASE/jobs/$JOB_ID" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')
  echo "status: $STATUS"
  case "$STATUS" in
    succeeded|failed) break ;;
  esac
  sleep 0.3
done

echo "== artifacts =="
curl -s "$BASE/plans/$PLAN_ID" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); [print("-", a["type"], a["uri"]) for a in d["artifacts"]]'

echo "== download tarball =="
ARTIFACT_ID=$(curl -s "$BASE/plans/$PLAN_ID" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(next(a["id"] for a in d["artifacts"] if a["type"]=="tarball"))')
curl -s -o "$DATA_DIR/artifacts.tar.gz" "$BASE/artifacts/$ARTIFACT_ID/download"
tar -tzf "$DATA_DIR/artifacts.tar.gz"

echo "== ok =="
