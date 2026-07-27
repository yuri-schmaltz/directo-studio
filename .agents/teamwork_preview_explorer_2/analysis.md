# Technical Exploration & Design Analysis: Local Media Generation Hub & Style Bible Subsystem

## Executive Summary
Directo Studio is expanding its local creative AI platform to support **Local Media Orchestration** and **Visual & Style Consistency Management**. This report provides a comprehensive technical exploration of existing media, audio, and video capabilities in `directo/`, defines requirements for all upcoming drivers and engines, and formulates clean architectural design patterns, domain models, and class interfaces for `directo/style_bible/` and `directo/media_hub/`.

---

## 1. Analysis of Existing Codebase Capabilities

Investigation of the current `directo/` package reveals several existing assets that establish strong patterns for our target subsystems:

### 1.1 ComfyUI Server Fleet Management (`directo/scale/nodes.py` & `vram.py`)
- **Current State**: `ComfyUINode`, `NodeRegistry`, and `NodeHealth` provide async health checking (`/system_stats`, `/queue`), VRAM capacity inspection, capability tag matching (`flux`, `video`, `sdxl`), and load-balanced routing.
- **Integration Point**: The new ComfyUI API Driver in `directo/media_hub/video/comfyui.py` should leverage `NodeRegistry.pick()` for server selection and execute workflow JSON payloads against ComfyUI `/prompt`, `/history`, and `/view` endpoints over WebSocket/HTTP.

### 1.2 Video Rendering & FFmpeg Stitching (`directo/director/animatic.py`)
- **Current State**: `AnimaticBuilder`, `KenBurnsBackend`, and `AIVideoBackend` provide image-to-video framing, pan-and-zoom motion via PIL, subtitle overlay rendering, and subprocess-based `ffmpeg` clip concatenation (`-f concat -safe 0`) and AAC audio multiplexing (`-c:v copy -c:a aac -shortest`).
- **Integration Point**: `directo/media_hub/video/ffmpeg.py` will encapsulate and extend this FFmpeg pipeline into a reusable video rendering engine supporting overlay composition, transitions, subtitle burn-in, and multi-track audio integration.

### 1.3 Prompt Enhancement (`directo/scale/enhance.py`)
- **Current State**: `PromptEnhancer` uses an adapter pattern (`LLMProvider`) supporting 13+ providers (including offline `TemplateEnhancer`, OpenAI, Anthropic, Ollama, LM Studio) and target model syntax rules (FLUX natural language, SDXL/ComfyUI weighted tags, negative banks).
- **Integration Point**: `directo/style_bible/prompt_builder.py` will build upon `PromptEnhancer` by injecting style directives, character LoRAs, visual anchors, and scenario seeds before delegating syntax optimization to `PromptEnhancer`.

### 1.4 Screenplay Parsing & Cinema Domain (`directo/cinema/parser.py`, `canvas.py`)
- **Current State**: Parses Fountain and Markdown screenplays into `Scene` domain objects containing `slugline`, `action`, `dialogue` (`character`, `text`), and `characters`. `StoryboardCanvas` manages spatial layout of panels.
- **Integration Point**: `LocalMediaOrchestrator` will accept `Scene` objects directly, mapping dialogue lines to TTS voice synthesis per character, action prompts to video generation, and scene metadata to BGM/SFX track selection.

---

## 2. Technical Exploration & Requirements for `directo/media_hub/`

`directo/media_hub/` acts as the local media generation engine. It consists of five key components:

```
directo/media_hub/
├── __init__.py
├── orchestrator.py      # LocalMediaOrchestrator (Facade & async pipeline)
├── video/               # Video & Overlay drivers
│   ├── __init__.py
│   ├── base.py          # VideoDriver Protocol / ABC
│   ├── comfyui.py       # ComfyUI API Driver (workflows: AnimateDiff, Wan 2.2, Hunyuan)
│   ├── ffmpeg.py        # FFmpeg rendering engine & overlay processor
│   └── mock.py          # Universal offline fallback driver
├── voices/              # Local TTS drivers
│   ├── __init__.py
│   ├── base.py          # TTSDriver Protocol / ABC
│   ├── piper.py         # Piper local neural TTS driver
│   ├── bark.py          # Bark expressive transformer TTS driver
│   ├── coqui.py         # Coqui / XTTS voice cloning driver
│   └── mock.py          # Fallback silent/beep TTS driver
├── subtitles/           # Whisper subtitle aligner
│   ├── __init__.py
│   ├── whisper.py       # WhisperSubtitleGenerator & SubtitleAligner
│   └── formatters.py    # SRT, VTT, JSON export formatters
└── audio/               # BGM & SFX ducking audio manager
    ├── __init__.py
    ├── mixer.py         # AudioMixer multi-track engine
    └── ducking.py       # Sidechain audio ducking calculator & FFmpeg filter builder
```

