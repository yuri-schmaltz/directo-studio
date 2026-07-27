# Orchestration Plan — Directo Studio Local Media & Style Bible Subsystem

## Overview
Directo Studio requires a comprehensive local media generation hub and style bible subsystem:
1. **R1: Style Bible Engine**: Data structures, JSON/YAML persistence, prompt builder with character/environment anchor injection, LoRA/seed tokens.
2. **R2: Local Media Generation Hub**:
   - Video/Overlays: ComfyUI / AnimateDiff / FFmpeg driver, prompt rendering, visual overlays, fallbacks.
   - Voices & Subtitles: Local TTS (Piper / Bark / Coqui) audio synthesis per character, Whisper subtitle alignment (.srt/.vtt/.json).
   - Audio Manager: BGM & SFX local management, dynamic volume mixing, sidechain ducking.
3. **R3: API Endpoints & UI Integration**:
   - Backend FastAPI endpoints and Pydantic schemas in `directo/`.
   - Frontend TypeScript types and schemas in `ui/`.
4. **Verification**:
   - `tests/test_style_bible.py`
   - `tests/test_prompt_builder.py`
   - `tests/test_local_media_orchestrator.py`
   - `tests/test_local_gen_api.py`

## Strategy & Topology
Using **Project Pattern** with **Dual Track** architecture:

1. **Exploration Phase**:
   - Dispatch 3 `teamwork_preview_explorer` instances to map existing `directo/`, `ui/`, `tests/`, dependencies, and design patterns.

2. **E2E Testing Track**:
   - Requirement-driven, opaque-box test suite design (Tiers 1-4).
   - Publishes `TEST_READY.md` when unit/integration/E2E test harnesses are complete.

3. **Implementation Track**:
   - **Milestone 1**: Style Bible Engine & Prompt Builder (`directo/style_bible/`).
   - **Milestone 2**: Local Media Generation Hub (`directo/media_hub/` - video, audio, voices, whisper subtitles).
   - **Milestone 3**: Backend FastAPI Endpoints & UI Integration (`directo/api/`, `ui/src/types/`).
   - **Milestone 4**: Final E2E Test Suite Pass (Tiers 1-4) & Adversarial Coverage Hardening (Tier 5).

4. **Forensic Integrity Verification**:
   - Mandatory `teamwork_preview_auditor` check on each milestone gate to ensure no cheating, hardcoded mock shortcuts, or dummy facades.
