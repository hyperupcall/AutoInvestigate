.PHONY: setup up down test smoke logs
# All keys/settings come from the single root .env.
DC = docker compose -f ../docker-compose.yml --env-file ../.env
setup: ; ./setup.sh
up:    ; $(DC) up -d --build slim agent_host web && echo "Open http://localhost:8090"
down:  ; $(DC) --profile run down
test:  ; uv run --no-project --python 3.13 --with httpx==0.28.1 --with pytest --with jsonschema python -m pytest tests -q
smoke: ; $(DC) exec -T web python -m scripts.live_smoke
logs:  ; $(DC) logs -f agent_host web