### 2.1 ComfyUI API Driver (`directo/media_hub/video/comfyui.py`)
- **Requirements**:
  - Connect to ComfyUI node endpoints managed by `NodeRegistry`.
  - Transform scene prompts, LoRAs, seeds, resolution, and frame counts into ComfyUI API format JSON workflows (supporting AnimateDiff, SVD, Wan 2.2, HunyuanVideo, CogVideoX).
  - Submit job via `POST /prompt` with `client_id` (UUID).
  - Track execution status over WebSocket (`ws://<node>/ws?clientId=...`) or HTTP polling (`GET /history/{prompt_id}`).
  - Retrieve rendered video bytes via `GET /view?filename=...&type=output`.
  - Implement non-blocking fallback to `FFmpegRenderer` / `MockVideoDriver` on server unreachable or timeout.

### 2.2 FFmpeg Rendering Pipeline (`directo/media_hub/video/ffmpeg.py`)
- **Requirements**:
  - Encapsulate `ffmpeg` subprocess operations into a clean Python API.
  - Video Clip Processing: Frame rate conversion (`-r`), aspect ratio scaling & padding (`scale`, `pad` filters), video codec encoding (`libx264`, `libvpx-vp9`, `hevc`).
  - Overlay Engine: Burn lower thirds, title cards, visual overlays, and watermark badges using FFmpeg `overlay` filter graph.
  - Concatenation: Seamlessly join video clips with optional crossfade/dissolve transition filter graphs or demuxer concat.
  - Subtitle Burn-In: Apply `.srt` / `.vtt` subtitles onto video streams via `subtitles=path.srt:force_style='...'`.

### 2.3 Local TTS Drivers (`directo/media_hub/voices/`)
- **Requirements**:
  - Common `TTSDriver` Protocol with methods `synthesize(text: str, voice_id: str, output_path: str, speed: float = 1.0) -> AudioResult`.
  - **PiperTTSDriver**: Invokes local `piper` binary or `piper-tts` python API. High efficiency, fast CPU/GPU inference, low VRAM footprint. Ideal default for standard voice synthesis.
  - **BarkTTSDriver**: Uses Suno Bark model for emotive speech, background ambient sounds, and non-verbal vocalizations (laughter, sighs). Higher VRAM demand.
  - **CoquiTTSDriver**: Integrates Coqui TTS / XTTS v2 for zero-shot voice cloning given a 3-6 second reference `.wav` audio sample per character.
  - **MockTTSDriver**: Offline mock synthesizer producing synthetic tone/silence audio files with correct duration derived from word count, enabling tests to run without local ML model weights.
  - **Voice Registry**: Maps character names to specific voice configurations (engine, model path, speaker ID, pitch/speed).

### 2.4 Whisper Subtitle Generator & Aligner (`directo/media_hub/subtitles/`)
- **Requirements**:
  - Interface `SubtitleAligner` / `WhisperSubtitleGenerator`.
  - Accept audio files (synthesized narration or full mix) or alignment text.
  - Execute Whisper model inference (via `faster-whisper`, `openai-whisper`, or fallback alignment estimator based on TTS timing).
  - Compute word-level and segment-level start/end timestamps (`start_s`, `end_s`, `text`).
  - Formatter methods:
    - `export_srt() -> str`: Standard SubRip format (`00:00:01,000 --> 00:00:03,500`).
    - `export_vtt() -> str`: WebVTT format (`WEBVTT`).
    - `export_json() -> list[dict]`: Detailed word-level timestamp array for frontend UI rendering.

