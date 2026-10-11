# Convenience wrapper around the per-directory run.sh scripts.
#
# Every target cd's into the right directory before running its run.sh, so you
# can drive the whole project from the repo root. Extra flags can be passed
# through with ARGS, e.g.:
#
#   make backend ARGS="--port 9000"
#
# Run `make` or `make help` to list everything.

SHELL := /bin/sh
.DEFAULT_GOAL := help

.PHONY: help run backend frontend evalreport examples tests js components css daemon smoke test

help: ## Show this help
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-11s %s\n", $$1, $$2}'

run: ## Run the whole stack (backend + frontend) from the repo root
	cd "$(CURDIR)" && ./run.sh $(ARGS)

backend: ## Run the Artifact Factory backend daemon
	cd artifactfactory && ./run.sh $(ARGS)

frontend: ## Serve the frontend static site
	cd frontend && ./run.sh $(ARGS)

evalreport: ## Run the Outshift Research Intelligence Streamlit app
	cd evalreport && ./run.sh $(ARGS)

examples: ## Run the backend end-to-end smoke test
	cd artifactfactory/examples && ./run.sh $(ARGS)

tests: ## Run the backend unit tests
	cd artifactfactory/tests && ./run.sh $(ARGS)

js: ## Syntax-check the frontend JavaScript
	cd frontend/js && ./run.sh $(ARGS)

components: ## Syntax-check the frontend component JavaScript
	cd frontend/js/components && ./run.sh $(ARGS)

css: ## Sanity-check the frontend CSS
	cd frontend/css && ./run.sh $(ARGS)

# Aliases (not listed in help).
daemon: backend
smoke: examples
test: tests
