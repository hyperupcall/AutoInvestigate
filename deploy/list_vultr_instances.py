#!/usr/bin/env python3
"""List Vultr instances (label, id, main IP, status, region).

Reads VULTR_API_ACCESS from the repo-root .env. Prints no secrets.

    python3 deploy/list_vultr_instances.py
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
API = "https://api.vultr.com/v2/instances"


def read_env(name):
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith(name + "="):
            val = line.split("=", 1)[1].strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            return val
    return ""


def main():
    api_key = read_env("VULTR_API_ACCESS")
    if not api_key:
        sys.exit("VULTR_API_ACCESS is not set in .env")
    req = urllib.request.Request(API)
    req.add_header("Authorization", "Bearer " + api_key)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()}")
    instances = body.get("instances", [])
    if not instances:
        print("no instances")
        return
    for i in instances:
        print(f"label={i.get('label')!r} id={i.get('id')} ip={i.get('main_ip')} "
              f"status={i.get('status')} region={i.get('region')} os={i.get('os')}")


if __name__ == "__main__":
    main()