### 2.5 BGM/SFX Ducking Audio Mixer (`directo/media_hub/audio/`)
- **Requirements**:
  - `AudioMixer` multi-track engine managing 3 primary track categories:
    1. **Narration / Speech**: Character voice lines synthesized by TTS. High priority.
    2. **BGM (Background Music)**: Looping or timed musical score.
    3. **SFX (Sound Effects)**: Spot effects triggered at specific timestamps.
  - **Sidechain Ducking Engine (`AudioDuckingEngine`)**:
    - Detects active intervals of Narration/Speech tracks.
    - Dynamically reduces BGM track volume during speech intervals (e.g., attenuation by -12dB to -18dB) with configurable attack (e.g. 50ms) and release (e.g. 300ms) times.
    - Supports dual implementation modes:
      - FFmpeg filter graph: `sidechaincompress=threshold=0.02:ratio=4:attack=50:release=300`.
      - Python envelope computation: Pure audio volume envelope calculation for precise offline mixing.
  - Export mixed multi-track audio to WAV/AAC/MP3 or stream into FFmpeg video multiplexing step.

---

## 3. Technical Exploration & Requirements for `directo/style_bible/`

`directo/style_bible/` acts as the visual and creative authority, ensuring consistent character features, environment aesthetics, camera framing, color palettes, and prompt syntax across all generated assets.

```
directo/style_bible/
├── __init__.py
├── models.py            # Data structures (StyleBible, CharacterProfile, EnvironmentAnchor, etc.)
├── store.py             # YAML/JSON file persistence & SQLite store
└── prompt_builder.py    # PromptBuilder engine with LoRA & anchor injection
```

### 3.1 Domain Model Specification (`directo/style_bible/models.py`)

#### `CharacterProfile`
- `name: str`: Character identifier (e.g., `"Elena"`).
- `trigger_tag: str`: LoRA or textual inversion trigger token (e.g., `"elena_v2"`).
- `visual_description: str`: Consistent physical description (e.g., `"30-year-old female engineer, sharp jawline, short dark hair, wearing green bomber jacket"`).
- `lora_name: str | None`: Associated LoRA filename/repo (e.g., `"elena_character_v2.safetensors"`).
- `lora_weight: float`: Weight factor (e.g., `0.85`).
- `preferred_voice_id: str | None`: Associated TTS voice ID / reference audio path for voice consistency.
- `reference_image_ids: list[str]`: List of gallery image IDs representing reference turnarounds.

#### `EnvironmentAnchor`
- `name: str`: Location identifier (e.g., `"Cyberpunk Lab"`).
- `location_type: str`: `"INT"` or `"EXT"`.
- `visual_description: str`: Architecture, lighting, objects, atmosphere (e.g., `"Neon-lit underground workshop, holographic screens, cluttered workbenches, moody blue ambient light"`).
- `color_palette: list[str]`: Hex codes or color keywords (e.g., `["#00f0ff", "#ff0055", "#0a0a16"]`).
- `lighting_mood: str`: (e.g., `"high contrast volumetric cyan and magenta"`).
- `camera_defaults: str`: (e.g., `"wide angle lens, eye-level shot"`).
- `lora_name: str | None`: Environment LoRA if applicable.
- `lora_weight: float`: Weight factor (e.g., `0.6`).

#### `StyleDirective`
- `art_style: str`: Master style keyword (e.g., `"Cinematic Realism"`, `"2D Anime"`, `"Stylized Render"`).
- `medium: str`: (e.g., `"35mm anamorphic film, ARRI Alexa"`).
- `master_positive_suffix: str`: Suffix appended to all prompts (e.g., `", cinematic lighting, sharp focus, 8k resolution, masterpiece"`).
- `master_negative_prompt: str`: Default negative prompt (e.g., `"blurry, low quality, distorted, extra limbs, bad anatomy"`).
- `aspect_ratio: str`: Default aspect ratio (e.g., `"16:9"`).
- `seed_policy: str`: `"random"`, `"fixed"`, or `"sequential"`.
- `default_seed: int | None`: Fixed seed value when policy is `"fixed"`.

#### `StyleBible`
- `id: str`: Style bible ID.
- `title: str`: Name of the style bible / project guidelines.
- `version: str`: Version string (e.g., `"1.0.0"`).
- `characters: dict[str, CharacterProfile]`: Keyed by character name.
- `environments: dict[str, EnvironmentAnchor]`: Keyed by environment name.
- `style: StyleDirective`: Global style settings.
- `loras: list[LoRAConfig]`: Global style LoRAs.

### 3.2 Persistence & Storage (`directo/style_bible/store.py`)
- `StyleBibleStore`:
  - `export_yaml(style_bible: StyleBible, path: str | Path)`: Export style bible to readable YAML file.
  - `import_yaml(path: str | Path) -> StyleBible`: Parse YAML file into `StyleBible` object.
  - `export_json(style_bible: StyleBible, path: str | Path)`: Export to JSON format.
  - `import_json(path: str | Path) -> StyleBible`: Parse JSON into `StyleBible`.
  - SQLite Store: `StyleBibleStore(db_path)` for persistent multi-bible database management.

