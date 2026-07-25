# 🎯 Directo — Creative AI Platform (Unified)

[![Latest release](https://img.shields.io/github/v/release/yuri-schmaltz/directo-studio)](https://github.com/yuri-schmaltz/directo-studio/releases/latest)
[![Tests](https://img.shields.io/badge/tests-213%2F213-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![Node](https://img.shields.io/badge/node-22-blue)]()
[![License](https://img.shields.io/badge/license-MIT-teal)]()
[![No Docker required](https://img.shields.io/badge/local%20dev-no%20Docker%20needed-teal)]()

The complete Directo creative AI platform in **one repository**. Production-ready, zero required external services, runs anywhere.

> **One prompt. One vision. Directo.**
> From concept to animatic — fully directed, fully yours.

## Quick start

```bash
git clone https://github.com/yuri-schmaltz/directo.git
cd directo
./start.sh    # creates .venv, installs deps, starts backend + UI, opens browser
```

- **UI**:    http://localhost:3000
- **API**:   http://localhost:8000
- **Docs**:  http://localhost:8000/docs

That's it. `start.sh`:

- detects the OS / shell (Linux, macOS, WSL, Windows Git Bash) and uses the
  right venv path + browser opener for each;
- creates `.venv`, installs the backend in editable mode plus the
  FastAPI/uvicorn/Click/httpx/websockets/Streamlit extras;
- runs `npm install` in `ui/` if `node_modules` is missing;
- brings the backend and the UI up in the background, waits for `/health`,
  and opens the UI in the default browser;
- is **idempotent and version-aware**: if a service is already up, it
  probes its `/health` (backend) or `/api/version` (UI) and **restarts it
  if the source is newer** — so `git pull && ./start.sh` is the right
  upgrade path and you can never be stuck on a stale build of either
  service.

> Prefer Docker? `./start-docker.sh` (or `make start-docker`) builds and
> runs the same stack as containers. The local flow above is the
> default because it has zero infrastructure dependencies.

## Day-to-day

### Local (no Docker)

```bash
./start.sh         # bootstrap + start (idempotent; auto-restarts on version mismatch)
./stop.sh          # stop backend + UI (keeps venv, node_modules, and SQLite data)
./logs.sh          # tail both log files (Ctrl+C to exit)
./start-docker.sh  # ...or switch to the Docker flow
```

All local artefacts are git-ignored: `directo_data/`, `.directo-*.log`,
`.directo-*.pid`. Re-running `start.sh` is safe and fast (a few seconds
once the venv and `node_modules` are warm).

### Docker (alternative)

```bash
make start-docker  # build, start, open browser
make stop-docker   # stop containers (keeps volumes and SQLite data)
make logs-docker   # follow logs
make rebuild       # tear down + rebuild from scratch
make prune         # ⚠ stop AND delete the SQLite volume (irreversible)
```

### All make targets

```bash
make help
```

| Local | Docker |
|---|---|
| `start`, `stop`, `restart` | `start-docker`, `stop-docker`, `restart-docker` |
| `logs`, `logs-api`, `logs-ui` | `logs-docker` |
| `ps-local`, `prune-local` | `ps`, `rebuild`, `prune`, `shell-api`, `shell-ui` |
| `health` | |
| `test`, `test-ui` | |
| `browser` | |

## What's in the box

```
directo/
├── directo/                   Python lib (5 phases, 29 modules, ~12k LOC)
│   ├── observability/         Phase 0
│   ├── vault/ queue/          Phase 0
│   ├── gallery/ printing/     Phase 0
│   ├── creative/              Phase 1
│   ├── scale/                 Phase 2
│   ├── cinema/                Phase 3
│   ├── director/              Phase 4
│   └── platform/              Phase 5  ← migrations, backup, costs,
│                                         cache, events, plugins, API, CLI
├── ui/                        Next.js 14 web dashboard (12 pages)
│   ├── app/                   App Router
│   ├── components/            UI primitives
│   ├── lib/                   API client, WebSocket, types
│   ├── Dockerfile
│   └── package.json
├── start.sh                   local-mode bootstrapper (version-aware)
├── start-docker.sh            docker-mode bootstrapper
├── stop.sh                    tear-down for local mode
├── logs.sh                    tail both local log files
├── Makefile                   local + docker targets
├── tests/                     213 Python tests
├── examples/                  Demo scripts
├── CHANGELOG.md               per-version release notes
├── docker-compose.yml         Docker flow
└── pyproject.toml
```

## 5 phases · 213 tests · 14,889 LOC

| Phase | Modules | Tests | Status |
|---|---|---|---|
| 0 — stabilization | 5 | 56 | ✅ |
| 1 — creative foundation | 4 | 25 | ✅ |
| 2 — technical scale | 4 | 27 | ✅ |
| 3 — differentiation (cinema) | 3 | 31 | ✅ |
| 4 — creative direction | 4 | 22 | ✅ |
| 5 — production hardening | 9 | 46 | ✅ |
| **Total** | **29** | **213** | **✅** |

## Interfaces

- **Python API** — `import directo; ...` (97 exports)
- **HTTP REST API** — `directo server` (15+ endpoints)
- **WebSocket** — `/ws/events` and `/ws/jobs/{id}` (live progress)
- **CLI** — `directo status/gallery/jobs/cinema/backup/...`
- **Web UI** — Next.js 14 dashboard (this monorepo's `ui/`)
- **Streamlit GUI** — `directo platform gui` (legacy)

## Manual venv setup (alternative to `./start.sh`)

`./start.sh` already does all of this for you. If you want the manual
recipe — e.g. to run the backend in a debugger, or to bypass the
`./start.sh` wrapper — it looks like this:

```bash
# 1. Backend
python3 -m venv .venv
.venv/bin/pip install -e . fastapi uvicorn click httpx websockets streamlit
.venv/bin/pytest                                 # 213/213

# --db-dir MUST come before the `server` subcommand — it's a top-level
# Click group option, not a subcommand option. Put it after `server`
# and Click rejects it with "No such option '--db-dir'".
.venv/bin/python -m directo.platform.cli --db-dir ./directo_data server --port 8000
# in another terminal:

# 2. Frontend
cd ui
npm install
DIRECTO_API_URL=http://localhost:8000 npm run dev
# → http://localhost:3000
```

The corresponding Windows path is `.venv\Scripts\python.exe`; everything
else is identical.

## CLI quick tour

```bash
.venv/bin/python -m directo.platform.cli status --db-dir ./directo_data
.venv/bin/python -m directo.platform.cli gallery list --limit 5
.venv/bin/python -m directo.platform.cli cinema "a knight with a smartphone" --era 1400-1500
.venv/bin/python -m directo.platform.cli backup queue
```

## Features

### Core (Python)
- **Queue** — persistent SQLite job queue, priorities, retries, DLQ, watchdog
- **Gallery** — image storage with ratings, search, dedup
- **Cinema engine** — 19 cinematic rules (era detection, anachronism blocking)
- **Director agent** — LLM-backed creative director with project memory
- **Moodboard / Slerp / Animatic** — visual direction tools
- **Prompts** — 13 style presets + 13-provider LLM enhancement
- **Storyboard** — multi-panel canvas, PDF export
- **Production** — migrations, backup, costs (GPU/LLM/storage), cache, events, webhooks, plugins

### Web UI (Next.js 14)
- **Dashboard** — live queue, gallery, costs, top projects
- **Gallery** — browse, search, rate images (SWR)
- **Jobs** — submit, list, cancel with real-time updates
- **Presets** — browse 13 packs, render + LLM-enhance prompts
- **Cinema** — 19-rule evaluation + script parser
- **Projects** — create + manage
- **Costs** — GPU/LLM/storage/bandwidth + timeseries chart
- **Backup** — on-demand backup with integrity check
- **Live Events** — real-time WebSocket event stream

## Recent updates

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

- **v1.1.2** — `start.sh` is now **version-aware**: it probes `/health` (backend) and `/api/version` (UI), and **restarts any service that's on an older release than the source**. New `GET /api/version` route in the UI. Fixes the "(skipped) — already running" trap where a fresh clone could land on a stale build of either service.
- **v1.1.1** — fixed the "Backend unreachable" error panel in the dashboard (wrong cwd, wrong venv path on Windows, `--db-dir` in the wrong position). Sidebar version badge bumped.
- **v1.1.0** — local-mode bootstrapper (`start.sh` no longer needs Docker), stop.sh + logs.sh, `Makefile` reworked, proxy pass-through fix (the catch-all proxy no longer 404s on `/health` and `/metrics`).

## Releases

Tags are `vMAJOR.MINOR.PATCH` on `main`. The GitHub release page
includes per-version notes and the diffstat:

- [github.com/yuri-schmaltz/directo-studio/releases](https://github.com/yuri-schmaltz/directo-studio/releases)

To upgrade an existing install:

```bash
git fetch origin v1.1.2
git checkout v1.1.2
./start.sh    # will detect any stale v1.1.1 service and restart it
```

## Why monorepo

- **One clone, everything works** — `git clone && ./start.sh` (or `docker compose up`)
- **Same `db_dir`** — UI, CLI, API all share SQLite state
- **Atomic changes** — update a Python type, see the UI break immediately
- **Single PR review** — frontend + backend changes together
- **One CI** — GitHub Actions runs tests for both

## Architecture

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  Browser     │──────▶│  Next.js UI      │──────▶│  FastAPI (core)  │
│              │  WS   │  /3000 (ui/)     │ REST  │  /8000 (directo/)│
│              │◀─────▶│                  │◀──────│  + SQLite        │
└──────────────┘       └──────────────────┘       └──────────────────┘
                              │                          ▲
                              └── /api/proxy/* ──────────┘
                                  server-side proxy

   HTTP REST: 15+ endpoints
   WebSocket: /ws/events, /ws/jobs/{id}
   CLI: 15+ commands
   Python: 97 exports
```

## License

MIT
