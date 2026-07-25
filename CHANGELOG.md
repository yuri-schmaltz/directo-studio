# Changelog

All notable changes to Directo are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-07-25

### Added

- **Local-mode bootstrapper** (`start.sh`). The previous `start.sh` was
  docker-only; the new one is a no-Docker bootstrap that creates `.venv`,
  installs backend + UI deps, starts both services in the background,
  waits for `/health`, and opens the browser. Detects Linux / macOS /
  WSL / Windows Git Bash and uses the right venv path and browser
  opener for each. Re-runnable and idempotent.
- **`stop.sh`** — kills the local backend and frontend by PID, walks
  the child process tree (covers the `npm → next-server` orphan case),
  and has a `pkill` safety net for any stragglers.
- **`logs.sh`** — `tail -F` for both log files.
- **`Makefile` targets for the local flow** — `start`, `stop`,
  `restart`, `logs`, `logs-api`, `logs-ui`, `ps-local`, `prune-local`.
  Docker targets are clearly namespaced (`start-docker`, `stop-docker`,
  `logs-docker`, `ps`, `rebuild`, `shell-api`, `shell-ui`, `prune`).

### Changed

- The old Docker-based `start.sh` content is preserved as
  `start-docker.sh` and continues to be used by `make start-docker`.
- `pyproject.toml`, `directo/__init__.py`, `directo/platform/api.py`
  (FastAPI app + `/health` response), `directo/platform/cli.py`
  (Click `--version`), and `ui/package.json` are now in sync at
  `1.1.0`.

### Fixed

- **Proxy 404 on `/health` and `/metrics`.** The catch-all proxy at
  `app/api/proxy/[...path]/route.ts` was hardcoding `/api/` into every
  forwarded URL, which broke the backend's top-level routes. The
  dashboard's SWR poll on `/api/proxy/health` now returns 200 even
  when the FastAPI is fully healthy, and the "Backend unreachable"
  panel no longer renders spuriously after a successful `./start.sh`.

### Chore

- `.gitignore` now ignores the local-mode runtime artefacts:
  `directo_data/`, `.directo-backend.log`, `.directo-frontend.log`,
  `.directo-backend.pid`, `.directo-frontend.pid`.

## [1.0.1] - 2026-07-15

### Fixed

- `start.sh` (Docker flow) had `--db-dir` AFTER the `server`
  subcommand, which Click rejected with "No such option '--db-dir'".
  Moved it before `server`. See `directo/platform/cli.py: build_cli()`.

## [1.0.0] - 2026-07-15

### Added

- **Initial public release.** Directo v1 — the unified monorepo
  bringing together the Python core (5 phases, 29 modules, ~12k LOC)
  and the Next.js 14 web dashboard (12 pages).
  - 213/213 tests passing.
  - 15+ HTTP REST endpoints, 2 WebSocket endpoints, 15+ CLI commands,
    97 Python exports.
  - SQLite-backed queue, gallery, costs, events, memory, presets,
    cinema rules, backup, migrations.
  - One-command Docker stack via `make start`.
