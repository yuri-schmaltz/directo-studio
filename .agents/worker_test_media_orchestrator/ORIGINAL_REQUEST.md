## 2026-07-26T20:24:14-03:00
<USER_REQUEST>
You are the Worker assigned to create and validate the opaque-box test suite `tests/test_local_media_orchestrator.py` for Directo Studio's Local Media Generation Hub.
Your working directory: `/home/yuri/Documentos/directo/.agents/worker_test_media_orchestrator`.
Read `/home/yuri/Documentos/directo/.agents/PROJECT.md` and `/home/yuri/Documentos/directo/.agents/TEST_INFRA.md`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks:
1. Initialize your working directory metadata (`progress.md` heartbeat).
2. Write `tests/test_local_media_orchestrator.py` implementing comprehensive pytest cases across 4 Tiers:
   - Tier 1: Feature Coverage (>=5 test cases per feature area):
     * ComfyUI video driver workflow submission and job monitoring.
     * FFmpeg renderer visual overlays, crossfades, letterboxing, and subtitle burn-in.
     * TTS speech synthesis with Piper, Bark, and Coqui drivers (and Mock fallback).
     * Whisper subtitle generation (.srt, .vtt, .json alignment).
     * AudioMixer multi-track mixing with AudioDuckingEngine sidechain compression (-12dB ducking when speech active).
   - Tier 2: Boundary & Corner Cases (>=5 test cases):
     * Zero duration video generation.
     * Missing audio tracks / empty dialogue events.
     * Invalid aspect ratios (e.g. 0:0 or unformatted strings).
     * Extreme ducking attenuation thresholds (e.g. -60dB or 0dB).
     * Offline ComfyUI node server connection failure fallback.
   - Tier 3: Cross-Feature Interactions:
     * LocalMediaOrchestrator async pipeline coordinating TTS -> Subtitle Alignment -> Audio Ducking -> ComfyUI Driver -> FFmpeg Render.
   - Tier 4: Real-World Scenario:
     * Full Script-to-Video production pipeline scenario with 2 characters talking, BGM ducking during narration, subtitle burn-in, and final video rendering (using mocks for offline test stability).
3. Use unittest.mock / pytest fixtures for external binary/server calls (ffmpeg, comfyui, tts engines) to ensure offline test stability.
4. Run pytest (`.venv/bin/pytest tests/test_local_media_orchestrator.py` or `pytest tests/test_local_media_orchestrator.py`) to verify test suite structure and syntax.
5. Create `handoff.md` in `/home/yuri/Documentos/directo/.agents/worker_test_media_orchestrator/handoff.md` with build/test results, logic chain, and findings, then send a completion message to the parent orchestrator.
</USER_REQUEST>
