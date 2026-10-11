# Artifact Factory — curl examples

Assumes the daemon is running at `http://127.0.0.1:8080`.

```bash
BASE=http://127.0.0.1:8080
```

## 1. Health

```bash
curl -s $BASE/health
```

## 2. Create a validated idea (creates a plan)

```bash
PLAN_ID=$(curl -s -X POST $BASE/ideas \
  -H 'Content-Type: application/json' \
  -d '{"text": "A homomorphic encryption toolkit for cloud analytics."}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["plan"]["id"])')
echo "$PLAN_ID"
```

## 3. Create an unvalidated idea (no plan)

```bash
curl -s -X POST $BASE/ideas \
  -H 'Content-Type: application/json' \
  -d '{"text": "Rough sketch", "validated": false}'
```

## 4. List ideas / plans

```bash
curl -s $BASE/ideas
curl -s $BASE/plans
```

## 5. Get the plan

```bash
curl -s $BASE/plans/$PLAN_ID
```

## 6. Start implementation (async)

```bash
JOB_ID=$(curl -s -X POST $BASE/plans/$PLAN_ID/implement \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "$JOB_ID"
```

## 7. Poll the job until terminal

```bash
while true; do
  STATUS=$(curl -s $BASE/jobs/$JOB_ID | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')
  echo "status: $STATUS"
  case "$STATUS" in
    succeeded|failed) break ;;
  esac
  sleep 0.5
done
```

## 8. Inspect the plan's artifacts

```bash
curl -s $BASE/plans/$PLAN_ID | python3 -m json.tool
```

## 9. Download the tarball artifact

```bash
ARTIFACT_ID=$(curl -s $BASE/plans/$PLAN_ID \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(next(a["id"] for a in d["artifacts"] if a["type"]=="tarball"))')

curl -s -o artifacts.tar.gz $BASE/artifacts/$ARTIFACT_ID/download
tar -tzf artifacts.tar.gz
```

## 10. Download any other artifact (returns a zip)

```bash
SRC_ID=$(curl -s $BASE/plans/$PLAN_ID \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(next(a["id"] for a in d["artifacts"] if a["type"]=="source_repository"))')

curl -s -o source.zip $BASE/artifacts/$SRC_ID/download
unzip -l source.zip
```