### 3.3 PromptBuilder Architecture (`directo/style_bible/prompt_builder.py`)
- **Design Pattern**: Pipeline Decorator Pattern combined with Strategy Adaptation.
- **Functionality**:
  1. Accepts base prompt text (e.g., `"Elena inspects the broken terminal while Marcus watches the door"`).
  2. Identifies matching characters in the prompt (e.g., `"Elena"`, `"Marcus"`) and injects their `trigger_tag` and physical `visual_description`.
  3. Identifies matching environment or accepts explicit `environment_name` parameter and injects location aesthetics.
  4. Appends master style directives (`art_style`, `medium`, `master_positive_suffix`).
  5. Aggregates character, environment, and global LoRAs into `BuiltPrompt.loras`.
  6. Computes appropriate negative prompt and seed.
  7. Passes the augmented prompt to `PromptEnhancer` for target model syntax tuning (FLUX, SDXL, ComfyUI).

---

## 4. Class Diagrams & Data Interface Contracts

### 4.1 `StyleBible` and `PromptBuilder` Interfaces
```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class BuiltPrompt:
    positive_prompt: str
    negative_prompt: str
    loras: list[dict[str, Any]] = field(default_factory=list)
    seed: int | None = None
    aspect_ratio: str = "16:9"
    metadata: dict[str, Any] = field(default_factory=dict)

class PromptBuilder:
    def __init__(self, style_bible: StyleBible | None = None) -> None:
        self.style_bible = style_bible or StyleBible.default()

    def build_prompt(
        self,
        raw_prompt: str,
        *,
        character_names: list[str] | None = None,
        environment_name: str | None = None,
        target_model: str = "flux-dev",
        override_seed: int | None = None,
    ) -> BuiltPrompt:
        ...
```

### 4.2 `LocalMediaOrchestrator` Facade Interface
```python
from pathlib import Path
from typing import Protocol, Any
from dataclasses import dataclass

@dataclass
class MediaPackage:
    scene_id: str
    video_path: Path
    audio_path: Path | None
    subtitle_path: Path | None
    duration_s: float
    metadata: dict[str, Any]

class LocalMediaOrchestrator:
    def __init__(
        self,
        video_driver: VideoDriver | None = None,
        tts_driver: TTSDriver | None = None,
        subtitle_aligner: SubtitleAligner | None = None,
        audio_mixer: AudioMixer | None = None,
        style_bible: StyleBible | None = None,
    ) -> None:
        ...

    async def generate_scene_media(
        self,
        scene: Scene,
        output_dir: Path,
        *,
        target_model: str = "comfyui",
    ) -> MediaPackage:
        ...
```

---

## 5. Summary of Implementation Strategy & Recommendations

1. **Milestone 1 (`directo/style_bible/`)**:
   - Implement dataclasses in `models.py` with full `to_dict()`, `from_dict()`, `to_yaml()`, `from_yaml()` serialization.
   - Implement `StyleBibleStore` supporting both file persistence (YAML/JSON) and SQLite table management.
   - Implement `PromptBuilder` with regex/token-matching anchor injection and `PromptEnhancer` integration.

2. **Milestone 2 (`directo/media_hub/`)**:
   - Implement driver protocols (`VideoDriver`, `TTSDriver`) and concrete drivers (`ComfyUIVideoDriver`, `FFmpegRenderer`, `PiperTTSDriver`, `BarkTTSDriver`, `CoquiTTSDriver`, `MockTTSDriver`).
   - Implement `WhisperSubtitleGenerator` with SRT/VTT/JSON formatters.
   - Implement `AudioMixer` with `AudioDuckingEngine` sidechain ducking.
   - Implement `LocalMediaOrchestrator` async facade wiring all drivers together.

3. **Milestone 3 (`directo/api/`, `ui/`)**:
   - Expose FastAPI endpoints for active Style Bible selection, media generation triggering, status polling, and WebSocket events.
   - Export TypeScript interfaces to `ui/src/types/`.

4. **Milestone 4 (Verification & Hardening)**:
   - Full Pytest suite pass (`test_style_bible.py`, `test_prompt_builder.py`, `test_local_media_orchestrator.py`, `test_local_gen_api.py`).

