#!/usr/bin/env bash
# Tail the local-mode Directo logs (Ctrl+C to exit).
# Equivalent to: tail -F .directo-backend.log .directo-frontend.log

set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .directo-backend.log ] && [ ! -f .directo-frontend.log ]; then
    echo "no log files yet — run ./start.sh first" >&2
    exit 1
fi

exec tail -F .directo-backend.log .directo-frontend.log
