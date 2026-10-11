#!/usr/bin/env bash
# Run the containers as the invoking user, so files they write into the mounted
# directories (logs/, council_results/, website/data/, _artifacts/, ...) stay
# owned by you instead of root. This overrides any value in .env.
export HOST_UID="$(id -u)" HOST_GID="$(id -g)"
docker compose up --build --remove-orphans
