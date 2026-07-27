# Technical Design & Testing Strategy: Style Bible Engine & Prompt Builder (Milestone 1)

## Executive Summary
This document presents the complete technical specification for `directo/style_bible/prompt_builder.py` (`PromptBuilder`, `PromptResult`) and the comprehensive testing strategy for `tests/test_style_bible.py` and `tests/test_prompt_builder.py`.

---

## 1. Specification & Technical Design for `prompt_builder.py`

### 1.1 Dataclass / Model: `PromptResult`
The output of prompt composition is represented by `PromptResult`:

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class PromptResult:
    """Encapsulates the output of a prompt composition operation."""
    positive_prompt: str
    negative_prompt: str
    lora_settings: List[Dict[str, Any]] = field(default_factory=list)
    seed_settings: Dict[str, Any]] = field(default_factory=dict)
```

**Field Descriptions**:
- `positive_prompt`: Fully assembled positive prompt string with clean comma separation, formatted `<lora:name:weight>` tags, and trigger words.
- `negative_prompt`: Combined negative prompt string from directive and character/environment negative tokens.
- `lora_settings`: Structured list of dicts for pipeline consumption:
  `[{"name": "cyberpunk_v1", "weight": 0.8, "trigger_words": ["neon glow", "cybernetic"]}]`
- `seed_settings`: Structured dictionary containing fixed and variation seeds:
  `{"characters": {"char_1": {"fixed": 12345, "variation": 67890}}, "directive_seed": 42}`

---

### 1.2 Class Design: `PromptBuilder`

```python
from typing import List, Optional, Dict, Any
from directo.style_bible.models import StyleBible, CharacterProfile, EnvironmentAnchor, StyleDirective

class PromptBuilder:
    """Assembles prompt strings, LoRA triggers, and seed settings from a StyleBible instance."""

    def __init__(self, style_bible: StyleBible) -> None:
        self.style_bible = style_bible

    def build_prompt(
        self,
        character_ids: Optional[List[str]] = None,
        environment_id: Optional[str] = None,
        directive_id: Optional[str] = None,
        action_prompt: str = ""
    ) -> PromptResult:
        ...
```

---

### 1.3 Prompt Composition Logic & Rules

#### A. Positive Prompt Composition
The positive prompt is constructed by assembling tokens in a deterministic order, followed by normalization:

1. **Directive Prefix**: If `directive_id` is provided and exists in `style_bible.directives`, prepend `directive.global_prompt_prefix`.
2. **Characters**: For each ID in `character_ids` (if provided):
   - Fetch `CharacterProfile` from `style_bible.characters`.
   - Append `character.base_prompt`.
   - Append `character.visual_anchors` (joined by `, `).
   - Collect `character.loras` into aggregated LoRA list.
   - Collect `character.seeds` into `seed_settings`.
3. **Action Prompt**: Append `action_prompt` (if non-empty).
4. **Environment**: If `environment_id` is provided and exists in `style_bible.environments`:
   - Fetch `EnvironmentAnchor`.
   - Append `environment.scenario_prompt`.
   - Append `environment.lighting` (if non-empty).
   - Append `environment.color_palette` (if non-empty).
   - Append `environment.style_tokens` (joined by `, `).
5. **Directive Suffix**: If `directive_id` is provided, append `directive.global_prompt_suffix`.
6. **LoRAs and Trigger Words**:
   - For each aggregated LoRA:
     - Format `<lora:name:weight>` tag.
     - Include `trigger_words` in positive prompt if not already present.
7. **String Sanitization / Normalization**:
   - Clean up double commas (`, ,`), extra spaces, leading/trailing whitespace and commas using helper `_normalize_prompt_string()`.

#### B. Negative Prompt Composition
1. If `directive_id` is provided and exists: Start with `directive.negative_prompt`.
2. Collect negative tokens/anchors from characters (if any specified).
3. Collect negative tokens from environment (if any specified).
4. Normalize string with `_normalize_prompt_string()`.

#### C. `lora_settings` Aggregation & Deduplication
- Aggregate `LoRAConfig` objects across all selected characters.
- If multiple characters reference the same LoRA `name`:
  - Retain the highest weight or specified merge strategy.
  - Deduplicate and merge `trigger_words`.
- Convert to list of dicts: `[{"name": ..., "weight": ..., "trigger_words": [...]}]`.

#### D. `seed_settings` Aggregation
- Structure:
  ```python
  seed_settings = {
      "characters": {
          char_id: character.seeds for char_id in selected_characters if character.seeds
      }
  }
  ```

---

### 1.4 Helper Functions in `prompt_builder.py`

```python
def _normalize_prompt_string(text: str) -> str:
    """Cleans up formatting issues in assembled prompt strings.
    - Strips leading/trailing whitespace and commas.
    - Replaces consecutive commas/spaces (e.g. ', ,' or ',,') with a single ', '.
    - Collapses multiple whitespace spaces into single space.
    """
    import re
    if not text:
        return ""
    # Normalize commas
    text = re.sub(r'\s*,\s*', ', ', text)
    text = re.sub(r'(,\s*)+', ', ', text)
    # Strip leading/trailing commas and whitespace
    text = text.strip(' ,')
    # Collapse multiple spaces
    text = re.sub(r' +', ' ', text)
    return text
