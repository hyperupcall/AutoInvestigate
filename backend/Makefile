.PHONY: setup up down test smoke logs
setup: ; ./setup.sh
up:    ; docker compose up -d --build slim agent_host web && echo "Open http://localhost:8090"
down:  ; docker compose --profile run down
test:  ; uv run --no-project --python 3.13 --with httpx==0.28.1 --with pytest --with jsonschema python -m pytest tests -q
smoke: ; docker compose exec -T web python -m scripts.live_smoke
logs:  ; docker compose logs -f agent_host web
