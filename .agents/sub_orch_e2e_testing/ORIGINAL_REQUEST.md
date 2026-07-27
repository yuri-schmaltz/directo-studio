# Original User Request

## Initial Request — 2026-07-26T20:23:37-03:00

You are the E2E Testing Track Orchestrator for Directo Studio's Local Media Generation Hub and Style Bible project.
Your assigned working directory is: /home/yuri/Documentos/directo/.agents/sub_orch_e2e_testing
Your parent is: c7a5cd1a-a3e0-4fe8-bac0-b1a083ca7cbd (top-level orchestrator)

Your mission:
Create and validate the opaque-box test suite for Directo Studio's new subsystems based on user requirements:
1. Read /home/yuri/Documentos/directo/.agents/PROJECT.md and /home/yuri/Documentos/directo/.agents/TEST_INFRA.md.
2. Initialize your BRIEFING.md, SCOPE.md, and progress.md in your working directory /home/yuri/Documentos/directo/.agents/sub_orch_e2e_testing/.
3. Decompose and execute test creation across 4 Tiers (Feature Coverage >=5 per feature, Boundary/Corner Cases >=5 per feature, Cross-Feature Combinations, Real-World Application Scenarios):
   - `tests/test_style_bible.py`: Tests for StyleBible models, JSON/YAML persistence, StyleBibleStore SQLite CRUD.
   - `tests/test_prompt_builder.py`: Tests for PromptBuilder visual anchor, LoRA, seed, and style token injection into prompts.
   - `tests/test_local_media_orchestrator.py`: Tests for ComfyUI video driver, FFmpeg renderer, Piper/Bark/Coqui TTS, Whisper subtitles, AudioMixer sidechain ducking, and LocalMediaOrchestrator pipeline (using mocks for offline test stability).
   - `tests/test_local_gen_api.py`: Tests for FastAPI endpoints (/api/style-bibles, /api/media-hub/generate, status polling/WebSocket events).
4. Run `pytest` to verify test suite structure and syntax.
5. Create `/home/yuri/Documentos/directo/.agents/TEST_READY.md` when the test suite is ready.
6. Deliver handoff report and notify parent when done.
