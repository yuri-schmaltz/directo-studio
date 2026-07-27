# Scope: Milestone 1 - Style Bible Engine & Prompt Builder

## Architecture & Responsibilities
- `directo/style_bible/models.py`: Data models (`StyleBible`, `CharacterProfile`, `EnvironmentAnchor`, `StyleDirective`, `LoRAConfig`), with JSON/YAML serialization/deserialization (`to_json`, `from_json`, `to_yaml`, `from_yaml`).
- `directo/style_bible/store.py`: `StyleBibleStore` SQLite database persistence for saving, loading, listing, deleting, importing, and exporting Style Bibles.
- `directo/style_bible/prompt_builder.py`: `PromptBuilder` for assembling positive/negative prompts, injecting character visual anchors, formatting LoRA triggers (`<lora:name:weight>`), fixed/variation seed settings, environment scenario prompts, global directives, and negative prompts. Returns `PromptResult` object.
- `directo/style_bible/__init__.py`: Package exports.
- `tests/test_style_bible.py` & `tests/test_prompt_builder.py`: Unit and integration test suite.

## Milestone State
| # | Name | Scope | Status |
|---|------|-------|--------|
| 1 | Style Bible Engine & Prompt Builder | `directo/style_bible/`, `tests/test_style_bible.py`, `tests/test_prompt_builder.py` | IN_PROGRESS |

## Interface Contracts
- `LoRAConfig`: `name: str`, `weight: float = 1.0`, `trigger_words: List[str] = []`.
- `CharacterProfile`: `id: str`, `name: str`, `base_prompt: str`, `visual_anchors: List[str]`, `loras: List[LoRAConfig]`, `seeds: Dict[str, int]`, `reference_images: List[str]`.
- `EnvironmentAnchor`: `id: str`, `name: str`, `scenario_prompt: str`, `lighting: str`, `color_palette: str`, `style_tokens: List[str]`.
- `StyleDirective`: `id: str`, `name: str`, `global_prompt_prefix: str`, `global_prompt_suffix: str`, `negative_prompt: str`, `aspect_ratio: str`, `audio_voice_filters: Dict[str, Any]`.
- `StyleBible`: `id: str`, `name: str`, `version: str`, `characters: Dict[str, CharacterProfile]`, `environments: Dict[str, EnvironmentAnchor]`, `directives: Dict[str, StyleDirective]`. Methods: `to_json()`, `from_json()`, `to_yaml()`, `from_yaml()`.
- `StyleBibleStore`: SQLite store `__init__(db_path: str = ":memory:")`, methods: `save_bible(bible)`, `load_bible(id) -> StyleBible`, `list_bibles() -> List[Dict]`, `delete_bible(id) -> bool`, `export_bible(id, format: str) -> str`, `import_bible(content: str, format: str) -> StyleBible`.
- `PromptBuilder`: `__init__(style_bible: StyleBible)` method `build_prompt(character_ids: List[str] = None, environment_id: str = None, directive_id: str = None, action_prompt: str = "") -> PromptResult`.
- `PromptResult`: `positive_prompt: str`, `negative_prompt: str`, `lora_settings: List[Dict[str, Any]]`, `seed_settings: Dict[str, Any]`.
