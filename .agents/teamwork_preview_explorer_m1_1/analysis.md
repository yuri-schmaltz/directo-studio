# Technical Analysis & Specification: Style Bible Data Models (`directo/style_bible/models.py`)

## Executive Summary

This report establishes the technical design and detailed code specification for `directo/style_bible/models.py` in Milestone 1 (Style Bible Engine & Prompt Builder). The data models represent the foundational domain objects for managing visual style consistency, prompt composition anchors, seeds, and LoRA model configurations in Directo Studio.

Key findings from codebase inspection:
1. **Core Data Modeling Approach**: The repository standardizes on standard library `@dataclass` (from `dataclasses`) with `from __future__ import annotations`, type hints, and Sphinx/Google-style docstrings. Pydantic is **not** installed in the project environment, so standard dataclasses with explicit `to_dict()` and `from_dict()` serialization patterns (matching `directo/gallery/models.py`, `directo/cinema/canvas.py`, etc.) are used.
2. **YAML & JSON Persistence**: PyYAML (`import yaml`) and `json` are both available and tested. Serialization methods (`to_json()`, `from_json()`, `to_yaml()`, `from_yaml()`) operate on top of dictionary representations (`to_dict()`, `from_dict()`) with full recursive conversion of nested data structures (`LoRAConfig` inside `CharacterProfile`, `CharacterProfile` / `EnvironmentAnchor` / `StyleDirective` inside `StyleBible`).

---

## 1. Repository & Ecosystem Inspection Findings

| Component / Standard | Discovery / Rule | Reference Location |
|----------------------|------------------|--------------------|
| **Python Version** | Python 3.11+ (`>=3.11` in `pyproject.toml`) | `pyproject.toml:10` |
| **Model Framework** | Python `@dataclass` with `asdict` and `field(default_factory=...)` | `directo/gallery/models.py`, `directo/creative/history.py` |
| **Dependencies** | `PyYAML` (installed), `loguru`, `json` (std lib), `sqlite3` (std lib), `pytest` | `pyproject.toml:25-34`, verified via `python3 -c "import yaml"` |
| **Pydantic** | Not installed in environment | Verified via `python3 -c "import pydantic"` (ModuleNotFoundError) |
| **Code Style** | 100 char line limit (Ruff), strict typing, `from __future__ import annotations`, clean docstrings | `pyproject.toml:73-80` |

---

## 2. Specification: Data Models & Interfaces

### 2.1 `LoRAConfig`
Represents configuration for a LoRA model adapter attached to characters or directives.

**Fields & Types**:
- `name: str`: Key or identifier for the LoRA model (e.g., `"anime_style_v2"`). Required.
- `weight: float`: Weight/multiplier for the LoRA (default: `1.0`).
- `trigger_words: list[str]`: List of activation words (default: `field(default_factory=list)`).

**Methods**:
- `to_dict() -> dict[str, Any]`
- `from_dict(data: dict[str, Any]) -> LoRAConfig` (classmethod)

---

### 2.2 `CharacterProfile`
Defines visual traits, base prompts, seeds, and LoRAs for a specific character.

**Fields & Types**:
- `id: str`: Unique identifier (default: `uuid.uuid4().hex`).
- `name: str`: Human-readable name (default: `""`).
- `base_prompt: str`: Core visual descriptor prompt (default: `""`).
- `visual_anchors: list[str]`: Key visual details (clothing, hair, features) (default: `field(default_factory=list)`).
- `loras: list[LoRAConfig]`: List of `LoRAConfig` objects (default: `field(default_factory=list)`).
- `seeds: dict[str, int]`: Mapping for fixed or variation seeds (e.g. `{"fixed": 42}`) (default: `field(default_factory=dict)`).
- `reference_images: list[str]`: Reference image paths or URIs (default: `field(default_factory=list)`).

**Methods**:
- `to_dict() -> dict[str, Any]`
- `from_dict(data: dict[str, Any]) -> CharacterProfile` (classmethod)