```

---

## 2. Comprehensive Testing Strategy

### 2.1 Test File 1: `tests/test_style_bible.py`

#### Objective
Verify model data structures, JSON/YAML serialization roundtrips, and `StyleBibleStore` SQLite CRUD & import/export methods.

#### Test Fixtures
- `sample_character`: `CharacterProfile` instance with 2 visual anchors, 1 LoRA, and seeds.
- `sample_environment`: `EnvironmentAnchor` instance with lighting, color palette, style tokens.
- `sample_directive`: `StyleDirective` instance with prefix, suffix, negative prompt, aspect ratio.
- `sample_bible`: `StyleBible` containing 2 characters, 1 environment, 1 directive.
- `temp_store`: `StyleBibleStore` using `:memory:` or temporary file SQLite DB.

#### Unit Test Cases
1. `test_lora_config_instantiation()`: Validate default values (`weight=1.0`, `trigger_words=[]`).
2. `test_character_profile_serialization()`: Roundtrip dict/JSON serialization of character with LoRAs and seeds.
3. `test_environment_anchor_serialization()`: Roundtrip JSON/YAML serialization.
4. `test_style_directive_serialization()`: Roundtrip JSON/YAML serialization.
5. `test_style_bible_json_roundtrip()`: Convert `sample_bible` to JSON and back via `to_json()` and `from_json()`. Verify nested object hierarchy matches original.
6. `test_style_bible_yaml_roundtrip()`: Convert `sample_bible` to YAML and back via `to_yaml()` and `from_yaml()`. Verify equality.
7. `test_store_save_and_load()`: Save `StyleBible` to `StyleBibleStore`, load by ID, verify equality.
8. `test_store_list_bibles()`: Save multiple bibles, verify `list_bibles()` returns list of metadata dicts.
9. `test_store_delete_bible()`: Save bible, delete it, confirm `delete_bible(id)` returns `True` and subsequent `load_bible(id)` returns `None`. Confirm deleting non-existent ID returns `False`.
10. `test_store_export_import_json()`: Export bible to JSON string, import into new store via `import_bible(content, format="json")`, verify imported bible matches.
11. `test_store_export_import_yaml()`: Export bible to YAML string, import via `import_bible(content, format="yaml")`, verify equality.
12. `test_store_invalid_import()`: Test importing malformed JSON/YAML string raises appropriate parsing error.

---

### 2.2 Test File 2: `tests/test_prompt_builder.py`

#### Objective
Verify `PromptBuilder` prompt composition under various input combinations, LoRA formatting, seed aggregation, and negative prompt assembly.

#### Unit Test Cases
1. `test_build_prompt_single_character()`:
   - Call `build_prompt(character_ids=["hero"])`.
   - Assert `positive_prompt` contains base prompt, visual anchors, and `<lora:name:weight>` tag.
   - Assert `lora_settings` and `seed_settings` contain hero's configuration.
2. `test_build_prompt_multi_character()`:
   - Call `build_prompt(character_ids=["hero", "villain"])`.
   - Assert positive prompt combines both base prompts and visual anchors.
   - Assert `lora_settings` collects LoRAs from both characters without duplicates.
   - Assert `seed_settings["characters"]` contains entries for both IDs.
3. `test_build_prompt_with_environment()`:
   - Call `build_prompt(environment_id="cyberpunk_city")`.
   - Assert scenario prompt, lighting, color palette, and style tokens are in `positive_prompt`.
4. `test_build_prompt_with_directive()`:
   - Call `build_prompt(directive_id="cinematic_film")`.
   - Assert `global_prompt_prefix` is at start of positive prompt.
   - Assert `global_prompt_suffix` is at end of positive prompt.
   - Assert `negative_prompt` equals directive's `negative_prompt`.
5. `test_build_prompt_full_combination()`:
   - Call `build_prompt(character_ids=["hero"], environment_id="env1", directive_id="dir1", action_prompt="fighting a dragon")`.
   - Assert positive prompt exact sequence: `[prefix] -> [hero base & anchors] -> [action_prompt] -> [env scenario & tokens] -> [suffix] -> [lora tags & trigger words]`.
6. `test_build_prompt_empty_inputs()`:
   - Call `build_prompt()` with no arguments / defaults.
   - Assert `positive_prompt` and `negative_prompt` return clean empty strings `""`.
7. `test_build_prompt_lora_formatting_and_triggers()`:
   - Character with LoRA `name="cyber_style"`, `weight=0.85`, `trigger_words=["neon neon", "cybernetic"]`.
   - Assert positive prompt contains `<lora:cyber_style:0.85>` and trigger words.
   - Assert `lora_settings` list contains `{"name": "cyber_style", "weight": 0.85, "trigger_words": [...]}`.
8. `test_build_prompt_seed_aggregation()`:
   - Verify character fixed seed (e.g. `1001`) and variation seed (e.g. `2002`) are correctly mapped in `seed_settings`.
9. `test_build_prompt_missing_ids_graceful_handling()`:
   - Pass invalid `character_ids=["unknown_id"]` or invalid `environment_id="missing"`.
   - Verify builder handles missing IDs gracefully (ignores or logs warning without crashing) or raises clear exception per design.
10. `test_prompt_normalization()`:
    - Verify extra whitespace, double commas, and trailing commas are cleaned up correctly in positive and negative prompts.

---

## 3. Implementation Checklist for Milestone 1 Team

- [ ] Implement `directo/style_bible/models.py` (`LoRAConfig`, `CharacterProfile`, `EnvironmentAnchor`, `StyleDirective`, `StyleBible`)
- [ ] Implement `directo/style_bible/store.py` (`StyleBibleStore`)
- [ ] Implement `directo/style_bible/prompt_builder.py` (`PromptResult`, `PromptBuilder`, `_normalize_prompt_string`)
- [ ] Implement `directo/style_bible/__init__.py` package exports
- [ ] Write `tests/test_style_bible.py` covering model serialization & SQLite store operations
- [ ] Write `tests/test_prompt_builder.py` covering prompt assembly scenarios
- [ ] Execute `pytest tests/test_style_bible.py tests/test_prompt_builder.py` and verify all tests pass.
