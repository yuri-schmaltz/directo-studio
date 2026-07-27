# Handoff Report: Style Bible Engine & Prompt Builder Specification (Explorer 3)

## 1. Observation
- Project contracts inspected:
  - `/home/yuri/Documentos/directo/.agents/PROJECT.md`
  - `/home/yuri/Documentos/directo/.agents/sub_orch_m1/SCOPE.md`
- Codebase style inspected from `/home/yuri/Documentos/directo/directo/cinema/canvas.py` and repository structure.
- Requirements for `PromptBuilder` (`directo/style_bible/prompt_builder.py`):
  - Class `PromptBuilder` initialized with a `StyleBible` instance.
  - Method `build_prompt(character_ids: List[str] = None, environment_id: str = None, directive_id: str = None, action_prompt: str = "") -> PromptResult`.
  - Return type `PromptResult` dataclass with fields `positive_prompt`, `negative_prompt`, `lora_settings`, `seed_settings`.
  - Composition logic for positive prompt: directive prefix -> character base prompts & visual anchors -> action prompt -> environment scenario, lighting, color, style tokens -> directive suffix -> `<lora:name:weight>` formatting & trigger words.
  - Negative prompt: directive negative prompt + character/environment negative tokens.
  - LoRA settings aggregation and deduplication.
  - Seed settings aggregation (fixed/variation seeds per character/directive).
- Requirements for test suite:
  - `tests/test_style_bible.py`: JSON/YAML roundtrip serialization of models (`LoRAConfig`, `CharacterProfile`, `EnvironmentAnchor`, `StyleDirective`, `StyleBible`), SQLite `StyleBibleStore` CRUD operations (save, load, list, delete, import, export).
  - `tests/test_prompt_builder.py`: Unit tests for single character, multi-character, environment, directive, action prompt, full composition, empty inputs, LoRA syntax & trigger words, seed aggregation, and prompt string normalization.

## 2. Logic Chain
1. **Model & Builder Specification**: `PromptBuilder` consumes a `StyleBible` object, which holds dictionaries of `characters`, `environments`, and `directives`.
2. **Token Ordering Strategy**: Placing directive prefix first and suffix last allows style framing around character and scene elements. Action prompt is positioned between character base prompts and environment anchors to preserve semantic context.
3. **LoRA Syntax & Settings**: Formatting `<lora:name:weight>` directly into the positive prompt allows direct compatibility with ComfyUI / AUTOMATIC1111 prompt parsers, while returning `lora_settings` as a structured `List[Dict[str, Any]]` provides structured data for native node workflow generators.
4. **Seed Management**: Structuring `seed_settings` by character ID allows downstream media orchestrators to maintain character consistency across multi-shot sequences.
5. **Prompt Normalization**: Using `_normalize_prompt_string()` eliminates malformed prompt artifacts like leading commas, doubled commas, or trailing spaces.
6. **Testing Architecture**:
   - `test_style_bible.py` ensures data models and SQLite store behave correctly for persistence and API operations.
   - `test_prompt_builder.py` validates prompt generation across all parameter combinations and edge cases.

## 3. Caveats
- **Read-Only Scope**: In compliance with Explorer constraints, no source files were modified or created under `directo/` or `tests/`. Implementation files must be created by the Implementer agent.
- **Missing ID Handling**: The specification defines graceful handling (skipping missing IDs or logging warnings) rather than throwing unhandled key errors during prompt construction.

## 4. Conclusion
The technical specification for `PromptBuilder` and `PromptResult`, along with the comprehensive test strategies for `tests/test_style_bible.py` and `tests/test_prompt_builder.py`, are fully formulated and documented in `/home/yuri/Documentos/directo/.agents/teamwork_preview_explorer_m1_3/analysis.md`. The design is completely aligned with `PROJECT.md` and `SCOPE.md` contracts and ready for implementation.

## 5. Verification Method
Once the Implementer agent writes `directo/style_bible/prompt_builder.py`, `tests/test_style_bible.py`, and `tests/test_prompt_builder.py`, verify execution using pytest:

```bash
pytest tests/test_style_bible.py tests/test_prompt_builder.py -v
```

Verification is successful when all unit tests pass with zero failures or warnings.
