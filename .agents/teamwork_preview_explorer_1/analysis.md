# Directo Studio — Codebase Analysis Report

**Date**: 2026-07-26  
**Repository Path**: `/home/yuri/Documentos/directo`  
**Explorer Agent**: `teamwork_preview_explorer_1`

---

## 1. Project Overview & System Architecture

Directo Studio is a single-repository creative AI platform that operates as a local media generation hub, storyboarding tool, and visual style bible. The application is structured in 6 progressive phases (Phase 0 through Phase 5), providing a complete end-to-end stack with zero mandatory external infrastructure dependencies (100% SQLite-backed).

### Key Architecture Components
- **Core Backend (`directo/`)**: Python 3.11+ library and server containing 29 submodules (~12,000 LOC).
- **Web Frontend (`ui/`)**: Next.js 14 web application using React 18, TypeScript 5, and Tailwind CSS (~3,000 LOC).
- **Database Layer**: Embedded SQLite databases using Write-Ahead Logging (WAL mode), thread-safe autocommit isolation, and thread locks (`threading.RLock`).
- **Interfaces**: REST HTTP API (FastAPI), WebSocket event streams (`/ws/events`, `/ws/jobs/{id}`), Click-based CLI (`directo`), Python module API, and legacy Streamlit GUI.

---

## 2. Directory Structure & Entry Points

```
/home/yuri/Documentos/directo/
├── directo/                   # Core Python package (5 phases, 29 modules)
│   ├── observability/         # Phase 0: Logging, Prometheus metrics, tracing
│   ├── vault/                 # Phase 0: Encrypted SQLite credential storage
│   ├── queue/                 # Phase 0: Persistent job queue & background worker
│   ├── gallery/               # Phase 0: Image storage, metadata, pHash dedup
│   ├── printing/              # Phase 0: Storyboard PDF generator (ReportLab)
│   ├── creative/              # Phase 1: Variants (4-options pattern), reference library, history, views
│   ├── scale/                 # Phase 2: ComfyUI node registry, VRAM profiler, preset packs, prompt enhancer
│   ├── cinema/                # Phase 3: 19-rule prompt validation engine, canvas, script parser
│   ├── director/              # Phase 4: Creative Director agent, moodboard, SLERP, animatic video builder
│   └── platform/              # Phase 5: Migrations, backup, costs, cache, events/webhooks, plugins, API, CLI
├── ui/                        # Next.js 14 web application (App Router)
│   ├── app/                   # Dashboard pages (gallery, jobs, presets, cinema, animatics, costs, backup, etc.)
│   ├── components/            # UI components, command palette, connection widget, n-panel, status bar
│   ├── lib/                   # API client, WebSocket client, TypeScript types, utilities
│   ├── package.json           # Frontend dependencies (next, react, swr, tailwindcss, zod, lucide-react)
│   └── tsconfig.json          # TypeScript configuration
├── tests/                     # 12 test files (217 unit & integration tests)
├── pyproject.toml             # Python package configuration & CLI entrypoint definition
├── Makefile                   # Local & Docker automation targets
├── start.sh                   # Idempotent, version-aware local runner script
├── stop.sh / logs.sh          # Operations scripts
├── docker-compose.yml / Dockerfile
└── README.md / CHANGELOG.md   # Documentation
```

### Main Entry Points
1. **Python CLI**: `directo.platform.cli:main` defined in `pyproject.toml` under `[project.scripts]`. Invoked via `.venv/bin/directo` or `python -m directo.platform.cli`.
2. **HTTP & WebSocket API**: `directo.platform.api:create_app` creates the FastAPI instance (default port 8000). Started via `.venv/bin/directo server --port 8000`.
3. **Web Dashboard**: Next.js 14 application in `ui/`, started via `npm run dev` (default port 3000). Communicates with backend via client-side requests and Next.js route proxy (`app/api/proxy/[...path]/route.ts`).
4. **Bootstrapper**: `./start.sh` detects venv/node_modules, launches backend & frontend, checks health endpoints, and auto-restarts stale builds.

---

## 3. Detailed Phase & Module Analysis