---

### 2.3 `EnvironmentAnchor`
Defines background environment details, scenario prompts, lighting, and palette rules.

**Fields & Types**:
- `id: str`: Unique identifier (default: `uuid.uuid4().hex`).
- `name: str`: Human-readable environment name (default: `""`).
- `scenario_prompt: str`: Environmental scene description prompt (default: `""`).
- `lighting: str`: Lighting setup details (e.g. `"dramatic volumetric lighting"`) (default: `""`).
- `color_palette: str`: Palette description (e.g. `"warm sunset tones, gold and deep blue"`) (default: `""`).
- `style_tokens: list[str]`: Environmental style tokens/tags (default: `field(default_factory=list)`).

**Methods**:
- `to_dict() -> dict[str, Any]`
- `from_dict(data: dict[str, Any]) -> EnvironmentAnchor` (classmethod)

---

### 2.4 `StyleDirective`
Defines global aesthetic constraints, prompt wrappers, negative prompts, and voice filters.

**Fields & Types**:
- `id: str`: Unique identifier (default: `uuid.uuid4().hex`).
- `name: str`: Directive name (default: `""`).
- `global_prompt_prefix: str`: Text prepended to positive prompts (default: `""`).
- `global_prompt_suffix: str`: Text appended to positive prompts (default: `""`).
- `negative_prompt: str`: Global negative prompt (default: `""`).
- `aspect_ratio: str`: Target aspect ratio (default: `"16:9"`).
- `audio_voice_filters: dict[str, Any]`: Voice processing configurations (default: `field(default_factory=dict)`).

**Methods**:
- `to_dict() -> dict[str, Any]`
- `from_dict(data: dict[str, Any]) -> StyleDirective` (classmethod)

---

### 2.5 `StyleBible`
The aggregate root model combining character profiles, environment anchors, and style directives.

**Fields & Types**:
- `id: str`: Unique identifier for the Style Bible document (default: `uuid.uuid4().hex`).
- `name: str`: Document title (default: `""`).
- `version: str`: Version tag (default: `"1.0.0"`).
- `characters: dict[str, CharacterProfile]`: Dictionary mapping character ID to `CharacterProfile` (default: `field(default_factory=dict)`).
- `environments: dict[str, EnvironmentAnchor]`: Dictionary mapping environment ID to `EnvironmentAnchor` (default: `field(default_factory=dict)`).
- `directives: dict[str, StyleDirective]`: Dictionary mapping directive ID to `StyleDirective` (default: `field(default_factory=dict)`).

**Methods**:
- `add_character(character: CharacterProfile) -> None`
- `get_character(character_id: str) -> CharacterProfile | None`
- `add_environment(environment: EnvironmentAnchor) -> None`
- `get_environment(environment_id: str) -> EnvironmentAnchor | None`
- `add_directive(directive: StyleDirective) -> None`
- `get_directive(directive_id: str) -> StyleDirective | None`
- `to_dict() -> dict[str, Any]`
- `from_dict(data: dict[str, Any]) -> StyleBible` (classmethod)
- `to_json(indent: int | None = 2) -> str`
- `from_json(json_str: str) -> StyleBible` (classmethod)
- `to_yaml(self) -> str`
- `from_yaml(yaml_str: str) -> StyleBible` (classmethod)

---

## 3. Serialization & Deserialization Strategy

### 3.1 Handling Nested Models
During `to_dict()`, each parent model invokes `to_dict()` on any nested model objects:
- `CharacterProfile.to_dict()` converts its `loras: list[LoRAConfig]` using `[lora.to_dict() if isinstance(lora, LoRAConfig) else lora for lora in self.loras]`.
- `StyleBible.to_dict()` converts `characters`, `environments`, and `directives` dictionary values using `to_dict()`.

