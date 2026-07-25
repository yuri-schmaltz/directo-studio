# Changelog

All notable changes to Directo are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.2] - 2026-07-25

### Fixed

- **`./start.sh` no longer silently reuses stale code.** Previous versions
  only checked whether a service was already listening on its port; if it
  was, the script printed "(skipped)" and left it alone. That was the
  wrong default when the running service was on an older release than
  the source the user just cloned (or pulled). Symptom: the UI sidebar
  still said `v1.0`, the Swagger header still said `1.0.0`, but the user
  had a fresh checkout of a newer tag.

  The bring-up is now version-aware. A new `ensure_service` helper:

    1. Probes the service's health URL.
    2. Reads the `version` field from the probe response.
    3. If the version matches what `pyproject.toml` (or
       `ui/package.json`) declares, skip — same as before.
    4. If the port is up but the version is different (or unreadable —
       which is what a pre-versioning build looks like), warn, kill the
       process on the port via `lsof`, wait one second, and start
       fresh with the current source.

  Both the backend (`/health`) and the UI (`/api/version`, a new tiny
  route added in this release) are covered. Running the new script
  against a stale v1.1.1 install correctly tears it down and brings
  up v1.1.2.

### Added

- **`GET /api/version` on the UI** (`ui/app/api/version/route.ts`).
  Returns `{ "name": "directo-ui", "version": "<from package.json>" }`.
  Used by `./start.sh` for the version-mismatch check; safe to hit
  from a browser too.

## [1.1.1] - 2026-07-25

### Fixed

- **"Backend unreachable" error panel showed a broken command.** The text
  inside `ui/app/(dashboard)/page.tsx` had three bugs:
    1. `cd directo` pointed to a directory that does not exist (the repo
       is `directo-studio`).
    2. The venv Python path was hardcoded as `.venv/bin/python`, which
       does not work on native Windows (the correct path there is
       `.venv\Scripts\python.exe`).
    3. The `\` line continuation put `--db-dir` AFTER the `server`
       subcommand. Click parses group-level options before the
       subcommand, so it rejected the whole thing with "No such option
       '--db-dir'" — exactly the same trap that bit `docker-compose.yml`
       in v1.0.1, just expressed in plain bash.

  The panel now points to `./start.sh` (which sets up and runs the
  whole stack on its own) and, as a manual fallback, shows the
  single-line command with `--db-dir` BEFORE `server` for both Unix
  and Windows.
- **Sidebar version badge** was hardcoded to `v1.0` in
  `ui/components/nav/sidebar.tsx`. Bumped to `v1.1`.

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
