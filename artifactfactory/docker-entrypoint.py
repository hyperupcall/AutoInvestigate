"""Docker entrypoint for the Artifact Factory: fix bind-mount ownership, then drop to
the host user.

Docker creates a bind-mount source directory as **root** when it does not already
exist, so a container running as the host user cannot write to it. This makes each
directory in `CHOWN_DIRS` (colon-separated), chowns it — and anything already in it —
to `HOST_UID:HOST_GID`, then drops to that user before running the command. See
website/docker-entrypoint.py for the full explanation.

If it is not started as root (for example when `user:` is set), it just runs the
command unchanged.
"""
import os
import sys


def _chown_tree(path: str, uid: int, gid: int) -> None:
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                os.chown(os.path.join(root, name), uid, gid)
            except OSError:
                pass
    try:
        os.chown(path, uid, gid)
    except OSError:
        pass


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("docker-entrypoint: no command given")

    uid = int(os.environ.get("HOST_UID", "0") or "0")
    gid = int(os.environ.get("HOST_GID", "0") or "0")

    if os.geteuid() == 0:
        for path in [d for d in os.environ.get("CHOWN_DIRS", "").split(":") if d]:
            try:
                os.makedirs(path, exist_ok=True)
                _chown_tree(path, uid, gid)
            except OSError as exc:  # a read-only or missing mount must not stop the service
                print(f"docker-entrypoint: could not fix {path}: {exc}", file=sys.stderr)
        if uid or gid:
            try:
                os.setgroups([])
            except OSError:
                pass
            os.setgid(gid)
            os.setuid(uid)

    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()