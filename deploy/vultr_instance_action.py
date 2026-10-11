#!/usr/bin/env python3
"""Start, stop, or reboot a Vultr instance by label or id.

Reads VULTR_API_ACCESS from the repo-root .env. Prints no secrets.

    python3 deploy/vultr_instance_action.py start autoinvestigate
    python3 deploy/vultr_instance_action.py stop  autoinvestigate
    python3 deploy/vultr_instance_action.py reboot autoinvestigate
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
API = "https://api.vultr.com/v2"
ACTIONS = {"start", "stop", "reboot", "halt"}


def read_env(name):
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith(name + "="):
            val = line.split("=", 1)[1].strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            return val
    return ""


def req(method, url, key, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", "Bearer " + key)
    r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ACTIONS:
        sys.exit(__doc__)
    action, target = sys.argv[1], sys.argv[2]
    key = read_env("VULTR_API_ACCESS")
    if not key:
        sys.exit("VULTR_API_ACCESS is not set in .env")

    status, body = req("GET", API + "/instances", key)
    if status != 200:
        sys.exit(f"HTTP {status}: {body.get('error', body)}")
    inst = next((i for i in body.get("instances", [])
                 if i.get("id") == target or i.get("label") == target), None)
    if not inst:
        sys.exit(f"no instance matching {target!r}")

    status, body = req("POST", f"{API}/instances/{inst['id']}/{action}", key)
    if status not in (200, 202, 204):
        sys.exit(f"HTTP {status}: {body.get('error', body)}")
    print(f"{action}: {inst['label']} ({inst['id']}) -> HTTP {status}")


if __name__ == "__main__":
    main()
