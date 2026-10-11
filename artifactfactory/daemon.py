import argparse
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from artifactfactory.config import Config, load_env_file

# Load the single root .env before importing the modules that read it at import time
# (mvp/evaluation read AF_MVP_MODEL / AF_MODEL / AF_EVAL_API when they are imported).
load_env_file()

from artifactfactory.api import serve


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Artifact Factory daemon")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--data-dir")
    parser.add_argument("--artifacts-dir")
    parser.add_argument("--storage", choices=["local", "s3"])
    parser.add_argument("--s3-bucket")
    parser.add_argument("--s3-prefix")
    parser.add_argument("--frontend-dir")
    args = parser.parse_args(argv)

    config = Config.from_env()
    if args.host is not None:
        config.host = args.host
    if args.port is not None:
        config.port = args.port
    if args.data_dir is not None:
        config.data_dir = args.data_dir
    if args.artifacts_dir is not None:
        config.artifacts_dir = args.artifacts_dir
    if args.storage is not None:
        config.storage_backend = args.storage
    if args.s3_bucket is not None:
        config.s3_bucket = args.s3_bucket
    if args.s3_prefix is not None:
        config.s3_prefix = args.s3_prefix
    if args.frontend_dir is not None:
        config.frontend_dir = args.frontend_dir

    serve(config)


if __name__ == "__main__":
    main()