### Phase 0 — Stabilization & Core Infrastructure
- **`directo.observability`**:
  - `logging.py`: Loguru wrapper with JSON formatting, context variables (`ContextVar`), and automatic secret redaction (`_REDACT_PATTERNS` for API keys and tokens).
  - `metrics.py`: Prometheus metrics collector tracking job runtimes, HTTP request latency, and queue lengths.
  - `tracing.py`: OpenTelemetry correlation ID propagation across async tasks.
- **`directo.vault`**:
  - `credentials.py`: SQLite-backed credential vault (`vault_secrets`, `vault_meta`, `vault_audit`). Encrypts credentials with Fernet (32-byte key derived via PBKDF2-HMAC-SHA256 with 600,000 iterations). Supports key rotation and audit logging.
- **`directo.queue`**:
  - `job.py`: `Job` dataclass and `JobState` enum (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `RETRYING`, `CANCELLED`). Includes priority ordering, exponential backoff retries, and DLQ support.
  - `persistent_queue.py`: SQLite-backed persistent queue (`jobs` table) with thread safety (`RLock`) and crash recovery/stale job reaping.
  - `worker.py`: Async background worker executing registered handlers for job kinds (`image.generate`, `animatic.generate`).
- **`directo.gallery`**:
  - `models.py`: `ImageRecord` dataclass (rating 0-5, color tags, prompt/negative prompt, sampler, cfg, seed, pHash hex).
  - `store.py`: SQLite-backed image store with search, filter by tag/favorite/rating, and perceptual hashing (`imagehash.phash`) for deduplication.
- **`directo.printing`**:
  - `storyboard.py`: Multi-panel PDF storyboard generation via ReportLab (`1up`, `2up`, `4up`, `contact` sheet layouts).

### Phase 1 — Creative Foundation
- **`directo.creative.variants`**:
  - `variants.py`: Implements the 4-options creative decision pattern. `VariantSet` and `VariantStore` track decision keys, prompt templates, locked/unlocked variant choices, and strategies (`SEED_VARIATION`, `PROMPT_VARIATION`, `MIXED`, `PARAMETER_SWEEP`).
- **`directo.creative.references`**:
  - `references.py`: Style and character reference library (`ReferenceLibrary`) with image embeddings/tags for style consistency.
- **`directo.creative.history`**:
  - `history.py`: Per-job image generation history tracking, rollback, and parameter restoration.
- **`directo.creative.views`**:
  - `views.py`: HTML/Data gallery renderer for multi-view grid visualizer.

### Phase 2 — Technical Scale & Style Bible
- **`directo.scale.nodes`**:
  - `nodes.py`: ComfyUI node registry (`NodeRegistry`), health checks (`NodeHealth`), and load balancing.
- **`directo.scale.vram`**:
  - `vram.py`: GPU VRAM profiling (`GPUInfo`, `VRAMProfile`) and quantization recommendation (FP16, Q8_0, Q4_K_M).
- **`directo.scale.presets`**:
  - `presets.py`: Cinema Style Preset Store (`PresetStore`) seeded with 13 starter packs spanning live-action historical eras (German Expressionism 1920s, Noir 1940s, Technicolor 1950s, New Hollywood 1970s, 90s Indie, Modern Anamorphic) and animation styles (Studio Ghibli, Pixar, Spider-Verse, Arcane, 90s Cel Anime).
- **`directo.scale.enhance`**:
  - `enhance.py`: Prompt enhancer (`PromptEnhancer`) supporting fallback `TemplateEnhancer` and 13 LLM providers (Ollama, OpenAI, Anthropic, Groq, xAI, etc.).

### Phase 3 — Cinema Prompt Engine & Storyboard Canvas
- **`directo.cinema.engine`**:
  - `engine.py`: `CinemaEngine` evaluates prompts against 19 cinematic, historical, and physics rules (`RuleKind.BLOCK`, `WARN`, `SUGGEST`, `INJECT`). Detects era anachronisms (e.g. smartphones before 1973), physical impossibilities, and missing camera/lighting cues. Returns `EngineReport`.
- **`directo.cinema.canvas`**:
  - `canvas.py`: Storyboard multi-panel canvas data structures (`StoryboardCanvas`, `Panel`) and SQLite store (`CanvasStore`).
- **`directo.cinema.parser`**:
  - `parser.py`: Script parser (`parse_fountain`, `parse_plain_text`, `parse_script_text`) converting screenplay text into structured scenes and shot prompts.

