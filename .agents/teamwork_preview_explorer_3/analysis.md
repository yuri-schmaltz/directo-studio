# Technical Analysis: Directo Studio UI & Test Suite Architecture

**Date**: 2026-07-26  
**Author**: Explorer Subagent (teamwork_preview_explorer_3)  
**Target Project**: Directo Studio — Local Media Generation Hub & Style Bible  
**Scope**: UI Directory Structure (`ui/`), TypeScript Configurations, Types, Schemas, API Client Interfaces, Test Suite Setup (`tests/`), Pytest Configurations, Test Runners, and Conventions.

---

## Executive Summary

Directo Studio consists of a **Next.js 14 App Router frontend** (`ui/`) and a **comprehensive Python pytest test suite** (`tests/`).

1. **Frontend (`ui/`)**: Built with Next.js 14.2.18, React 18, Tailwind CSS, SWR, and Lucide React. API communications use a typed client (`ui/lib/api.ts`) routed through a server-side proxy route (`ui/app/api/proxy/[...path]/route.ts`) to avoid CORS issues. Types are manually maintained in `ui/lib/types.ts`. Zod is present in `package.json` but not currently used for runtime validation. **There are currently no frontend unit tests or test framework configurations (Jest/Vitest/Playwright) set up in `ui/`.**
2. **Backend Test Suite (`tests/`)**: Contains 12 test files covering all 5 platform phases, creative primitives, cinema rule engine, queue management, scale/VRAM features, director module, observability, vault encryption, PDF printing, and Streamlit GUI. Pytest is configured in `pyproject.toml` with `asyncio_mode = "auto"`.

---

## 1. Frontend Architecture & UI Structure (`ui/`)

### 1.1 Directory Structure & Layout
```
ui/
├── app/                        # Next.js 14 App Router
│   ├── (dashboard)/            # Main dashboard route group
│   │   ├── about/page.tsx      # System version & release notes
│   │   ├── animatics/page.tsx  # Storyboard & animatic builder
│   │   ├── backup/page.tsx     # SQLite backup manager & verification
│   │   ├── cinema/page.tsx     # Cinema engine evaluator & script parser
│   │   ├── costs/page.tsx      # Token & generation cost analytics
│   │   ├── events/page.tsx     # Real-time event log viewer
│   │   ├── gallery/page.tsx    # Media generation hub gallery
│   │   ├── jobs/               # Queue management & job submission
│   │   │   ├── page.tsx
│   │   │   └── new/page.tsx
│   │   ├── presets/page.tsx    # Era & style preset library
│   │   ├── projects/           # Project memory management
│   │   │   ├── page.tsx
│   │   │   └── new/page.tsx
│   │   ├── settings/page.tsx   # Node registry & system settings
│   │   ├── layout.tsx          # Dashboard shell layout (Header, Sidebar, StatusBar)
│   │   └── page.tsx            # Main overview dashboard
│   ├── api/                    # Next.js Server API routes
│   │   ├── proxy/[...path]/    # FastAPI reverse proxy route
│   │   └── version/            # UI version info route
│   ├── error.tsx               # Error boundary
│   ├── globals.css             # Tailwind base styles
│   ├── layout.tsx              # Root HTML/Body layout
│   ├── loading.tsx            # Global loading skeleton
│   └── not-found.tsx          # 404 page
├── components/                 # React UI components
│   ├── nav/                    # Header, Sidebar, Connection Widget
│   ├── ui/                     # Primitives: badge, button, card, empty-state, input
│   ├── collapsible-panel.tsx   # Collapsible side drawer panel
│   ├── command-palette.tsx    # Global Ctrl+K command launcher
│   ├── event-feed.tsx          # Live event stream ticker widget
│   ├── live-indicator.tsx      # WebSocket connection indicator
│   ├── n-panel.tsx             # N-panel sidebar drawer
│   ├── notifications-provider.tsx # Toast provider (Sonner)
│   ├── split-viewport.tsx      # Dual image/media split comparison viewport
│   ├── stat-card.tsx           # Stat metric display card
│   └── status-bar.tsx          # Bottom status bar
├── lib/                        # Core utilities & API layer
│   ├── api.ts                  # Typed FastAPI HTTP client
│   ├── types.ts                # TypeScript interface definitions
│   ├── utils.ts                # Formatting & class merging utilities
│   └── ws.ts                   # WebSocket reconnecting hook (useEventStream)
├── next.config.mjs             # Next.js standalone build configuration
├── tailwind.config.ts          # Tailwind CSS theme & plugin config
├── tsconfig.json               # TypeScript compiler configuration
└── package.json                # Dependencies and npm scripts
```

