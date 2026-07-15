# 🎯 Directo — Creative AI Platform (Unified)

[![Tests](https://img.shields.io/badge/tests-213%2F213-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![Node](https://img.shields.io/badge/node-22-blue)]()
[![License](https://img.shields.io/badge/license-MIT-teal)]()

The complete Directo creative AI platform in **one repository**. Production-ready, zero required external services, runs anywhere.

> **One prompt. One vision. Directo.**
> From concept to animatic — fully directed, fully yours.

## What's in the box

This is a **monorepo** containing both the Python core and the Next.js web UI:

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
├── tests/                     213 Python tests
├── examples/                  Demo scripts
├── docker-compose.yml         ← One command to run everything
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

## Quick start

### One command (Docker)

```bash
git clone https://github.com/yuri-schmaltz/directo.git
cd directo
docker compose up --build
```

- UI:    http://localhost:3000
- API:   http://localhost:8000
- Docs:  http://localhost:8000/docs

### Local development

```bash
# 1. Backend
python3 -m venv .venv
.venv/bin/pip install -e . fastapi uvicorn click httpx websockets streamlit
.venv/bin/pytest                                 # 213/213
.venv/bin/python -m directo.platform.cli server --port 8000
# in another terminal:

# 2. Frontend
cd ui
npm install
DIRECTO_API_URL=http://localhost:8000 npm run dev
# → http://localhost:3000
```

### CLI quick tour

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

## Why monorepo

- **One clone, everything works** — `git clone && docker compose up`
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
