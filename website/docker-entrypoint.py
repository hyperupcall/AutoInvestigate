"""Docker entrypoint: fix bind-mount ownership, then drop to the host user.

Docker creates a bind-mount source directory as **root** when it does not already
exist. A container that then runs as the host user cannot write to it, so the app
fails with "Permission denied" (for example creating `logs/runs`) or "unable to open
database file" (SQLite).

This entrypoint fixes that the standard way: when it starts as root it makes each
directory in `CHOWN_DIRS` (colon-separated) and `ID_DATA_DIR`, chowns it — and anything
already in it — to `HOST_UID:HOST_GID`, and then drops to that user before running the
command. Files written to the mounted dirs therefore stay owned by you on the host, not
by root.

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


def _dirs() -> list:
    """Every directory to fix: CHOWN_DIRS (colon-separated) plus the ideation data dir."""
    dirs = [d for d in os.environ.get("CHOWN_DIRS", "").split(":") if d]
    data_dir = os.environ.get("ID_DATA_DIR")
    if data_dir:
        dirs.append(data_dir)
    return dirs


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("docker-entrypoint: no command given")

    uid = int(os.environ.get("HOST_UID", "0") or "0")
    gid = int(os.environ.get("HOST_GID", "0") or "0")

    if os.geteuid() == 0:
        for path in _dirs():
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