### Phase 4 — Creative Director & Video Animatic
- **`directo.director.agent`**:
  - `agent.py`: `CreativeDirector` agent maintaining `ProjectMemory`, `Character` profiles, `StyleGuide`, and creative decision logs.
- **`directo.director.backends`**:
  - `backends.py`: `TemplateBackend` and `DynamicLLMBackend` for LLM decision-making.
- **`directo.director.moodboard`**:
  - `moodboard.py`: `MoodboardBuilder` extracts color palettes (K-Means/Pillow) and visual moods from reference image sets.
- **`directo.director.slerp`**:
  - `slerp.py`: `LatentSpaceExplorer` for spherical linear interpolation across latent space vectors.
- **`directo.director.animatic`**:
  - `animatic.py`: `AnimaticBuilder` generates video animatics using KenBurns panning/zooming effects and AI video backends (`KenBurnsBackend`, `AIVideoBackend`).

### Phase 5 — Production Hardening & Infrastructure
- **`directo.platform.migrations`**: Schema versioning and SQL migrations for SQLite databases.
- **`directo.platform.backup`**: `BackupManager` providing online SQLite backup with SHA256 integrity verification.
- **`directo.platform.costs`**: `CostTracker` recording GPU compute time, LLM tokens, storage, and bandwidth costs.
- **`directo.platform.cache`**: `CacheLayer`, `ImageCache`, and `PromptCache` for sub-millisecond prompt hit recovery.
- **`directo.platform.events`**: Event bus (`EventBus`) with async pub/sub, event persistence, and webhook dispatcher (`WebhookManager`).
- **`directo.platform.plugins`**: Plugin system (`PluginHooks`) enabling custom event subscribers, LLM providers, and preset packs.
- **`directo.platform.api`**: FastAPI application with comprehensive REST endpoints and WebSocket event streams.
- **`directo.platform.cli`**: Click CLI framework (`directo` command line interface).

---

## 4. Dependencies & Technical Stack

### Backend Dependencies (`pyproject.toml`)
- **Required Core**: `loguru>=0.7.0`, `cryptography>=42.0.0`, `pillow>=10.0.0`, `imagehash>=4.3.1`, `reportlab>=4.0.0`, `prometheus-client>=0.19.0`
- **Extra/Runtime**: `fastapi`, `uvicorn`, `click`, `httpx`, `websockets`, `streamlit`
- **Development**: `pytest>=7.4.0`, `pytest-asyncio>=0.21.0`, `pytest-cov>=4.1.0`, `mypy>=1.5.0`, `ruff>=0.1.0`

### Frontend Dependencies (`ui/package.json`)
- **Core**: `next: 14.2.18`, `react: 18.3.1`, `react-dom: 18.3.1`, `typescript: 5.6.3`, `tailwindcss: 3.4.14`
- **State & UI Libraries**: `swr: 2.2.5`, `clsx`, `tailwind-merge`, `lucide-react`, `recharts`, `sonner`, `zod`

---

## 5. Code Conventions & Architectural Patterns

1. **Explicit Data Models**: Domain objects are represented as standard Python `@dataclass` instances with `to_dict()`, `from_dict()`, or `from_row()` methods.
2. **Zero External Services**: Persistence relies strictly on SQLite with `PRAGMA journal_mode=WAL` and `isolation_level=None` (autocommit). Thread safety is enforced using `threading.RLock()` across all store classes (`PersistentQueue`, `Gallery`, `PresetStore`, `CanvasStore`, `VariantStore`, `CredentialVault`).
3. **Structured Event Publishing**: All mutating actions in API endpoints publish events through `EventBus` (e.g. `EventKind.JOB_ENQUEUED`, `EventKind.IMAGE_ADDED`, `EventKind.CANVAS_SAVED`), which stream live to WebSocket clients (`/ws/events`).
4. **Idempotency & Resilience**: Job state transitions use explicit SQL updates (`WHERE state = 'pending'`); failed jobs undergo exponential backoff before being moved to DLQ.
5. **Code Style**: Formatted with `ruff` (line-length 100, target-version `py311`), type annotated for `mypy` strict optional checking, and tested with `pytest` (217 tests passing).
