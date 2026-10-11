.PHONY: up hello round0 demo test down logs
# All keys/settings come from the single root .env.
DC = docker compose --env-file ../../.env
PACE ?= 4
up:    ; $(DC) --profile run build moderator && $(DC) up -d --build frontend runner slim tech_risk market cisco_fit horizon security_expert customer_voice specialist_on_demand
hello: up ; sleep 8 && : > logs/events.jsonl && $(DC) run --rm moderator
round0: up ; sleep 8 && : > logs/events.jsonl && $(DC) run --rm moderator python -m moderator.main round0
down:  ; $(DC) --profile run down
logs:  ; $(DC) logs -f tech_risk market cisco_fit horizon
test: ; $(DC) run --rm --no-deps -v $(PWD)/tests:/app/tests moderator python tests/test_tally.py
demo: up
	sleep 8
	$(DC) restart tech_risk market cisco_fit horizon security_expert customer_voice specialist_on_demand
	sleep 8
	: > logs/events.jsonl
	$(DC) run --rm -e PACE=$(PACE) moderator python -m moderator.main negotiate
start: up
	@echo "Open http://localhost:8090 and press 'Reset and run'"
