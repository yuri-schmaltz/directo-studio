#!/usr/bin/env bash
# Directo stack bootstrapper — Docker mode.
# - Cleans up any half-stopped containers from previous runs (`docker compose down`)
# - Verifies that ports 3000 (UI) and 8000 (API) are free, otherwise fails FAST
#   with a clear "this is what's holding the port" message, instead of waiting
#   78s for a build to fail on `Bind for 0.0.0.0:XXXX failed: port is already
#   allocated`.
# - Builds images, starts containers in the background
# - Waits for both API and UI healthchecks to pass
# - Opens the UI in the default browser (handles WSL too)
#
# This is the Docker-mode flow. The default `./start.sh` is the local-mode
# (no-Docker) bootstrapper — use this script if you specifically want Docker.
#
set -euo pipefail

cd "$(dirname "$0")"

UI_URL="http://localhost:3000"
API_URL="http://localhost:8000"
API_PORT="${DIRECTO_API_PORT:-8000}"
UI_PORT="${DIRECTO_UI_PORT:-3000}"
TIMEOUT_SECONDS="${DIRECTO_START_TIMEOUT:-180}"

# ----- pretty output -------------------------------------------------------
log()  { printf '\033[1;36m→\033[0m %s\n' "$*"; }
ok()   { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[1;33m!\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
hr()   { printf '\033[2m%s\033[0m\n' "----------------------------------------------------------"; }

# ----- buildx fallback -----------------------------------------------------
# Docker Compose v2.20+ uses Bake as the default build backend. If the host
# doesn't have buildx installed, the build still works but prints a noisy
# "buildx isn't installed" warning. Detect once and disable Bake so the
# output stays clean. Users with a working buildx setup still get Bake.
if ! docker buildx version >/dev/null 2>&1; then
    warn "docker buildx not installed — falling back to the classic builder (COMPOSE_BAKE=false)"
    export COMPOSE_BAKE=false
fi

# ----- pre-flight: stop any half-stopped containers from a previous run ----
log "Stopping any previous Directo containers (docker compose down)..."
docker compose down --remove-orphans >/dev/null 2>&1 || true
ok "previous containers cleaned up"

# ----- pre-flight: port check ---------------------------------------------
# Fail fast (before the 78s build) if the dev ports are already bound by
# something we don't manage. Without this, the failure shows up at the very
# end of the build as "Bind for 0.0.0.0:8000 failed: port is already
# allocated" with no hint about what's holding the port.
check_port_free() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        local pids
        pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            return 1
        fi
    elif command -v ss >/dev/null 2>&1; then
        if ss -tlnH "sport = :$port" 2>/dev/null | grep -q LISTEN; then
            return 1
        fi
    fi
    return 0
}

if ! check_port_free "$API_PORT"; then
    hr
    fail "port $API_PORT is already in use. The Docker api container cannot bind it.

Likely culprits:
  - a local-mode ./start.sh backend is still running. Run ./stop.sh to stop it.
  - a previous docker compose stack that didn't clean up. Run: docker compose down
  - some other process on this host. Identify it with: lsof -i :$API_PORT

If you are sure the port is supposed to be free, free it manually and re-run."
fi
ok "port $API_PORT (API) is free"

if ! check_port_free "$UI_PORT"; then
    hr
    fail "port $UI_PORT is already in use. The Docker ui container cannot bind it.

Likely culprits:
  - a local-mode ./start.sh frontend is still running. Run ./stop.sh to stop it.
  - a previous docker compose stack that didn't clean up. Run: docker compose down
  - some other process on this host. Identify it with: lsof -i :$UI_PORT

If you are sure the port is supposed to be free, free it manually and re-run."
fi
ok "port $UI_PORT (UI) is free"

# ----- main ----------------------------------------------------------------
log "Building and starting the Directo stack (docker compose up --build -d)..."
docker compose up --build -d

log "Waiting for API at $API_URL/health (timeout: ${TIMEOUT_SECONDS}s)..."
elapsed=0
until curl -sf "$API_URL/health" > /dev/null 2>&1; do
    if [ "$elapsed" -ge "$TIMEOUT_SECONDS" ]; then
        fail "API did not become healthy in time. Last 50 log lines:
$(docker compose logs --tail=50 api)"
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done
ok "API is healthy"

log "Waiting for UI at $UI_URL/ (timeout: ${TIMEOUT_SECONDS}s)..."
elapsed=0
until curl -sf "$UI_URL/" > /dev/null 2>&1; do
    if [ "$elapsed" -ge "$TIMEOUT_SECONDS" ]; then
        fail "UI did not become reachable in time. Last 50 log lines:
$(docker compose logs --tail=50 ui)"
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done
ok "UI is reachable"

log "Opening $UI_URL in your browser..."

# Detect WSL (Windows Subsystem for Linux) and route to the Windows host browser.
if grep -qi microsoft /proc/version 2>/dev/null; then
    powershell.exe /c start "" "$UI_URL" > /dev/null 2>&1 || true
else
    xdg-open "$UI_URL" > /dev/null 2>&1 || true
fi

hr
ok "Directo is running (Docker mode)!"
hr
echo "  • UI:   $UI_URL"
echo "  • API:  $API_URL"
echo "  • Docs: $API_URL/docs"
echo
echo "Useful commands:"
echo "  ./stop-docker.sh   # stop the stack (keeps the SQLite volume)"
echo "  make logs-docker   # follow container logs (Ctrl+C to exit)"
echo "  make shell-api     # bash into the API container"
echo "  make stop-docker   # same as ./stop-docker.sh (Make target)"
