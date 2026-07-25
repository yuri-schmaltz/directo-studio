#!/usr/bin/env bash
# Directo stack bootstrapper — local mode (no Docker required).
#
# This script does everything end-to-end on a fresh checkout:
#   1. Detects the OS / shell (Linux, macOS, WSL, native Windows Git Bash).
#   2. Creates a Python .venv and installs backend + API deps in editable mode.
#   3. Creates the SQLite data dir if missing.
#   4. Starts the FastAPI backend on :8000 in the background (logs → .directo-backend.log).
#   5. Runs `npm install` in ui/ if node_modules is missing.
#   6. Starts the Next.js dev server on :3000 in the background (logs → .directo-frontend.log).
#   7. Waits for both /health endpoints to come up.
#   8. Opens the UI in the default browser (handles WSL too).
#
# It is safe to re-run: existing venv/node_modules/data are reused; if a service
# is already up on its port it is left alone.
#
# Use the companion scripts:
#   ./stop.sh    — stop the local backend + frontend
#   ./logs.sh    — tail both log files
#
# For the Docker-based flow (the old behaviour), use:
#   ./start-docker.sh
#
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"

# ----- config (override via env) -------------------------------------------
API_PORT="${DIRECTO_API_PORT:-8000}"
UI_PORT="${DIRECTO_UI_PORT:-3000}"
API_HOST="${DIRECTO_API_HOST:-127.0.0.1}"
UI_HOST="${DIRECTO_UI_HOST:-127.0.0.1}"
API_URL="http://${API_HOST}:${API_PORT}"
UI_URL="http://${UI_HOST}:${UI_PORT}"
TIMEOUT_SECONDS="${DIRECTO_START_TIMEOUT:-180}"

DATA_DIR="${ROOT}/directo_data"
BACKEND_LOG="${ROOT}/.directo-backend.log"
FRONTEND_LOG="${ROOT}/.directo-frontend.log"
BACKEND_PID_FILE="${ROOT}/.directo-backend.pid"
FRONTEND_PID_FILE="${ROOT}/.directo-frontend.pid"
VENV_DIR="${ROOT}/.venv"

# ----- pretty output -------------------------------------------------------
log()  { printf '\033[1;36m→\033[0m %s\n' "$*"; }
ok()   { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[1;33m!\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
hr()   { printf '\033[2m%s\033[0m\n' "----------------------------------------------------------"; }

# ----- env detection -------------------------------------------------------
detect_env() {
    local uname_s
    uname_s="$(uname -s 2>/dev/null || echo unknown)"
    case "$uname_s" in
        Linux*)
            if grep -qi microsoft /proc/version 2>/dev/null; then
                OS="wsl"
            else
                OS="linux"
            fi
            ;;
        Darwin*)              OS="macos" ;;
        MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
        *)                    OS="unknown" ;;
    esac

    if command -v python3 >/dev/null 2>&1; then
        PY=python3
    elif command -v python >/dev/null 2>&1; then
        PY=python
    else
        fail "python3 (or python) not found in PATH. Install Python 3.11+ first."
    fi

    case "$OS" in
        windows) VENV_PY="${VENV_DIR}/Scripts/python.exe" ;;
        *)       VENV_PY="${VENV_DIR}/bin/python" ;;
    esac

    if command -v npm >/dev/null 2>&1; then
        NODE_OK=1
    else
        NODE_OK=0
    fi
}

# ----- helpers -------------------------------------------------------------
open_browser() {
    case "$OS" in
        linux)   xdg-open "$1"             >/dev/null 2>&1 || true ;;
        macos)   open "$1"                 >/dev/null 2>&1 || true ;;
        wsl)     powershell.exe /c start "" "$1" >/dev/null 2>&1 || true ;;
        windows) cmd.exe /c start "" "$1" >/dev/null 2>&1 || true ;;
        *)       warn "auto-open not supported on this OS; open $1 manually" ;;
    esac
}