During `from_dict()`, parent models deserialize dictionary structures into instances of their respective child dataclasses:
- `CharacterProfile.from_dict()` converts dictionary elements in `loras` into `LoRAConfig` instances.
- `StyleBible.from_dict()` converts dictionaries in `characters`, `environments`, and `directives` into `CharacterProfile`, `EnvironmentAnchor`, and `StyleDirective` instances.

### 3.2 Robustness & Edge Cases
1. **Unrecognized Keys**: `from_dict()` filters incoming dict keys against `cls.__dataclass_fields__` to ensure backward/forward compatibility without raising unexpected argument errors.
2. **Missing Fields**: Optional fields missing from input data default to empty strings, default values, or empty lists/dicts via `field(default_factory=...)`.
3. **Flexible Collection Input**: `StyleBible.from_dict()` supports both dictionary mapping (`{"char_1": {...}}`) and list formats (`[{"id": "char_1", ...}]`) when parsing `characters`, `environments`, or `directives`.
4. **Invalid Input Handling**: `from_json()` and `from_yaml()` check for empty or non-dict parsed contents and raise descriptive `ValueError` or `TypeError` exceptions.

---

## 4. Complete Reference Implementation

Below is the proposed python implementation code for `directo/style_bible/models.py`:

```python
"""Data models for Style Bible Engine & Prompt Builder.

Provides data structures (`LoRAConfig`, `CharacterProfile`, `EnvironmentAnchor`,
`StyleDirective`, `StyleBible`) for visual consistency, prompt composition,
and seed/LoRA configuration management. Supports JSON and YAML serialization/deserialization.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class LoRAConfig:
    """Configuration for a LoRA model adapter.

    Attributes:
        name: Name or file path key of the LoRA model (e.g. "anime_style_v2").
        weight: LoRA strength/multiplier (default: 1.0).
        trigger_words: List of trigger words associated with this LoRA.
    """

    name: str
    weight: float = 1.0
    trigger_words: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert model instance to a dictionary."""
        return {
            "name": self.name,
            "weight": self.weight,
            "trigger_words": list(self.trigger_words),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoRAConfig:
        """Construct model instance from a dictionary."""
        d = dict(data)
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in d.items() if k in valid_keys}
        if "trigger_words" in filtered and filtered["trigger_words"] is None:
            filtered["trigger_words"] = []
        return cls(**filtered)


@dataclass
class CharacterProfile:
    """Visual profile and prompt rules for a character.

    Attributes:
        id: Unique identifier for the character profile.
        name: Human-readable character name.
        base_prompt: Core visual descriptor for the character.
        visual_anchors: Key visual details (clothing, hair, distinctive traits).
        loras: List of LoRAConfig objects associated with this character.
        seeds: Fixed or variation seed configurations (e.g. {"fixed": 42}).
        reference_images: List of paths or URIs to reference images.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    base_prompt: str = ""
    visual_anchors: list[str] = field(default_factory=list)
    loras: list[LoRAConfig] = field(default_factory=list)
    seeds: dict[str, int] = field(default_factory=dict)
    reference_images: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert character profile to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "base_prompt": self.base_prompt,
            "visual_anchors": list(self.visual_anchors),
            "loras": [
                lora.to_dict() if isinstance(lora, LoRAConfig) else lora
                for lora in self.loras
            ],
            "seeds": dict(self.seeds),
            "reference_images": list(self.reference_images),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CharacterProfile:
        """Construct CharacterProfile from a dictionary."""
        d = dict(data)
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in d.items() if k in valid_keys}

        loras_raw = filtered.get("loras", [])
        parsed_loras: list[LoRAConfig] = []
        if loras_raw:
            for item in loras_raw:
                if isinstance(item, LoRAConfig):
                    parsed_loras.append(item)
                elif isinstance(item, dict):
                    parsed_loras.append(LoRAConfig.from_dict(item))
        filtered["loras"] = parsed_loras

        if filtered.get("visual_anchors") is None:
            filtered["visual_anchors"] = []
        if filtered.get("reference_images") is None:
            filtered["reference_images"] = []
        if filtered.get("seeds") is None:
            filtered["seeds"] = {}

        return cls(**filtered)


@dataclass
class EnvironmentAnchor:
    """Environmental context and lighting parameters.

    Attributes:
        id: Unique identifier for the environment anchor.
        name: Human-readable environment name.
        scenario_prompt: Environmental scene description prompt.
        lighting: Lighting setup description.
        color_palette: Dominant color palette description.
        style_tokens: Key environmental style keywords/tags.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    scenario_prompt: str = ""
    lighting: str = ""
    color_palette: str = ""
    style_tokens: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert environment anchor to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "scenario_prompt": self.scenario_prompt,
            "lighting": self.lighting,
            "color_palette": self.color_palette,
            "style_tokens": list(self.style_tokens),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnvironmentAnchor:
        """Construct EnvironmentAnchor from a dictionary."""
        d = dict(data)
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in d.items() if k in valid_keys}
        if filtered.get("style_tokens") is None:
            filtered["style_tokens"] = []
        return cls(**filtered)


@dataclass
class StyleDirective:
    """Global aesthetic directives and generation constraints.

    Attributes:
        id: Unique identifier for the style directive.
        name: Human-readable directive name.
        global_prompt_prefix: Text prepended to positive prompts.
        global_prompt_suffix: Text appended to positive prompts.
        negative_prompt: Default negative prompt text.
        aspect_ratio: Target aspect ratio (default: "16:9").
        audio_voice_filters: Audio/voice processing parameter dictionary.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    global_prompt_prefix: str = ""
    global_prompt_suffix: str = ""
    negative_prompt: str = ""
    aspect_ratio: str = "16:9"
    audio_voice_filters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert style directive to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "global_prompt_prefix": self.global_prompt_prefix,
            "global_prompt_suffix": self.global_prompt_suffix,
            "negative_prompt": self.negative_prompt,
            "aspect_ratio": self.aspect_ratio,
            "audio_voice_filters": dict(self.audio_voice_filters),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StyleDirective:
        """Construct StyleDirective from a dictionary."""
        d = dict(data)
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in d.items() if k in valid_keys}
        if filtered.get("audio_voice_filters") is None:
            filtered["audio_voice_filters"] = {}
        return cls(**filtered)


@dataclass
class StyleBible:
    """Container aggregating character profiles, environment anchors, and style directives.

    Attributes:
        id: Unique identifier for the style bible document.
        name: Human-readable style bible name.
        version: Version string (default: "1.0.0").
        characters: Dictionary mapping character ID to CharacterProfile.
        environments: Dictionary mapping environment ID to EnvironmentAnchor.
        directives: Dictionary mapping directive ID to StyleDirective.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    version: str = "1.0.0"
    characters: dict[str, CharacterProfile] = field(default_factory=dict)
    environments: dict[str, EnvironmentAnchor] = field(default_factory=dict)
    directives: dict[str, StyleDirective] = field(default_factory=dict)

    def add_character(self, character: CharacterProfile) -> None:
        """Add or update a character profile in the style bible."""
        self.characters[character.id] = character

    def get_character(self, character_id: str) -> CharacterProfile | None:
        """Get character profile by ID."""
        return self.characters.get(character_id)

    def add_environment(self, environment: EnvironmentAnchor) -> None:
        """Add or update an environment anchor in the style bible."""
        self.environments[environment.id] = environment

    def get_environment(self, environment_id: str) -> EnvironmentAnchor | None:
        """Get environment anchor by ID."""
        return self.environments.get(environment_id)

    def add_directive(self, directive: StyleDirective) -> None:
        """Add or update a style directive in the style bible."""
        self.directives[directive.id] = directive

    def get_directive(self, directive_id: str) -> StyleDirective | None:
        """Get style directive by ID."""
        return self.directives.get(directive_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert StyleBible into a primitive dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "characters": {
                cid: char.to_dict() if isinstance(char, CharacterProfile) else char
                for cid, char in self.characters.items()
            },
            "environments": {
                eid: env.to_dict() if isinstance(env, EnvironmentAnchor) else env
                for eid, env in self.environments.items()
            },
            "directives": {
                did: dir_obj.to_dict() if isinstance(dir_obj, StyleDirective) else dir_obj
                for did, dir_obj in self.directives.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StyleBible:
        """Construct StyleBible from a dictionary, recursively parsing nested models."""
        d = dict(data)
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in d.items() if k in valid_keys}

        # Deserialize characters
        chars_raw = filtered.get("characters", {})
        parsed_chars: dict[str, CharacterProfile] = {}
        if isinstance(chars_raw, dict):
            for cid, cdata in chars_raw.items():
                if isinstance(cdata, CharacterProfile):
                    parsed_chars[cid] = cdata
                elif isinstance(cdata, dict):
                    profile = CharacterProfile.from_dict(cdata)
                    parsed_chars[profile.id or cid] = profile
        elif isinstance(chars_raw, list):
            for cdata in chars_raw:
                if isinstance(cdata, CharacterProfile):
                    parsed_chars[cdata.id] = cdata
                elif isinstance(cdata, dict):
                    profile = CharacterProfile.from_dict(cdata)
                    parsed_chars[profile.id] = profile
        filtered["characters"] = parsed_chars

        # Deserialize environments
        envs_raw = filtered.get("environments", {})
        parsed_envs: dict[str, EnvironmentAnchor] = {}
        if isinstance(envs_raw, dict):
            for eid, edata in envs_raw.items():
                if isinstance(edata, EnvironmentAnchor):
                    parsed_envs[eid] = edata
                elif isinstance(edata, dict):
                    anchor = EnvironmentAnchor.from_dict(edata)
                    parsed_envs[anchor.id or eid] = anchor
        elif isinstance(envs_raw, list):
            for edata in envs_raw:
                if isinstance(edata, EnvironmentAnchor):
                    parsed_envs[edata.id] = edata
                elif isinstance(edata, dict):
                    anchor = EnvironmentAnchor.from_dict(edata)
                    parsed_envs[anchor.id] = anchor
        filtered["environments"] = parsed_envs

        # Deserialize directives
        dirs_raw = filtered.get("directives", {})
        parsed_dirs: dict[str, StyleDirective] = {}
        if isinstance(dirs_raw, dict):
            for did, ddata in dirs_raw.items():
                if isinstance(ddata, StyleDirective):
                    parsed_dirs[did] = ddata
                elif isinstance(ddata, dict):
                    directive = StyleDirective.from_dict(ddata)
                    parsed_dirs[directive.id or did] = directive
        elif isinstance(dirs_raw, list):
            for ddata in dirs_raw:
                if isinstance(ddata, StyleDirective):
                    parsed_dirs[ddata.id] = ddata
                elif isinstance(ddata, dict):
                    directive = StyleDirective.from_dict(ddata)
                    parsed_dirs[directive.id] = directive
        filtered["directives"] = parsed_dirs

        return cls(**filtered)

    def to_json(self, indent: int | None = 2) -> str:
        """Serialize StyleBible to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> StyleBible:
        """Deserialize StyleBible from JSON string."""
        if not json_str or not json_str.strip():
            raise ValueError("Empty or whitespace JSON string provided")
        data = json.loads(json_str)
        if not isinstance(data, dict):
            raise TypeError(f"Expected JSON object (dict), got {type(data).__name__}")
        return cls.from_dict(data)

    def to_yaml(self) -> str:
        """Serialize StyleBible to YAML string."""
        return yaml.dump(self.to_dict(), sort_keys=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> StyleBible:
        """Deserialize StyleBible from YAML string."""
        if not yaml_str or not yaml_str.strip():
            raise ValueError("Empty or whitespace YAML string provided")
        data = yaml.safe_load(yaml_str)
        if not isinstance(data, dict):
            raise TypeError(f"Expected YAML mapping (dict), got {type(data).__name__}")
        return cls.from_dict(data)
```
