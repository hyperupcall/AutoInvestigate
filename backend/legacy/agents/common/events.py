"""Append-only JSONL event log (one JSON object per line)."""
import json
import os
from datetime import datetime, timezone

from agents.common.config import EVENTS_LOG


def log_event(kind: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(EVENTS_LOG) or ".", exist_ok=True)
    line = {"logged_at": datetime.now(timezone.utc).isoformat(), "kind": kind, **payload}
    with open(EVENTS_LOG, "a") as f:
        f.write(json.dumps(line) + "\n")
