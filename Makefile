# Directo — Developer convenience targets
# Run `make` (or `make help`) to list everything.

.DEFAULT_GOAL := help

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

COMPOSE       := docker compose
UI_URL        := http://localhost:3000
API_URL       := http://localhost:8000

# ----- help -----------------------------------------------------------------

.PHONY: help
help: ## Show this help (default target)
	@awk 'BEGIN {FS = ":.*## "; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} \
	/^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2} \
	END {printf "\n"}' $(MAKEFILE_LIST)

# ----- stack lifecycle ------------------------------------------------------

.PHONY: start
start: ## Build, start the stack and open the UI in your default browser
	@./start.sh

.PHONY: stop
stop: ## Stop the stack (keeps volumes and SQLite data)
	$(COMPOSE) down

.PHONY: restart
restart: ## Restart the running containers (no rebuild)
	$(COMPOSE) restart

.PHONY: rebuild
rebuild: ## Tear down and rebuild images from scratch
	$(COMPOSE) down
	$(COMPOSE) up --build -d

.PHONY: ps
ps: ## Show running containers
	$(COMPOSE) ps

# ----- logs -----------------------------------------------------------------

.PHONY: logs
logs: ## Follow logs from all services (Ctrl+C to exit)
	$(COMPOSE) logs -f --tail=100

.PHONY: logs-api
logs-api: ## Follow only the API logs
	$(COMPOSE) logs -f --tail=100 api

.PHONY: logs-ui
logs-ui: ## Follow only the UI logs
	$(COMPOSE) logs -f --tail=100 ui

# ----- access ---------------------------------------------------------------

.PHONY: browser
browser: ## Open the UI in the default browser
	@if grep -qi microsoft /proc/version 2>/dev/null; then \
		powershell.exe /c start $(UI_URL) > /dev/null 2>&1 || true; \
	else \
		xdg-open $(UI_URL) > /dev/null 2>&1 || true; \
	fi

.PHONY: shell-api
shell-api: ## Open a bash shell inside the API container
	$(COMPOSE) exec api bash

.PHONY: shell-ui
shell-ui: ## Open a sh shell inside the UI container
	$(COMPOSE) exec ui sh

.PHONY: health
health: ## Curl /health on the API
	@curl -sS $(API_URL)/health || true
	@echo

# ----- cleanup --------------------------------------------------------------

.PHONY: clean
clean: ## Stop containers and remove the default network (keeps volumes)
	$(COMPOSE) down

.PHONY: prune
prune: ## ⚠ Stop everything AND delete the SQLite volume (irreversible)
	@read -p "This will DELETE all Directo data. Continue? [y/N] " ans && [ "$$ans" = "y" ] || (echo "aborted" && exit 1)
	$(COMPOSE) down -v
	docker system prune -f

# ----- tests ----------------------------------------------------------------

.PHONY: test
test: ## Run the Python test suite (213 tests)
	pytest -q

.PHONY: test-ui
test-ui: ## Run the Next.js test suite inside the UI container
	$(COMPOSE) exec ui npm test --silent
