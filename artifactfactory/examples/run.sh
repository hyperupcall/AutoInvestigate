#!/bin/sh
# Run the end-to-end smoke test (starts a throwaway daemon, adds an idea,
# implements it, downloads the tarball, then shuts the daemon down).
set -e

DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$DIR/../.." && pwd)

cd "$ROOT"
exec sh artifactfactory/examples/smoke.sh "$@"
