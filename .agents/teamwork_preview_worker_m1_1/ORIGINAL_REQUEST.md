## 2026-07-26T23:24:57Z
You are Worker 1 for Milestone 1: Style Bible Engine & Prompt Builder (`directo/style_bible/`).
Working directory: /home/yuri/Documentos/directo/.agents/teamwork_preview_worker_m1_1/

Mission:
Implement the complete Style Bible Engine & Prompt Builder subsystem and automated test suite according to project contracts and Explorer specifications.

Specifications to read and follow:
- /home/yuri/Documentos/directo/.agents/PROJECT.md
- /home/yuri/Documentos/directo/.agents/sub_orch_m1/SCOPE.md
- /home/yuri/Documentos/directo/.agents/teamwork_preview_explorer_m1_1/analysis.md (models & serialization specification)
- /home/yuri/Documentos/directo/.agents/teamwork_preview_explorer_m1_2/analysis.md (store & init package specification)
- /home/yuri/Documentos/directo/.agents/teamwork_preview_explorer_m1_3/analysis.md (prompt builder & test suite specification)

Files to create:
1. `directo/style_bible/models.py`: Dataclasses `LoRAConfig`, `CharacterProfile`, `EnvironmentAnchor`, `StyleDirective`, `StyleBible` with `to_dict()`, `from_dict()`, `to_json()`, `from_json()`, `to_yaml()`, `from_yaml()`.
2. `directo/style_bible/store.py`: `StyleBibleStore` SQLite database store supporting `__init__(db_path=":memory:")`, `save_bible()`, `load_bible()`, `list_bibles()`, `delete_bible()`, `export_bible()`, `import_bible()`, context manager (`__enter__`/`__exit__`/`close`), `RLock`, `sqlite3.Row`.
3. `directo/style_bible/prompt_builder.py`: Dataclass `PromptResult` and class `PromptBuilder` with `build_prompt(character_ids, environment_id, directive_id, action_prompt)`.
4. `directo/style_bible/__init__.py`: Package re-exports for `StyleBible`, `CharacterProfile`, `EnvironmentAnchor`, `StyleDirective`, `LoRAConfig`, `StyleBibleStore`, `PromptBuilder`, `PromptResult`, and `__all__`.
5. `tests/test_style_bible.py`: Test suite covering model instantiation, JSON/YAML serialization roundtrips, and `StyleBibleStore` SQLite persistence/CRUD/import/export.
6. `tests/test_prompt_builder.py`: Test suite covering `PromptBuilder` prompt assembly, character visual anchors, LoRA formatting, seeds, environment scenarios, directive prefix/suffix/negative prompts, empty inputs, and prompt string normalization.

Execution & Verification:
- Run tests: `pytest tests/test_style_bible.py tests/test_prompt_builder.py -v`.
- Ensure all tests pass with 100% success rate.
- Write implementation summary in `/home/yuri/Documentos/directo/.agents/teamwork_preview_worker_m1_1/changes.md`.
- Write handoff report in `/home/yuri/Documentos/directo/.agents/teamwork_preview_worker_m1_1/handoff.md` with explicit command outputs and test results.
- Send a summary message to parent sub-orchestrator when finished.
