.PHONY: up hello round0 demo test down logs
PACE ?= 4
up:    ; docker compose --profile run build moderator && docker compose up -d --build frontend runner slim tech_risk market cisco_fit horizon security_expert customer_voice specialist_on_demand
hello: up ; sleep 8 && : > logs/events.jsonl && docker compose run --rm moderator
round0: up ; sleep 8 && : > logs/events.jsonl && docker compose run --rm moderator python -m moderator.main round0
down:  ; docker compose --profile run down
logs:  ; docker compose logs -f tech_risk market cisco_fit horizon
test: ; docker compose run --rm --no-deps -v $(PWD)/tests:/app/tests moderator python tests/test_tally.py
demo: up
	sleep 8
	docker compose restart tech_risk market cisco_fit horizon security_expert customer_voice specialist_on_demand
	sleep 8
	: > logs/events.jsonl
	docker compose run --rm -e PACE=$(PACE) moderator python -m moderator.main negotiate
start: up
	@echo "Open http://localhost:8090 and press 'Reset and run'"
