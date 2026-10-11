"""Generate a demo artifact set into the project's `_artifacts` directory.

Run from the repo root:

    python3 artifactfactory/examples/generate_demo.py

This uses the default configuration, so artifacts are written under
`<repo>/_artifacts/plans/<plan-id>/...` and state is kept in
`<repo>/_artifactfactory-data/state.json`.
"""
import os
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from artifactfactory.config import Config
from artifactfactory.service import Service


def main() -> None:
    config = Config.from_env()
    service = Service(config)

    result = service.add_idea("A homomorphic encryption toolkit for cloud analytics.")
    plan_id = result["plan"]["id"]
    print(f"artifacts dir: {config.artifacts_dir}")
    print(f"plan:          {plan_id}")

    job = service.start_implementation(plan_id)
    while True:
        job = service.get_job(job["id"])
        if job["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    print(f"job:           {job['status']}")

    for artifact in service.get_plan(plan_id)["artifacts"]:
        print(f"  - {artifact['type']}: {artifact['uri']}")


if __name__ == "__main__":
    main()
