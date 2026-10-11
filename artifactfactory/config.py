from dataclasses import dataclass
import os


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8080
    data_dir: str = "./artifactfactory-data"
    storage_backend: str = "local"   # "local" | "s3"
    s3_bucket: str = ""
    s3_prefix: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            host=os.environ.get("AF_HOST", "127.0.0.1"),
            port=int(os.environ.get("AF_PORT", "8080")),
            data_dir=os.environ.get("AF_DATA_DIR", "./artifactfactory-data"),
            storage_backend=os.environ.get("AF_STORAGE", "local"),
            s3_bucket=os.environ.get("AF_S3_BUCKET", ""),
            s3_prefix=os.environ.get("AF_S3_PREFIX", ""),
        )
