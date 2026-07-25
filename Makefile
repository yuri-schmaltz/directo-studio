# Directo — Developer convenience targets
# Run `make` (or `make help`) to list everything.

.DEFAULT_GOAL := help

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# `make start` (the default) runs the **local** mode (no Docker required):
# it builds a .venv, installs backend + UI deps, and brings both up in the
# background. Use `make start-docker` for the original Docker flow.
UI_URL        := http://localhost:3000
API_URL       := http://localhost:8000

# ----- help -----------------------------------------------------------------

.PHONY: help
help: ## Show this help (default target)
	@awk 'BEGIN {FS = ":.*## "; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} \
	/^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2} \
	END {printf "\n"}' $(MAKEFILE_LIST)

# ----- local stack (default; no Docker) ------------------------------------

.PHONY: start
start: ## Bootstrap + start the local stack (venv + node_modules + both services)
	@./start.sh

.PHONY: stop
stop: ## Stop the local stack (keeps venv, node_modules, and SQLite data)
	@./stop.sh

.PHONY: restart
restart: ## Restart the local stack
	@./stop.sh || true
	@./start.sh

.PHONY: logs
logs: ## Tail both local log files (Ctrl+C to exit)
	@./logs.sh

.PHONY: logs-api
logs-api: ## Tail only the backend log
	@tail -F .directo-backend.log

.PHONY: logs-ui
logs-ui: ## Tail only the frontend log
	@tail -F .directo-frontend.log

.PHONY: ps-local
ps-local: ## Show local PIDs and which ports are bound
	@printf 'backend  pid: ';  cat .directo-backend.pid  2>/dev/null || echo '(not running)'
	@printf 'frontend pid: '; cat .directo-frontend.pid 2>/dev/null || echo '(not running)'
	@command -v lsof >/dev/null 2>&1 && \
		lsof -iTCP:8000 -sTCP:LISTEN 2>/dev/null | tail -n +2 | sed 's/^/api    /' && \
		lsof -iTCP:3000 -sTCP:LISTEN 2>/dev/null | tail -n +2 | sed 's/^/ui     /' || true

.PHONY: prune-local
prune-local: ## ⚠ Wipe .venv, node_modules, SQLite data, pid and log files (irreversible)
	@read -p "This will DELETE the local venv, node_modules, and SQLite data. Continue? [y/N] " ans && [ "$$ans" = "y" ] || (echo "aborted" && exit 1)
	@./stop.sh || true
	@rm -rf .venv ui/node_modules directo_data .directo-backend.pid .directo-frontend.pid .directo-backend.log .directo-frontend.log
	@echo "local artefacts wiped"

# ----- docker stack (alternative; requires Docker) --------------------------

.PHONY: start-docker
start-docker: ## Build, start the Docker stack and open the UI in your browser
	@./start-docker.sh

.PHONY: stop-docker
stop-docker: ## Stop the Docker stack (keeps volumes and SQLite data)
	docker compose down

.PHONY: restart-docker
restart-docker: ## Restart the running Docker containers (no rebuild)
	docker compose restart

.PHONY: rebuild
rebuild: ## Tear down and rebuild Docker images from scratch
	docker compose down
	docker compose up --build -d

.PHONY: logs-docker
logs-docker: ## Follow Docker logs from all services
	docker compose logs -f --tail=100

.PHONY: ps
ps: ## Show running Docker containers
	docker compose ps

.PHONY: shell-api
shell-api: ## Open a bash shell inside the API container
	docker compose exec api bash

.PHONY: shell-ui
shell-ui: ## Open a sh shell inside the UI container
	docker compose exec ui sh

.PHONY: clean
clean: ## Stop Docker containers and remove the default network (keeps volumes)
	docker compose down

.PHONY: prune
prune: ## ⚠ Stop Docker AND delete the SQLite volume (irreversible)
	@read -p "This will DELETE all Directo Docker data. Continue? [y/N] " ans && [ "$$ans" = "y" ] || (echo "aborted" && exit 1)
	docker compose down -v
	docker system prune -f

# ----- browser + health -----------------------------------------------------

.PHONY: browser
browser: ## Open the UI in the default browser
	@if grep -qi microsoft /proc/version 2>/dev/null; then \
		powershell.exe /c start $(UI_URL) > /dev/null 2>&1 || true; \
	else \
		xdg-open $(UI_URL) > /dev/null 2>&1 || true; \
	fi

.PHONY: health
health: ## Curl /health on the API
	@curl -sS $(API_URL)/health || true
	@echo

# ----- tests ----------------------------------------------------------------

.PHONY: test
test: ## Run the Python test suite (213 tests) inside the local venv
	@if [ ! -x .venv/bin/python ]; then echo "no .venv — run \`make start\` first"; exit 1; fi
	.venv/bin/pytest -q

.PHONY: test-ui
test-ui: ## Run the Next.js test suite inside the UI container
	docker compose exec ui npm test --silent
