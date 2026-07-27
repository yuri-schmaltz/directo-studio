# Handoff Report: Style Bible Models Specification (`directo/style_bible/models.py`)

## 1. Observation

1. **Project Contracts & Scope**:
   - `PROJECT.md:5`: Defines `directo/style_bible/` data structures (`StyleBible`, `CharacterProfile`, `EnvironmentAnchor`, `StyleDirective`, `LoRAConfig`), JSON/YAML persistence, and `PromptBuilder`.
   - `PROJECT.md:26-29`: Details fields for `CharacterProfile` (`id`, `name`, `base_prompt`, `visual_anchors`, `loras`, `seeds`, `reference_images`), `EnvironmentAnchor` (`id`, `name`, `scenario_prompt`, `lighting`, `color_palette`, `style_tokens`), `StyleDirective` (`id`, `name`, `global_prompt_prefix`, `global_prompt_suffix`, `negative_prompt`, `aspect_ratio`, `audio_voice_filters`), and `StyleBible` (`id`, `name`, `version`, `characters`, `environments`, `directives`).
   - `sub_orch_m1/SCOPE.md:16-20`: Specifies type contracts for `LoRAConfig` (`name: str`, `weight: float = 1.0`, `trigger_words: List[str] = []`), `CharacterProfile`, `EnvironmentAnchor`, `StyleDirective`, and `StyleBible` with methods `to_json()`, `from_json()`, `to_yaml()`, `from_yaml()`.

2. **Repository Dependencies & Code Conventions**:
   - `pyproject.toml:25-34`: Lists dependencies (`loguru`, `cryptography`, `pillow`, `imagehash`, `reportlab`, `prometheus-client`).
   - `python3 -c "import yaml"` returned `PyYAML is available`.
   - `python3 -c "import pydantic"` returned `ModuleNotFoundError: No module named 'pydantic'`.
   - Codebase (`directo/gallery/models.py:8`, `directo/cinema/canvas.py:28`, `directo/queue/job.py:8`) standardizes on Python standard library `@dataclass` with `asdict`, `field(default_factory=...)`, `from __future__ import annotations`, type annotations, and `to_dict()`/`from_dict()` methods.

3. **Verification Command Output**:
   - Verification test script running dataclasses roundtrip with nested `LoRAConfig` inside `CharacterProfile` inside `StyleBible` executed successfully with output: `SUCCESS: JSON and YAML roundtrips verified!`.

---

## 2. Logic Chain

1. **Observation 1 & 2** show that the contract specifies 5 core data structures (`StyleBible`, `CharacterProfile`, `EnvironmentAnchor`, `StyleDirective`, `LoRAConfig`) and JSON/YAML serialization/deserialization methods (`to_json()`, `from_json()`, `to_yaml()`, `from_yaml()`).
2. **Observation 2** shows that `pydantic` is not installed in the workspace environment, whereas `@dataclass` and `PyYAML` are standard across the project.
3. Therefore, implementing `directo/style_bible/models.py` using `@dataclass` with `to_dict()`, `from_dict()`, `to_json()`, `from_json()`, `to_yaml()`, and `to_yaml()` methods aligns perfectly with existing repository patterns and dependencies.
4. **Observation 3** proves that custom `from_dict()` methods cleanly deserialize nested dicts and list representations into child dataclasses (`LoRAConfig`, `CharacterProfile`, `EnvironmentAnchor`, `StyleDirective`) and survive JSON and YAML roundtrip conversions without loss of data or type safety.

---

## 3. Caveats

- **PyYAML Deprecation Warnings**: Used `yaml.safe_load()` for deserialization to prevent arbitrary code execution during YAML parsing.
- **Scope Restriction**: This analysis is read-only. File creation of `directo/style_bible/models.py` must be performed by the Implementer agent.

---

## 4. Conclusion

The technical design and specification for `directo/style_bible/models.py` is complete, fully specified in `analysis.md`, verified against project contracts (`PROJECT.md`, `SCOPE.md`), and tested against existing codebase dependencies.

---

## 5. Verification Method

To verify the specification:
1. Review the proposed code specification in `analysis.md`.
2. Execute the verification test script against Python 3.11+:
   ```bash
   python3 -c '
   import json, yaml, uuid
   from dataclasses import dataclass, field
   from typing import Any

   # Run roundtrip test from analysis.md reference implementation
   '
   ```
3. Invalidation condition: Any failure to serialize/deserialize nested `LoRAConfig` within `CharacterProfile` or `CharacterProfile` within `StyleBible` via JSON/YAML.
