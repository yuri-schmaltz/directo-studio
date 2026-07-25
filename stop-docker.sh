#!/usr/bin/env bash
# Stop the Docker-based Directo stack started by ./start-docker.sh.
# - `docker compose down` tears down the containers and removes the default
#   network, but keeps named volumes (so the SQLite data survives).
# - Detects WSL and opens the Windows browser if a UI URL is given as $1
#   (no-op when no arg is passed).

set -euo pipefail

cd "$(dirname "$0")"

echo "→ Stopping the Directo Docker stack (docker compose down)..."
docker compose down

echo ""
echo "Stack stopped. Named volumes are preserved (SQLite data survives)."
echo ""
echo "To delete the SQLite volume as well: docker compose down -v"
