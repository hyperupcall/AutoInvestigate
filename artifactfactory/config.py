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
        )
