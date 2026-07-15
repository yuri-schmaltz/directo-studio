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

## Quick start

### Local (with the FastAPI backend already running)

```bash
# 1. Install deps
npm install

# 2. Make sure the FastAPI is running
#    (from ../directo)
#    .venv/bin/python -m directo.platform.cli server --port 8000

# 3. Start the dev server
cp .env.example .env.local
npm run dev
# → http://localhost:3000
```

### With Docker (recommended)

From the repository root:

```bash
docker compose -f directo-ui/docker-compose.yml up --build
# → UI:   http://localhost:3000
# → API:  http://localhost:8000
# → Docs: http://localhost:8000/docs
```

This builds the Next.js image, starts the FastAPI, mounts the Directo SQLite
data into a named volume, and waits for the API to be healthy before starting
the UI.

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
directo-ui/
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
│   ├── api/[...path]/       # server-side proxy
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
├── docker-compose.yml
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
