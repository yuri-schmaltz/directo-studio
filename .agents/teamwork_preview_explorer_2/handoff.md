# Handoff Report — Local Media Generation Hub & Style Bible Exploration

## 1. Observation
1. **Existing ComfyUI Fleet Capabilities (`directo/scale/nodes.py`)**:
   - `ComfyUINode` (lines 50–137) probes server health (`/system_stats`, `/queue`), tracks VRAM (`vram_free_mb`), evaluates job tags (`tags`), and calculates load scores.
   - `NodeRegistry` (lines 156–264) provides in-memory routing via `pick()` with warm affinity support.
2. **Existing FFmpeg & Video Stitching (`directo/director/animatic.py`)**:
   - `KenBurnsBackend` (lines 97–193) uses PIL to frame images and executes `ffmpeg` via `subprocess.run` (`-c:v libx264 -pix_fmt yuv420p -crf 18`).
   - `AnimaticBuilder.build()` (lines 359–420) concatenates MP4 clips using `ffmpeg -f concat` and multiplexes audio using `-c:v copy -c:a aac -shortest`.
3. **Existing Prompt Enhancement (`directo/scale/enhance.py`)**:
   - `PromptEnhancer` (lines 493–580) provides `enhance(prompt, target=...)` supporting model target syntaxes (`flux-dev`, `sdxl`, `comfyui`) and negative prompt defaults.
4. **Existing Script Parser & Canvas State (`directo/cinema/parser.py`, `canvas.py`)**:
   - `parse_script_text()` (lines 307–315) parses Fountain and Markdown scripts into `Scene` objects with `slugline`, `action`, `dialogue` (`character`, `text`), and `characters`.
5. **Absence of Target Subsystems**:
   - `directo/media_hub/` and `directo/style_bible/` do not yet exist in the codebase.
   - `pyproject.toml` contains base requirements (`loguru`, `cryptography`, `pillow`, `imagehash`, `reportlab`, `prometheus-client`) and dev dependencies (`pytest`, `pytest-asyncio`, `pytest-cov`, `mypy`, `ruff`).

---

## 2. Logic Chain
1. **Observation 1 & 2** demonstrate that Directo already possesses functional HTTP/WebSocket probing patterns for ComfyUI servers and subprocess-based FFmpeg video rendering mechanisms.
2. Therefore, `directo/media_hub/video/comfyui.py` can directly extend `NodeRegistry` to route API workflow JSON jobs, while `directo/media_hub/video/ffmpeg.py` can encapsulate and extend the subprocess FFmpeg pipeline for clip rendering, overlay composition, and subtitle burn-in.
3. **Observation 3** shows that `PromptEnhancer` already exists for target syntax translation.
4. Therefore, `directo/style_bible/prompt_builder.py` should be implemented as a Decorator around `PromptEnhancer`, injecting visual anchors, character LoRAs, style directives, scenario tokens, and seed rules prior to calling `PromptEnhancer.enhance()`.
5. **Observation 4** shows that `Scene` objects in `directo/cinema/parser.py` contain structured character dialogue lines and action text.
6. Therefore, `LocalMediaOrchestrator` in `directo/media_hub/orchestrator.py` can directly accept `Scene` objects, mapping dialogue to character TTS voice synthesis (Piper/Bark/Coqui), action to video generation (ComfyUI/FFmpeg), narration to Whisper subtitle generation (.srt/.vtt/.json), and background tracks to `AudioMixer` with sidechain ducking.

---

## 3. Caveats
- Local ML model dependencies (such as `piper`, `bark`, `coqui-tts`, `whisper` / `faster-whisper`) may not be installed in all test execution environments. Thus, fallback mock drivers (`MockVideoDriver`, `MockTTSDriver`, `MockSubtitleAligner`) must be provided so that unit and integration tests can execute offline with zero external binary or GPU requirements.
- ComfyUI API workflows vary depending on the chosen model (AnimateDiff, SVD, Wan 2.2, HunyuanVideo). The driver design should treat workflow JSON payloads as configurable templates.

---

## 4. Conclusion
The technical architecture, domain models, driver specifications, and design patterns for `directo/style_bible/` and `directo/media_hub/` have been defined and documented in detail in `/home/yuri/Documentos/directo/.agents/teamwork_preview_explorer_2/analysis.md`. The design leverages existing codebase patterns in `scale/nodes.py`, `director/animatic.py`, `scale/enhance.py`, and `cinema/parser.py`, and is ready for implementation across Milestones 1 and 2.

---

## 5. Verification Method
1. Inspect the detailed design and interface specifications written in:
   - `/home/yuri/Documentos/directo/.agents/teamwork_preview_explorer_2/analysis.md`
2. Verify existing codebase references:
   - Check ComfyUI server fleet management in `directo/scale/nodes.py`
   - Check FFmpeg video stitching in `directo/director/animatic.py`
   - Check prompt enhancement in `directo/scale/enhance.py`
   - Check screenplay parsing in `directo/cinema/parser.py`
3. Invalidation condition: If `analysis.md` or `handoff.md` are missing from `/home/yuri/Documentos/directo/.agents/teamwork_preview_explorer_2/`, or if recommended interfaces conflict with `PROJECT.md` contracts.
