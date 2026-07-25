#!/usr/bin/env bash
# Stop the local-mode Directo services started by ./start.sh.
# Kills the tracked backend/frontend PIDs, walks the child process tree, and
# uses pattern-based pkill as a safety net for any orphans (npm can detach
# the next-server child if its own PID gets reaped first).
#
# Does NOT remove the venv, node_modules, or SQLite data.

set -euo pipefail

cd "$(dirname "$0")"

ok()   { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[1;33m!\033[0m %s\n' "$*"; }

API_PORT="${DIRECTO_API_PORT:-8000}"
UI_PORT="${DIRECTO_UI_PORT:-3000}"

# kill_tree <pid>  — TERM the whole subtree, wait, then KILL anything left.
kill_tree() {
    local pid="$1" tries=8
    [ -z "$pid" ] && return 0
    kill -0 "$pid" 2>/dev/null || return 0

    # Try the process group first (covers `setsid` setups), then fall back
    # to TERM-ing the root and walking children explicitly.
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    local child
    for child in $(pgrep -P "$pid" 2>/dev/null || true); do
        kill_tree "$child"
    done

    while [ "$tries" -gt 0 ] && kill -0 "$pid" 2>/dev/null; do
        sleep 1
        tries=$((tries - 1))
    done
    if kill -0 "$pid" 2>/dev/null; then
        kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
        for child in $(pgrep -P "$pid" 2>/dev/null || true); do
            kill -KILL "$child" 2>/dev/null || true
        done
    fi
}

# stop_tracked <pid_file> <name> <extra_pattern>
# - kills the PID stored in the file (and its children)
# - also pkill's anything matching the extra pattern (orphan safety net)
stop_tracked() {
    local pid_file="$1" name="$2" extra_pattern="$3" pid=""

    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file" 2>/dev/null || true)
    fi

    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill_tree "$pid"
        ok "stopped $name (pid $pid)"
    else
        warn "$name was not running (stale pid file removed if any)"
    fi
    rm -f "$pid_file"

    if [ -n "$extra_pattern" ]; then
        # pkill returns 1 when nothing matches, which would trip `set -e`; mask it.
        local matched
        matched=$(pgrep -f "$extra_pattern" 2>/dev/null || true)
        if [ -n "$matched" ]; then
            # shellcheck disable=SC2086
            kill -KILL $matched 2>/dev/null || true
            warn "killed extra $name processes: $matched"
        fi
    fi
}

stop_tracked .directo-frontend.pid "frontend" "next-server|next dev --"
stop_tracked .directo-backend.pid  "backend"  "directo\.platform\.cli"

# Defensive: also free the dev ports in case anything is still bound.
if command -v lsof >/dev/null 2>&1; then
    for port in "$UI_PORT" "$API_PORT"; do
        local_pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
        if [ -n "$local_pids" ]; then
            warn "killing leftover processes on port $port: $local_pids"
            # shellcheck disable=SC2086
            kill -KILL $local_pids 2>/dev/null || true
        fi
    done
fi

ok "all local services stopped"
echo
echo "Re-run ./start.sh to bring the stack back up."
