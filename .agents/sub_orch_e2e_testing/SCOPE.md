# Scope: E2E Testing Track Orchestrator

## Architecture & Subsystem Test Suite
The E2E Testing Track is responsible for constructing an opaque-box test suite for Directo Studio's Local Media Generation Hub and Style Bible project across four core test files:

1. `tests/test_style_bible.py`:
   - Feature 1: Style Bible Data Models & Persistence (StyleBible, CharacterProfile, EnvironmentAnchor, StyleDirective, LoRAConfig) in JSON and YAML.
   - Feature 1 (Store): StyleBibleStore SQLite CRUD (save, load, list, search, export, import).
   - Tiers: Tier 1 (Feature Coverage >=5), Tier 2 (Boundary/Corner Cases >=5), Tier 3 (Cross-feature interactions), Tier 4 (Real-world scenario).

2. `tests/test_prompt_builder.py`:
   - Feature 2: PromptBuilder visual anchor, LoRA weight formatting, seed injection, style token injection, negative prompts.
   - Tiers: Tier 1 (>=5), Tier 2 (>=5), Tier 3 (Cross-feature interactions), Tier 4 (Real-world scenario).

3. `tests/test_local_media_orchestrator.py`:
   - Features 3-7: ComfyUI Video Driver, FFmpeg Renderer, Piper/Bark/Coqui TTS, Whisper Subtitles, AudioMixer Sidechain Ducking, LocalMediaOrchestrator async pipeline.
   - Using mocks for offline test stability.
   - Tiers: Tier 1 (>=5 per feature area), Tier 2 (>=5 boundary/corner), Tier 3 (Cross-feature pipeline), Tier 4 (Real-world script-to-video workflow).

4. `tests/test_local_gen_api.py`:
   - Features 8-9: FastAPI Endpoints (`/api/style-bibles`, `/api/media-hub/generate`, status polling/WebSocket events, UI TypeScript schema compliance).
   - Tiers: Tier 1 (>=5 API endpoints), Tier 2 (>=5 boundary/invalid inputs), Tier 3 (Cross-feature REST + WebSocket flow), Tier 4 (Full REST CRUD & Generation trigger).

## Milestones & Status
| # | Target File / Subsystem | Scope | Dependencies | Status |
|---|-------------------------|-------|--------------|--------|
| 1 | `tests/test_style_bible.py` | Models, JSON/YAML persistence, SQLite store | None | PLANNED |
| 2 | `tests/test_prompt_builder.py` | PromptBuilder anchors, LoRAs, seeds, tokens | M1 | PLANNED |
| 3 | `tests/test_local_media_orchestrator.py` | ComfyUI, FFmpeg, TTS, Whisper, AudioMixer, Pipeline | M1, M2 | PLANNED |
| 4 | `tests/test_local_gen_api.py` | FastAPI REST endpoints, WebSockets, UI schemas | M1, M2, M3 | PLANNED |
| 5 | Validation & TEST_READY | Full pytest suite run, verify structure & syntax, publish TEST_READY.md | M1, M2, M3, M4 | PLANNED |

## Interface Contracts & Test Requirements
- Category-Partition, BVA, Pairwise, and Real-World Workload methodologies strictly applied.
- Offline stability via mocks for heavy GPU/network models.
- Clean pytest structure with proper fixtures, async test support if needed (`pytest.mark.asyncio`), and zero test hardcoding/facades.
