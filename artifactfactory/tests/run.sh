#!/bin/sh
# Run the Artifact Factory unit tests.
set -e

DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$DIR/../.." && pwd)

cd "$ROOT"
exec python3 -m unittest discover -s artifactfactory -t . -v
