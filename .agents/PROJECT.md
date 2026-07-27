# Project: Directo Studio Local Media Generation Hub & Style Bible Subsystem

## Architecture & System Overview
Directo Studio is expanding with an integrated Local Media Generation Hub and Style Bible Subsystem:
- `directo/style_bible/`: Data structures (`StyleBible`, `CharacterProfile`, `EnvironmentAnchor`, `StyleDirective`, `LoRAConfig`), JSON/YAML persistence (`StyleBibleStore`), and `PromptBuilder` for character/environment anchor injection and LoRA/seed syntax composition.
- `directo/media_hub/`: Asynchronous hub for local media creation:
  - `video/`: `ComfyUIVideoDriver` (routes workflows via `NodeRegistry`), `FFmpegRenderer` (overlays, padding, crossfades, subtitle burn-in), `MockVideoDriver`.
  - `voices/`: Local TTS engines (`PiperTTSDriver`, `BarkTTSDriver`, `CoquiTTSDriver`, `MockTTSDriver`).
  - `subtitles/`: `WhisperSubtitleGenerator` and `SubtitleAligner` (.srt, .vtt, .json formats).
  - `audio/`: `AudioMixer` multi-track manager and `AudioDuckingEngine` (sidechain compression for BGM ducking during character speech).
  - `orchestrator.py`: `LocalMediaOrchestrator` async facade coordinating full production pipeline.
- `directo/api/` (and `directo/platform/api.py`): FastAPI REST/WebSocket endpoints for Style Bibles and Local Media Hub generation.
- `ui/`: TypeScript interface definitions (`ui/lib/types.ts`), API client methods (`ui/lib/api.ts`), and Zod validation schemas (`ui/lib/schemas.ts`).
- `tests/`: Automated unit, integration, and E2E test suite (`test_style_bible.py`, `test_prompt_builder.py`, `test_local_media_orchestrator.py`, `test_local_gen_api.py`).

## Implementation Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Style Bible Engine & Prompt Builder | `directo/style_bible/`, `tests/test_style_bible.py`, `tests/test_prompt_builder.py` | None | IN_PROGRESS |
| 2 | Local Media Generation Hub | `directo/media_hub/`, `tests/test_local_media_orchestrator.py` | M1 | PLANNED |
| 3 | Backend FastAPI API & UI Schemas | `directo/platform/api.py`, `ui/lib/`, `tests/test_local_gen_api.py` | M1, M2 | PLANNED |
| 4 | E2E Validation & Adversarial Hardening | `tests/`, full codebase | M1, M2, M3 | PLANNED |

## Interface Contracts
### Style Bible Subsystem (`directo/style_bible/`)
- `CharacterProfile`: `id`, `name`, `base_prompt`, `visual_anchors`, `loras` (list of `LoRAConfig`), `seeds` (fixed/variation), `reference_images`.
- `EnvironmentAnchor`: `id`, `name`, `scenario_prompt`, `lighting`, `color_palette`, `style_tokens`.
- `StyleDirective`: `id`, `name`, `global_prompt_prefix`, `global_prompt_suffix`, `negative_prompt`, `aspect_ratio`, `audio_voice_filters`.
- `StyleBible`: `id`, `name`, `version`, `characters`, `environments`, `directives`. Methods: `to_json()`, `from_json()`, `to_yaml()`, `from_yaml()`.
- `StyleBibleStore`: SQLite store for saving, loading, listing, and exporting Bíblias de Estilo.
- `PromptBuilder`: Methods: `build_prompt(character_ids, environment_id, action_prompt) -> PromptResult` (contains `positive_prompt`, `negative_prompt`, `lora_settings`, `seed_settings`).

### Local Media Generation Hub (`directo/media_hub/`)
- `VideoDriver` Protocol: `generate_video(prompt, loras, seed, duration, aspect_ratio) -> VideoResult`.
  - `ComfyUIVideoDriver`: Uses `NodeRegistry.pick()` for node routing, submits `/prompt` workflow JSONs, monitors WebSocket job execution.
  - `FFmpegRenderer`: Uses `ffmpeg` for visual overlays, transition crossfades, aspect ratio letterboxing, and subtitle burn-in.
- `TTSDriver` Protocol: `synthesize_speech(text, character_id, voice_settings) -> SpeechResult` (audio file path, duration).
  - Implementations: `PiperTTSDriver`, `BarkTTSDriver`, `CoquiTTSDriver`, `MockTTSDriver`.
- `WhisperSubtitleGenerator`: `generate_subtitles(speech_audio_path, dialogue_events) -> SubtitleResult` (.srt, .vtt, .json alignment).
- `AudioMixer`: `mix_tracks(speech_track, bgm_track, sfx_tracks, ducking_config) -> MixedAudioResult`.
- `AudioDuckingEngine`: Applies sidechain compression (attenuating BGM volume by -12dB when speech active).
- `LocalMediaOrchestrator`: Asynchronous facade connecting `StyleBible`, `PromptBuilder`, `VideoDriver`, `TTSDriver`, `WhisperSubtitleGenerator`, and `AudioMixer`.

### API & UI Contracts (`directo/platform/api.py` & `ui/lib/`)
- REST Endpoints:
  - `GET /api/style-bibles`, `POST /api/style-bibles`, `GET /api/style-bibles/{id}`, `PUT /api/style-bibles/{id}`, `DELETE /api/style-bibles/{id}`, `POST /api/style-bibles/import`, `GET /api/style-bibles/{id}/export`
  - `POST /api/media-hub/generate`, `GET /api/media-hub/jobs/{job_id}`, `GET /api/media-hub/jobs/{job_id}/stream`
- UI TypeScript & Zod:
  - `ui/lib/types.ts`: `StyleBible`, `CharacterProfile`, `EnvironmentAnchor`, `StyleDirective`, `MediaGenJob`, `MediaGenRequest`.
  - `ui/lib/schemas.ts`: Zod schemas for request validation.
  - `ui/lib/api.ts`: `api.styleBible` and `api.mediaHub` fetcher methods.

## Code Layout
- `directo/`
  - `style_bible/`
    - `__init__.py`
    - `models.py`
    - `store.py`
    - `prompt_builder.py`
  - `media_hub/`
    - `__init__.py`
    - `orchestrator.py`
    - `video/` (`base.py`, `comfyui.py`, `ffmpeg.py`, `mock.py`)
    - `voices/` (`base.py`, `piper.py`, `bark.py`, `coqui.py`, `mock.py`)
    - `subtitles/` (`whisper.py`, `aligner.py`)
    - `audio/` (`mixer.py`, `ducking.py`)
  - `platform/api.py` (and `directo/api/`)
- `ui/lib/` (`types.ts`, `api.ts`, `schemas.ts`)
- `tests/` (`test_style_bible.py`, `test_prompt_builder.py`, `test_local_media_orchestrator.py`, `test_local_gen_api.py`)
