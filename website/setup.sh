#!/usr/bin/env bash
# One-command setup for the evaluation backend.
#   ./setup.sh            check Docker, write the root .env (asks for the OpenRouter key once), start the SLIM bus,
#                         one AGNTCY agent process per evaluator, and the web app; wait until all agents are online
#   SKIP_SMOKE=1 ./setup.sh   skip the final one-call-per-model check (costs well under $0.001)
# Safe to run again at any time; it keeps the root .env and only rebuilds what changed.
set -euo pipefail
cd "$(dirname "$0")"

# The single root .env holds every key and shared setting (see ../.env.example).
ENV_FILE=../.env

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mok\033[0m  %s\n' "$*"; }
fail() { printf '\n\033[31mSetup stopped: %s\033[0m\n' "$*" >&2; exit 1; }
get_var() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- || true; }
set_var() {  # portable in-place edit (no sed -i differences between macOS and Linux)
  local tmp; tmp=$(mktemp); grep -v "^$1=" "$ENV_FILE" > "$tmp" || true; printf '%s=%s\n' "$1" "$2" >> "$tmp"; mv "$tmp" "$ENV_FILE"
}
dc() { docker compose -f ../docker-compose.yml --env-file "$ENV_FILE" "$@"; }

bold "1/6  Docker"
command -v docker >/dev/null || fail "Docker is not installed. Install Docker Desktop (Mac/Windows) or Docker Engine with the compose plugin (Linux)."
docker compose version >/dev/null 2>&1 || fail "'docker compose' is missing. Install the Docker Compose plugin."
docker info >/dev/null 2>&1 || fail "Docker is installed but not running (or your user can't reach it). Start Docker and run ./setup.sh again."
ok "$(docker --version)"

bold "2/6  Configuration ($ENV_FILE)"
[ -f "$ENV_FILE" ] || { cp ../.env.example "$ENV_FILE"; ok "created $ENV_FILE from ../.env.example"; }
key=$(get_var OPENROUTER_API_KEY)
if [[ "$key" != sk-or-* ]]; then
  if [[ "${OPENROUTER_API_KEY:-}" == sk-or-* ]]; then key=$OPENROUTER_API_KEY
  else read -rsp "  Paste your OpenRouter API key (starts with sk-or-, input hidden): " key; echo; fi
  [[ "$key" == sk-or-* ]] || fail "That doesn't look like an OpenRouter key (it should start with sk-or-)."
  set_var OPENROUTER_API_KEY "$key"
fi
secret=$(get_var SLIM_SHARED_SECRET)
if [ -z "$secret" ] || [[ "$secret" == *REPLACE* ]]; then
  set_var SLIM_SHARED_SECRET "$(openssl rand -hex 24 2>/dev/null || head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  ok "generated a SLIM shared secret"
fi
[ -n "$(get_var SLIM_SERVER)" ] || set_var SLIM_SERVER slim:46357
set_var HOST_UID "$(id -u)"; set_var HOST_GID "$(id -g)"   # so files the app writes stay owned by you
chmod 600 "$ENV_FILE"
ok "$ENV_FILE ready (it is gitignored; never commit it)"

bold "3/6  OpenRouter key"
code=$(curl -s -o /tmp/or_key.$$ -w '%{http_code}' -H "Authorization: Bearer $(get_var OPENROUTER_API_KEY)" https://openrouter.ai/api/v1/key || echo 000)
[ "$code" = 200 ] || { rm -f /tmp/or_key.$$; fail "OpenRouter rejected the key (HTTP $code). Fix OPENROUTER_API_KEY in $ENV_FILE and run again."; }
ok "key accepted ($(grep -o '"usage":[0-9.]*' /tmp/or_key.$$ | head -1 | cut -d: -f2 | xargs printf 'used $%s so far' 2>/dev/null || echo valid))"
rm -f /tmp/or_key.$$

bold "4/6  Ports 8090 (app) and 46357 (SLIM)"
if [ -z "$(dc ps -q web 2>/dev/null)" ]; then
  for p in 8090 46357; do
    if (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null; then fail "port $p is already in use by another program. Free it and run again."; fi
  done
fi
ok "free"
[ -f frontend/index.html ] && ok "frontend found at frontend (served at http://localhost:8090/)" \
  || ok "no frontend next to this folder; the live view will be the home page"

bold "5/6  Building and starting (the first build takes a few minutes)"
mkdir -p data ../logs council_results
dc up -d --build slim agent_host web
want=$(dc exec -T web python -c "from deliberation import settings; s=settings.load(); print(len({a['id'] for g in s['groups'] for a in g['agents']}))")
printf '  waiting for %s agents to register on SLIM ' "$want"
for i in $(seq 1 90); do
  ready=$(dc logs agent_host 2>/dev/null | grep -c "agent ready" || true)
  [ "$ready" -ge "$want" ] && break
  printf '.'; sleep 2
done
echo
[ "$ready" -ge "$want" ] || fail "only $ready of $want agents came online. See: docker compose logs agent_host"
for i in $(seq 1 30); do curl -s -o /dev/null http://localhost:8090/api/status && break; sleep 1; done
curl -s -o /dev/null http://localhost:8090/api/status || fail "the web app is not answering. See: docker compose logs web"
ok "$want agents online, each its own AGNTCY/SLIM endpoint (deliberation/agents/<id>)"

bold "6/6  One tiny call to every configured model"
if [ "${SKIP_SMOKE:-0}" = 1 ]; then ok "skipped"; else
  dc exec -T web python -m scripts.live_smoke | tail -4
fi

bold "Done"
cat <<MSG
  App (AutoInvestigate frontend)   http://localhost:8090/
  Live three-column view           http://localhost:8090/live
  Settings (models, agents, keys)  the Settings popup in the app header
  Logs                              docker compose logs -f agent_host web   (from the repo root)
  Stop everything                   docker compose down                     (from the repo root)
MSG