wait_for() {
    local url="$1" name="$2" log_file="$3" elapsed=0
    while ! curl -sf "$url" >/dev/null 2>&1; do
        if [ "$elapsed" -ge "$TIMEOUT_SECONDS" ]; then
            hr
            printf '\033[1;31m✗ %s did not become healthy within %ss.\033[0m\n' \
                "$name" "$TIMEOUT_SECONDS" >&2
            printf 'Last 40 log lines from %s:\n' "$log_file" >&2
            hr >&2
            tail -n 40 "$log_file" 2>/dev/null >&2 || true
            hr >&2
            exit 1
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
}

# ----- main ----------------------------------------------------------------
detect_env

hr
log "Directo bootstrap (local mode, no Docker required)"
hr
echo "  repo:    $ROOT"
echo "  os:      $OS"
echo "  python:  $("$PY" --version 2>&1)"
echo "  venv:    $VENV_DIR"
echo "  api:     $API_URL"
echo "  ui:      $UI_URL"
echo

# 1. venv
if [ ! -x "$VENV_PY" ]; then
    log "Creating Python venv at $VENV_DIR"
    "$PY" -m venv "$VENV_DIR"
    ok "venv created"
else
    ok "venv already exists"
fi

# 2. backend deps (idempotent; pip no-ops when up to date)
log "Installing backend dependencies (editable + fastapi/uvicorn/click/httpx/websockets/streamlit)"
"$VENV_PY" -m pip install --upgrade pip --quiet
"$VENV_PY" -m pip install -e . fastapi 'uvicorn[standard]' click httpx websockets streamlit --quiet
ok "backend deps installed"

# 3. data dir
mkdir -p "$DATA_DIR"
ok "data dir ready: $DATA_DIR"

# 4. backend
if curl -sf "$API_URL/health" >/dev/null 2>&1; then
    ok "backend already responding on $API_URL (skipped)"
else
    log "Starting backend on $API_URL  (logs → .directo-backend.log)"
    : > "$BACKEND_LOG"
    nohup "$VENV_PY" -m directo.platform.cli --db-dir "$DATA_DIR" \
        server --host "$API_HOST" --port "$API_PORT" \
        >> "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
    wait_for "$API_URL/health" "Backend" "$BACKEND_LOG"
    ok "backend up (pid $(cat "$BACKEND_PID_FILE"))"
fi

# 5. UI deps
if [ "$NODE_OK" -eq 0 ]; then
    fail "npm not found. Install Node.js 18+ first: https://nodejs.org/"
fi
if [ ! -d "$ROOT/ui/node_modules" ]; then
    log "Installing UI dependencies (npm install in ui/)"
    ( cd "$ROOT/ui" && npm install --no-audit --no-fund --loglevel=error )
    ok "ui deps installed"
else
    ok "ui node_modules present"
fi

# 6. UI
if curl -sf "$UI_URL/" >/dev/null 2>&1; then
    ok "ui already responding on $UI_URL (skipped)"
else
    log "Starting UI on $UI_URL  (logs → .directo-frontend.log)"
    : > "$FRONTEND_LOG"
    (
        cd "$ROOT/ui" && \
        DIRECTO_API_URL="$API_URL" \
        NEXT_PUBLIC_DIRECTO_API_URL="$API_URL" \
        PORT="$UI_PORT" \
        nohup npm run dev -- --hostname "$UI_HOST" --port "$UI_PORT" \
            >> "$FRONTEND_LOG" 2>&1 &
        echo $! > "$FRONTEND_PID_FILE"
    )
    wait_for "$UI_URL/" "Frontend" "$FRONTEND_LOG"
    ok "ui up (pid $(cat "$FRONTEND_PID_FILE"))"
fi

# 7. browser
log "Opening $UI_URL in your browser"
open_browser "$UI_URL"

hr
ok "Directo is running!"
hr
echo "  • UI:    $UI_URL"
echo "  • API:   $API_URL"
echo "  • Docs:  $API_URL/docs"
echo
echo "Companion scripts:"
echo "  ./stop.sh    # stop backend + frontend (keeps venv + data)"
echo "  ./logs.sh    # tail backend + frontend logs (Ctrl+C to exit)"
echo "  ./start-docker.sh  # run the Docker-based stack instead"
echo
echo "Manual log access:"
echo "  tail -f .directo-backend.log"
echo "  tail -f .directo-frontend.log"
