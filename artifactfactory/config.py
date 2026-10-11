import os
from dataclasses import dataclass

# The project root is the directory that contains the `artifactfactory` package.
# Defaults are anchored here so artifacts always land in the same place no
# matter which directory the daemon is started from.
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(PACKAGE_DIR)

DEFAULT_DATA_DIR = os.path.join(PROJECT_ROOT, "_artifactfactory-data")
DEFAULT_ARTIFACTS_DIR = os.path.join(PROJECT_ROOT, "_artifacts")
# The frontend static site (dashboard page + shared css/js). Mounted read-only
# into the container at /app/frontend; defaults to <repo>/website/frontend locally.
DEFAULT_FRONTEND_DIR = os.path.join(PROJECT_ROOT, "website", "frontend")


def load_env_file(path: str = None) -> None:
    """Load the single root .env (docker compose injects it too). Existing vars win.

    The daemon reads OPENROUTER_API_KEY / AF_* at call time, so loading this before the
    first build means `python3 -m artifactfactory.daemon` generates real artifacts, not
    just `run.sh` (which sources .env) or docker compose (which uses env_file).
    """
    path = path or os.path.join(PROJECT_ROOT, ".env")
    if not os.path.isfile(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key:
                os.environ.setdefault(key, value.strip().strip('"').strip("'"))


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8080
    data_dir: str = DEFAULT_DATA_DIR          # where state.json lives
    artifacts_dir: str = DEFAULT_ARTIFACTS_DIR  # where generated artifacts live
    storage_backend: str = "local"   # "local" | "s3"
    s3_bucket: str = ""
    s3_prefix: str = ""
    frontend_dir: str = DEFAULT_FRONTEND_DIR  # where the dashboard page lives
    run_host: str = "127.0.0.1"  # bind host for a run artifact server (AF_RUN_HOST)

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            host=os.environ.get("AF_HOST", "127.0.0.1"),
            port=int(os.environ.get("AF_PORT", "8080")),
            data_dir=os.environ.get("AF_DATA_DIR", DEFAULT_DATA_DIR),
            artifacts_dir=os.environ.get("AF_ARTIFACTS_DIR", DEFAULT_ARTIFACTS_DIR),
            storage_backend=os.environ.get("AF_STORAGE", "local"),
            s3_bucket=os.environ.get("AF_S3_BUCKET", ""),
            s3_prefix=os.environ.get("AF_S3_PREFIX", ""),
            frontend_dir=os.environ.get("AF_FRONTEND_DIR", DEFAULT_FRONTEND_DIR),
            run_host=os.environ.get("AF_RUN_HOST", "127.0.0.1"),
        )
