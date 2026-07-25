# Directo UI

Web dashboard for the [Directo](https://github.com/yuri-schmaltz/directo)
creative AI platform. Built with **Next.js 14 + TypeScript + Tailwind CSS**,
consuming the FastAPI backend via REST and WebSocket.

## Features

- **Dashboard** — live queue, gallery, cost, and cache metrics
- **Gallery** — browse, search, rate images (real-time)
- **Jobs** — submit, list, cancel jobs (auto-refresh 2s)
- **Presets** — 13 style packs, with LLM prompt enhancement
- **Cinema Engine** — 19 cinematic rules + script parser
- **Projects** — creative director projects
- **Costs** — GPU/LLM/storage/bandwidth breakdown + timeseries chart
- **Backup** — on-demand backup with integrity verification
- **Live Events** — real-time WebSocket event stream
- **About** — version + phase info

## Architecture

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  Browser     │──────▶│  Next.js (3000)  │──────▶│  FastAPI (8000)  │
│              │  WS   │  + TypeScript    │  REST │  + Python 3.11   │
│              │◀─────▶│  + Tailwind      │◀──────│  + SQLite        │
└──────────────┘       └──────────────────┘       └──────────────────┘
                              │
                              └── /api/[...path] (server-side proxy)
```

- The browser never talks to FastAPI directly — Next.js proxies all requests,
  avoiding CORS issues.
- WebSocket reconnect is handled client-side with exponential backoff.
- All pages use Server Components by default; client interactivity only where
  needed (forms, WebSocket, charts).
- `GET /api/version` (this app) returns the version from `package.json`; the
  root `./start.sh` uses it together with the backend's `/health` to detect
  when a running service is stale relative to the source and restart it.

## Quick start

The recommended way to run the UI is via the root-level
[`./start.sh`](../start.sh), which creates the venv, installs both
backend and UI deps, and brings the whole stack up:

```bash
# from the repo root
./start.sh
# → UI:   http://localhost:3000
# → API:  http://localhost:8000
# → Docs: http://localhost:8000/docs
```

If you want to run just the UI in isolation (with a backend already
running on :8000), this directory works on its own:

```bash
# from the repo root, in a separate terminal from the backend
cd ui
npm install
DIRECTO_API_URL=http://localhost:8000 npm run dev
# → http://localhost:3000
```

### With Docker

The recommended Docker flow is at the **repository root**:

```bash
# from the repo root
make start-docker          # or: ./start-docker.sh
# → UI:   http://localhost:3000
# → API:  http://localhost:8000
# → Docs: http://localhost:8000/docs
```

The `ui/docker-compose.yml` in this directory is a legacy single-service
definition; new setups should use the root-level compose file.

## Tech stack

| Layer | Tech |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript 5.6 (strict) |
| Styling | Tailwind CSS 3.4 (no shadcn, hand-built components) |
| Data | SWR 2.2 (client-side cache + revalidation) |
| Icons | Lucide React |
| Charts | Recharts (available, used lightly) |
| Build | Standalone output (small Docker image) |

## File layout

```
ui/
├── app/
│   ├── (dashboard)/         # group with sidebar layout
│   │   ├── page.tsx         # dashboard
│   │   ├── gallery/
│   │   ├── jobs/
│   │   ├── presets/
│   │   ├── cinema/
│   │   ├── projects/
│   │   ├── costs/
│   │   ├── backup/
│   │   ├── events/
│   │   └── about/
│   ├── api/
│   │   ├── [...path]/       # server-side proxy to the FastAPI backend
│   │   └── version/         # GET /api/version — version probe for start.sh
│   ├── error.tsx
│   ├── loading.tsx
│   ├── not-found.tsx
│   ├── globals.css
│   └── layout.tsx
├── components/
│   ├── ui/                  # button, card, input, badge, etc.
│   ├── nav/                 # sidebar, header
│   ├── event-feed.tsx
│   ├── stat-card.tsx
│   └── live-indicator.tsx
├── lib/
│   ├── api.ts               # typed FastAPI client
│   ├── ws.ts                # reconnecting WebSocket
│   ├── types.ts             # matching API types
│   └── utils.ts             # cn(), formatters
├── Dockerfile
├── next.config.mjs
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

## Scripts

```bash
npm run dev          # development (port 3000)
npm run build        # production build
npm run start        # production server
npm run lint         # eslint
npm run type-check   # tsc --noEmit
```

## Environment

| Variable | Default | Notes |
|---|---|---|
| `DIRECTO_API_URL` | `http://localhost:8000` | Server-side only |
| `NEXT_PUBLIC_DIRECTO_API_URL` | (none) | Browser-side; falls back to `DIRECTO_API_URL` |
| `NEXT_PUBLIC_DIRECTO_WS_URL` | `ws://localhost:8000` | WebSocket base URL |

## License

MIT
