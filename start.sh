#!/usr/bin/env bash
# Directo stack bootstrapper — local mode (no Docker required).
#
# This script does everything end-to-end on a fresh checkout:
#   1. Detects the OS / shell (Linux, macOS, WSL, native Windows Git Bash).
#   2. Creates a Python .venv and installs backend + API deps in editable mode.
#   3. Creates the SQLite data dir if missing.
#   4. Starts (or verifies) the FastAPI backend on :8000.
#        - If /health responds and reports the expected version, skip.
#        - If /health responds with a DIFFERENT version (or no version), kill
#          the stale process and start fresh.
#        - If /health does not respond, start fresh.
#   5. Runs `npm install` in ui/ if node_modules is missing.
#   6. Same version-aware bring-up for the Next.js dev server on :3000.
#   7. Waits for both endpoints to come up.
#   8. Opens the UI in the default browser (handles WSL too).
#
# It is safe to re-run: existing venv/node_modules/data are reused; if a
# service is up *and on the right version*, it is left alone.
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

# probe_version <url>
#   Reads JSON from <url> and returns the value of the "version" key on stdout.
#   Returns empty string on any failure (network error, bad JSON, missing key,
#   missing python3, etc.). Caller is expected to handle the empty case.
probe_version() {
    local url="$1"
    # curl --fail silently on non-2xx, --max-time to avoid hanging, --silent
    # for clean output. python3 is used to parse because the rest of the script
    # already depends on Python being available (the venv ships with it).
    curl -sf --max-time 3 "$url" 2>/dev/null \
        | python3 -c "import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get('version','') if isinstance(d, dict) else '')
except Exception:
    pass" 2>/dev/null \
        || true
}

# kill_on_port <port> [extra_pkill_pattern]...
#   Kill anything currently bound to <port>, then verify the port is actually
#   free before returning. Uses SIGKILL because by definition we are replacing
#   the listener with a known-good one.
#
#   Pass extra pkill patterns (e.g. "next-server") to also nuke parents and
#   siblings of the listener — useful when the listener is a child of a
#   long-running wrapper (npm run dev → sh → node next → next-server) and
#   just killing the listener isn't enough: the wrapper can re-spawn it, and
#   other processes in the same tree keep the port in TIME_WAIT.
#
#   Polls lsof every second for up to 10s. If the port is still not free
#   after that, warns and returns non-zero so the caller can decide.
kill_on_port() {
    local port="$1"
    shift
    if ! command -v lsof >/dev/null 2>&1; then
        warn "lsof not available; skipping port-$port cleanup (best-effort)"
        return 0
    fi

    # First sweep: anything listening on the port.
    local pids
    pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        # shellcheck disable=SC2086
        kill -KILL $pids 2>/dev/null || true
    fi

    # Second sweep: pkill by pattern (parents/siblings of the listener).
    for pat in "$@"; do
        pkill -KILL -f "$pat" 2>/dev/null || true
    done

    # Verify the port is actually free. The kernel can take a moment to release
    # it after SIGKILL (TIME_WAIT, socket teardown), so poll instead of a
    # single sleep.
    local attempt=0
    while [ "$attempt" -lt 10 ]; do
        if [ -z "$(lsof -ti tcp:"$port" 2>/dev/null || true)" ]; then
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done

    warn "could not free port $port within 10s; pids still bound: $(lsof -ti tcp:"$port" 2>/dev/null || true)"
    return 1
}

# ensure_service <name> <health_url> <version_url> <expected_version> \
#                <port> <log_file> <pid_file> <start_fn>
#
#   The single source of truth for "is the right version already running?".
#   - If <health_url> is up AND <version_url> reports <expected_version>, skip.
#   - If <health_url> is up but the version differs (or is unreadable), warn,
#     kill the existing process on <port>, and (re)start.
#   - If <health_url> is down, (re)start.
#
#   <start_fn> is the literal command to background. We pass it as a string
#   rather than a function reference so the implementation can stay in plain
#   bash without `declare -F` lookups.
ensure_service() {
    local name="$1"
    local health_url="$2"
    local version_url="$3"
    local expected_version="$4"
    local port="$5"
    local log_file="$6"
    local pid_file="$7"
    local start_cmd="$8"

    if curl -sf --max-time 3 "$health_url" >/dev/null 2>&1; then
        local running_version
        running_version=$(probe_version "$version_url")
        if [ -n "$expected_version" ] && [ "$running_version" = "$expected_version" ]; then
            ok "$name already on $expected_version at $health_url (skipped)"
            return 0
        fi
        if [ -n "$running_version" ]; then
            warn "$name on $health_url reports version $running_version, expected $expected_version — restarting"
        else
            warn "$name on $health_url is up but did not report a version (stale or pre-versioning build) — restarting"
        fi
        kill_on_port "$port" "next-server" "next dev" "directo.platform.cli"
    fi

    log "Starting $name on $health_url  (logs → $log_file)"
    : > "$log_file"
    # Run the start command in a subshell so `cd` and env vars are scoped.
    # `&` backgrounds it; the subshell exits immediately, leaving the child
    # running. The child's stdout/stderr are already redirected to $log_file.
    (
        nohup setsid bash -c "$start_cmd" >> "$log_file" 2>&1 &
        pid=$!
        echo "$pid" > "$pid_file"
    )
    wait_for "$health_url" "$name" "$log_file"
    ok "$name up (pid $(cat "$pid_file"))"
}

# ----- main ----------------------------------------------------------------
detect_env

# Read the expected versions from the source tree (single source of truth).
EXPECTED_API_VERSION=$(grep '^version' pyproject.toml | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
EXPECTED_UI_VERSION=$(grep '"version"' ui/package.json | head -1 | sed -E 's/.*"([^"]+)".*/\1/')

hr
log "Directo bootstrap (local mode, no Docker required)"
hr
echo "  repo:    $ROOT"
echo "  os:      $OS"
echo "  python:  $("$PY" --version 2>&1)"
echo "  venv:    $VENV_DIR"
echo "  api:     $API_URL  (expected version $EXPECTED_API_VERSION)"
echo "  ui:      $UI_URL   (expected version $EXPECTED_UI_VERSION)"
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
log "Installing backend dependencies (editable mode)"
"$VENV_PY" -m pip install --upgrade pip --quiet
"$VENV_PY" -m pip install -e . --quiet
ok "backend deps installed"

# 3. data dir
mkdir -p "$DATA_DIR"
ok "data dir ready: $DATA_DIR"

# 4. backend — version-aware bring-up
ensure_service \
    "Backend" \
    "$API_URL/health" \
    "$API_URL/health" \
    "$EXPECTED_API_VERSION" \
    "$API_PORT" \
    "$BACKEND_LOG" \
    "$BACKEND_PID_FILE" \
    "cd '$ROOT' && nohup '$VENV_PY' -m directo.platform.cli --db-dir '$DATA_DIR' server --host '$API_HOST' --port '$API_PORT'"

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

# 6. UI — version-aware bring-up
ensure_service \
    "UI" \
    "$UI_URL/" \
    "$UI_URL/api/version" \
    "$EXPECTED_UI_VERSION" \
    "$UI_PORT" \
    "$FRONTEND_LOG" \
    "$FRONTEND_PID_FILE" \
    "cd '$ROOT/ui' && DIRECTO_API_URL='$API_URL' NEXT_PUBLIC_DIRECTO_API_URL='$API_URL' PORT='$UI_PORT' setsid nohup npm run dev -- --hostname '$UI_HOST' --port '$UI_PORT'"

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