### 1.2 TypeScript Configurations (`ui/tsconfig.json`)
* **Target & Module**: ES2022 target, `esnext` module with `bundler` module resolution.
* **Strictness**: `"strict": true`, `"skipLibCheck": true`, `"isolatedModules": true`.
* **Path Aliases**: `"@/*": ["./*"]` for clean imports across the project.
* **Build Integration**: Includes `next-env.d.ts`, `**/*.ts`, `**/*.tsx`, `.next/types/**/*.ts`.

### 1.3 Data Types & Schema Validation
* **`ui/lib/types.ts`**: Contains complete TypeScript definitions mirroring the FastAPI response models:
  * `HealthResponse`, `QueueStats`, `JobKind`, `JobState`, `Job`, `JobCreatePayload`
  * `ImageRecord`, `Preset`, `CinemaReport`, `Scene`, `EvaluateScriptResponse`
  * `CostSummary`, `TimeseriesPoint`, `BackupResult`, `ProjectRecord`, `Event`, `EventKind`
  * Constants: `JOB_KINDS`, `JOB_STATES`
* **Schema Validation**:
  * `zod` (v3.23.8) is listed in `package.json`.
  * Currently, **no Zod schemas exist** in `ui/lib/` or `ui/app/`. All runtime JSON payload parsing relies on TypeScript type assertions (`res.json() as Promise<T>`).

### 1.4 API Client & Networking Layer
* **HTTP Client (`ui/lib/api.ts`)**:
  * Dual-mode fetching: Server-side calls target `DIRECTO_API_URL` directly; Client-side calls target `/api/proxy/*` to prevent CORS issues.
  * Standardized helper `request<T>(path, init)` throwing detailed HTTP status errors.
  * Provides organized sub-clients: `api.health`, `api.metrics`, `api.gallery`, `api.jobs`, `api.presets`, `api.cinema`, `api.projects`, `api.backup`.
  * Exports `swrFetcher` for use with `useSWR`.
* **Server-Side Proxy (`ui/app/api/proxy/[...path]/route.ts`)**:
  * Handles `GET`, `POST`, `PUT`, `DELETE`, `PATCH` requests and forwards headers & body to the FastAPI backend.
* **WebSocket Client (`ui/lib/ws.ts`)**:
  * `useEventStream` hook manages persistent connection to `/ws/events`.
  * Implements exponential backoff (1s, 2s, 4s... max 30s) and caps client event buffer at 500 events to prevent memory leaks.

---

## 2. Test Suite & Automation Setup (`tests/`)

