"""Docker entrypoint for the ideation daemon.

Docker creates a bind-mount source directory as **root** when it does not already
exist. A container that then runs as the host user cannot write to it, so SQLite
fails with "unable to open database file".

This entrypoint fixes that the standard way: when it starts as root it makes the
data directory, chowns it (and anything already in it) to HOST_UID:HOST_GID, and
then drops to that user before running the command. The database therefore ends up
owned by you on the host, not by root.

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
    data_dir = os.environ.get("ID_DATA_DIR", "/app/_ideation-data")

    if os.geteuid() == 0:
        os.makedirs(data_dir, exist_ok=True)
        _chown_tree(data_dir, uid, gid)
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
