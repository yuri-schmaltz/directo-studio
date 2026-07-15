#!/usr/bin/env bash
# Directo stack bootstrapper.
# - Builds images, starts containers in the background
# - Waits for both API and UI healthchecks to pass
# - Opens the UI in the default browser (handles WSL too)
#
# Used by `make start` and safe to run directly.

set -euo pipefail

cd "$(dirname "$0")"

UI_URL="http://localhost:3000"
API_URL="http://localhost:8000"
TIMEOUT_SECONDS=180

echo "→ Building and starting the Directo stack (docker compose up --build -d)..."
docker compose up --build -d

echo "→ Waiting for API at $API_URL/health (timeout: ${TIMEOUT_SECONDS}s)..."
elapsed=0
until curl -sf "$API_URL/health" > /dev/null 2>&1; do
    if [ "$elapsed" -ge "$TIMEOUT_SECONDS" ]; then
        echo "✗ API did not become healthy in time. Showing last 50 log lines:" >&2
        docker compose logs --tail=50 api >&2
        exit 1
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done
echo "  ✓ API is healthy"

echo "→ Waiting for UI at $UI_URL/ (timeout: ${TIMEOUT_SECONDS}s)..."
elapsed=0
until curl -sf "$UI_URL/" > /dev/null 2>&1; do
    if [ "$elapsed" -ge "$TIMEOUT_SECONDS" ]; then
        echo "✗ UI did not become reachable in time. Showing last 50 log lines:" >&2
        docker compose logs --tail=50 ui >&2
        exit 1
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done
echo "  ✓ UI is reachable"

echo "→ Stack is up. Opening $UI_URL in the default browser..."

# Detect WSL (Windows Subsystem for Linux) and route to the Windows host browser.
if grep -qi microsoft /proc/version 2>/dev/null; then
    powershell.exe /c start "$UI_URL" > /dev/null 2>&1 || true
else
    xdg-open "$UI_URL" > /dev/null 2>&1 || true
fi

echo ""
echo "All set! Directo is running:"
echo "  • UI:   $UI_URL"
echo "  • API:  $API_URL"
echo "  • Docs: $API_URL/docs"
echo ""
echo "Useful commands:"
echo "  make logs     # follow logs (Ctrl+C to exit)"
echo "  make stop     # stop the stack"
echo "  make shell-api  # open a shell in the API container"
