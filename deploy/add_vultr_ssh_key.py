#!/usr/bin/env python3
"""Register the local deploy public key with Vultr.

Reads VULTR_API_ACCESS from the repo-root .env and the public key from
deploy/keys/vultr_deploy.pub, then makes sure that key exists in the Vultr
account so it can be selected when creating a droplet.

Prints only the key id/name -- never the API key or the private key.

    python3 deploy/add_vultr_ssh_key.py
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
PUBKEY_FILE = ROOT / "deploy" / "keys" / "vultr_deploy.pub"
KEY_NAME = "autoinvestigate-deploy"
API = "https://api.vultr.com/v2/ssh-keys"


def read_env(name):
    if not ENV_FILE.exists():
        sys.exit(f"{ENV_FILE} not found")
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith(name + "="):
            val = line.split("=", 1)[1].strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            return val
    return ""


def request(method, url, api_key, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + api_key)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def main():
    api_key = read_env("VULTR_API_ACCESS")
    if not api_key:
        sys.exit("VULTR_API_ACCESS is not set in .env")
    if not PUBKEY_FILE.exists():
        sys.exit(f"{PUBKEY_FILE} not found -- generate the keypair first")
    pubkey = PUBKEY_FILE.read_text().strip()

    status, body = request("GET", API, api_key)
    if status != 200:
        sys.exit(f"Vultr rejected the API key (HTTP {status}): {body.get('error', body)}")
    for k in body.get("ssh_keys", []):
        if k.get("ssh_key", "").strip() == pubkey:
            print(f"already registered: id={k['id']} name={k['name']}")
            return

    status, body = request("POST", API, api_key, {"name": KEY_NAME, "ssh_key": pubkey})
    if status not in (200, 201):
        sys.exit(f"failed to add key (HTTP {status}): {body.get('error', body)}")
    k = body.get("ssh_key", {})
    print(f"added: id={k.get('id')} name={k.get('name')}")


if __name__ == "__main__":
    main()
