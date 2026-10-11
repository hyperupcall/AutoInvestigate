#!/usr/bin/env bash
# Fix the "Permission denied" errors the Docker services hit.
#
# Docker creates a bind-mount source directory as root when it does not already exist.
# The containers run as you (HOST_UID:HOST_GID), so they cannot write to a root-owned
# directory. You then see errors like:
#
#   PermissionError: [Errno 13] Permission denied: 'logs/runs'
#   sqlite3.OperationalError: unable to open database file
#
# This script creates every directory the services mount and chowns it (recursively)
# to you, so the containers can write to it. Run it whenever you see a permission
# error, or before `docker compose up` on a fresh checkout.
#
#   ./fix-permissions.sh              # fix the mounted directories
#   ./fix-permissions.sh --restart    # ...and rebuild + restart the services
#   ./fix-permissions.sh --dry-run    # show what would change, change nothing
set -euo pipefail
cd "$(dirname "$0")"

UID_="$(id -u)"
GID_="$(id -g)"
RESTART=0
DRY=0
for arg in "$@"; do
  case "$arg" in
    --restart) RESTART=1 ;;
    --dry-run|-n) DRY=1 ;;
    -h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

# Every host directory a service bind-mounts (see docker-compose.yml).
DIRS=(
  logs
  website/data
  website/council_results
  _artifacts
  _artifactfactory-data
  _ideation-data
)

owner_of() {  # GNU stat first, then BSD/macOS stat
  stat -c '%u:%g' "$1" 2>/dev/null || stat -f '%u:%g' "$1" 2>/dev/null || echo '?'
}

changed=0
for d in "${DIRS[@]}"; do
  if [ ! -e "$d" ]; then
    echo "  create  $d"
    [ "$DRY" = 1 ] || mkdir -p "$d"
    changed=$((changed + 1))
    continue
  fi
  owner="$(owner_of "$d")"
  if [ "$owner" = "$UID_:$GID_" ]; then
    echo "  ok      $d"
    continue
  fi
  echo "  chown   $d  ($owner -> $UID_:$GID_)"
  changed=$((changed + 1))
  [ "$DRY" = 1 ] && continue
  if ! chown -R "$UID_:$GID_" "$d" 2>/dev/null; then
    echo "          needs root; retrying with sudo"
    sudo chown -R "$UID_:$GID_" "$d"
  fi
done

if [ "$DRY" = 1 ]; then
  echo "Dry run: $changed director$([ "$changed" = 1 ] && echo y || echo ies) would change."
  exit 0
fi

echo "Done: $changed director$([ "$changed" = 1 ] && echo y || echo ies) fixed."

if [ "$RESTART" = 1 ]; then
  echo "Rebuilding and restarting the services..."
  docker compose up -d --build
fi