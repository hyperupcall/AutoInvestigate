"""Entry point for the ideation daemon.

    python -m ideation.daemon            # from website/
    python website/ideation/daemon.py    # from the repo root

Opens the SQLite store, seeds the default watchlist on first run, starts the
scheduler (unless ID_AUTOSTART=0) and serves the API + Ideation View.
"""
import argparse
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ideation.api import serve
from ideation.config import Config
from ideation.scheduler import Scheduler
from ideation.service import Service
from ideation.store import Store
from ideation.topics import seed_if_empty


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Ideation Collective daemon")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--data-dir")
    parser.add_argument("--frontend-dir")
    parser.add_argument("--poll-interval", type=int)
    parser.add_argument("--no-autostart", action="store_true", help="do not start the scheduler")
    args = parser.parse_args(argv)

    config = Config.from_env()
    if args.host is not None:
        config.host = args.host
    if args.port is not None:
        config.port = args.port
    if args.data_dir is not None:
        config.data_dir = args.data_dir
    if args.frontend_dir is not None:
        config.frontend_dir = args.frontend_dir
    if args.poll_interval is not None:
        config.poll_interval_seconds = args.poll_interval
    if args.no_autostart:
        config.autostart = False

    store = Store(config.db_path)
    service = Service(config, store)
    service.load_settings()  # persisted settings win over the environment
    added = seed_if_empty(store)
    if added:
        print(f"Seeded {added} default topics.")

    scheduler = Scheduler(service, service.config.poll_interval_seconds)
    if service.config.autostart:
        scheduler.start()
        print(f"Scheduler started (every {scheduler.interval}s).")

    serve(service.config, service, scheduler)


if __name__ == "__main__":
    main()
