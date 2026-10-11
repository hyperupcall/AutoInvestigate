#!/usr/bin/env bash
#
# One-time setup for the Vultr droplet. Run it as root:
#
#   ssh -i deploy/keys/vultr_deploy root@<droplet> 'bash -s' < deploy/server-setup.sh
#
# It installs Docker + the compose plugin, creates the deploy user, adds it to
# the docker group, and gives it the same SSH key root already has.
#
#   DEPLOY_USER   the user CI will SSH as   (default: deploy)
#
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"

echo "==> installing Docker + compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || { echo "error: compose plugin missing" >&2; exit 1; }

echo "==> creating user '$DEPLOY_USER'"
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
fi
usermod -aG docker "$DEPLOY_USER"

echo "==> installing the SSH key for '$DEPLOY_USER'"
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh"
if [ -f /root/.ssh/authorized_keys ]; then
  cp /root/.ssh/authorized_keys "/home/$DEPLOY_USER/.ssh/authorized_keys"
  chown "$DEPLOY_USER:$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh/authorized_keys"
  chmod 600 "/home/$DEPLOY_USER/.ssh/authorized_keys"
fi

echo "==> done"
docker --version
docker compose version
id "$DEPLOY_USER"
