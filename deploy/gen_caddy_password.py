#!/usr/bin/env python3
"""Generate a 40-character random password and its bcrypt hash for Caddy basic auth.

Writes CADDY_USER, CADDY_PASSWORD and CADDY_PASSWORD_HASH into the repo-root .env
(creating them, or replacing existing values). Prints only a confirmation -- never
the password or the hash.

    python3 deploy/gen_caddy_password.py [username]

The password is 40 characters from a 62-symbol alphabet, drawn from Python's
`secrets` module (a CSPRNG). The hash is bcrypt, which is what Caddy's
`basic_auth` directive expects.
"""
import secrets
import string
import sys
from pathlib import Path

import bcrypt

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
ALPHABET = string.ascii_letters + string.digits
LENGTH = 40


def set_env(name, value, lines):
    prefix = name + "="
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = prefix + value + "\n"
            return
    lines.append(prefix + value + "\n")


def main():
    user = sys.argv[1] if len(sys.argv) > 1 else "admin"
    password = "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
    digest = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    lines = ENV_FILE.read_text().splitlines(keepends=True) if ENV_FILE.exists() else []
    set_env("CADDY_USER", user, lines)
    set_env("CADDY_PASSWORD", password, lines)
    set_env("CADDY_PASSWORD_HASH", digest, lines)
    ENV_FILE.write_text("".join(lines))
    ENV_FILE.chmod(0o600)

    print(f"wrote CADDY_USER, CADDY_PASSWORD and CADDY_PASSWORD_HASH to {ENV_FILE}")
    print(f"username: {user}")
    print(f"password: stored in {ENV_FILE} (not printed) -- read it with:  grep '^CADDY_PASSWORD=' {ENV_FILE}")


if __name__ == "__main__":
    main()