### 2.1 Pytest Configuration (`pyproject.toml`)
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --tb=short"
markers = [
    "gui: Streamlit GUI tests (require streamlit)",
]
```
* Executed via `.venv/bin/pytest` or `make test`.

### 2.2 Test Suite Inventory & Coverage

| File | Subsystem Tested | Key Capabilities & Components Tested |
|---|---|---|
| `tests/test_ai_video.py` | Animatic & Video Generation | `AIVideoBackend` (mock rendering, clip rendering, output file creation), `/api/animatics` endpoint integration. |
| `tests/test_cinema.py` | Cinema Engine & Fountain Parser | `CinemaEngine` (builtin era, physics, cinematography, consistency rules), `StoryboardCanvas`, `CanvasStore` (grid layout, panel bounds), Fountain script parser (`parse_fountain`, `parse_plain_text`, `parse_script_text`, Markdown). |
| `tests/test_creative.py` | Creative Primitives & References | `VariantSet`, `VariantLock` (locking, unlocking, rejecting, SQLite store persistence), `plan_seeds`, `PillowBackend` (image hashing/embedding), `ReferenceLibrary` (deduplication, tag filtering, similarity search). |
| `tests/test_director.py` | Director & Project Memory | `ProjectMemory` (SQLite CRUD, decision tracking), `CreativeDirector` (character manager, style guide setting, offline prompt enrichment), `AnimaticBuilder`, `MoodboardBuilder`, `LatentSpaceExplorer`. |
| `tests/test_gallery.py` | Media Gallery | `Gallery` SQLite database, `ImageRecord` (add, get, rating, favorite, color tags, tag deduplication, text search). |
| `tests/test_gui.py` | Streamlit GUI | Streamlit app (`directo.platform.gui`), service caching via `@st.cache_resource`, headless rendering using `streamlit.testing.v1.AppTest`. Marked with `@pytest.mark.gui`. |
| `tests/test_observability.py` | Observability & Logging | Loguru logger, JSON formatted output, correlation ID tracking via `contextvars`, API key redaction in logs, Prometheus `MetricsCollector` singleton, `Tracer` span execution tracking. |
| `tests/test_platform.py` | Platform Subsystems | `MigrationManager` (version tracking, idempotency, out-of-order detection), `BackupManager` & `MultiBackup` (backup creation & verification), `EventBus` (pub-sub, async handlers), `CostTracker` (USD metrics by project/kind), `CacheLayer` (`PromptCache`, `ImageCache`), Plugin hooks lifecycle, `WebhookManager`. |
| `tests/test_printing.py` | Storyboard Export | `StoryboardExporter` (PDF generation using ReportLab across 1-up, 2-up, 4-up, contact sheet layouts, missing image fallback, `%PDF` header validation). |
| `tests/test_queue.py` | Persistent Job Queue | `PersistentQueue` (SQLite job lifecycle, priority queueing, FIFO tie-breaking, scheduled jobs, exponential backoff retries, dead-lettering, worker claim lease renewal). |
| `tests/test_scale.py` | Scale & VRAM Optimization | VRAM profiling and quantization recommendation (`recommend_quant_for_model`), ComfyUI node health checking and tag routing (`ComfyUINode`, `NodeRegistry`), `PresetStore`, `TemplateEnhancer`. |
| `tests/test_vault.py` | Credential Security | `CredentialVault` (AES/Fernet encryption, key rotation `rotate_key`, restart persistence, metadata tags, activity audit log). |

### 2.3 Test Conventions & Practices
1. **Fixture Modularization**: No `conftest.py` is used. Fixtures are declared locally per test file (e.g. `tmp_image`, `gallery`, `workspace`).
2. **Isolation via `tmp_path`**: Almost all tests construct temporary SQLite databases (`:memory:` or `tmp_path / "test.db"`) to ensure complete test isolation.
3. **Mocking**: Tests use internal mock backends (e.g., `AIVideoBackend(name="mock")`, `TemplateBackend()`) or `monkeypatch` to avoid external API calls.

### 2.4 Gap Analysis & Observations
* **Frontend Test Coverage**: The Next.js frontend in `ui/` currently lacks any automated test harness (Jest, Vitest, React Testing Library, or Playwright/Cypress). The `Makefile` target `test-ui` (`docker compose exec ui npm test --silent`) fails if run directly because `"test"` is missing from `ui/package.json`.
* **Runtime Validation**: While `zod` is installed in `ui/package.json`, API responses and form inputs are not parsed using Zod schemas.

---

## 3. Recommended Next Steps for Team

1. **Frontend Testing Setup**: Add a lightweight unit test runner (e.g., Vitest + React Testing Library) or E2E runner (Playwright) to `ui/`, and add `"test": "vitest run"` to `ui/package.json`.
2. **Zod Runtime Schemas**: Introduce runtime Zod schemas for API responses and client input validation in `ui/lib/schemas.ts` to complement static TypeScript types.
3. **Shared Fixtures**: If test complexity grows, consolidate common Python test fixtures (e.g. `tmp_image`, `api_client`) into a root `tests/conftest.py`.
