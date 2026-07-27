# Original User Request

## Initial Request — 2026-07-26T23:23:37Z

You are the Milestone 1 Sub-Orchestrator for Directo Studio's Style Bible Engine & Prompt Builder (`directo/style_bible/`).
Your assigned working directory is: /home/yuri/Documentos/directo/.agents/sub_orch_m1
Your parent is: c7a5cd1a-a3e0-4fe8-bac0-b1a083ca7cbd (top-level orchestrator)

Your mission:
Execute Milestone 1 (Style Bible Engine & Prompt Builder):
1. Read /home/yuri/Documentos/directo/.agents/PROJECT.md.
2. Initialize your BRIEFING.md, SCOPE.md, and progress.md in /home/yuri/Documentos/directo/.agents/sub_orch_m1/.
3. Decompose work and dispatch Explorer -> Worker -> Reviewer -> Challenger -> Forensic Auditor cycle for `directo/style_bible/`:
   - `directo/style_bible/models.py`: `StyleBible`, `CharacterProfile`, `EnvironmentAnchor`, `StyleDirective`, `LoRAConfig` (with JSON/YAML import/export).
   - `directo/style_bible/store.py`: `StyleBibleStore` SQLite persistence.
   - `directo/style_bible/prompt_builder.py`: `PromptBuilder` for character visual anchors, LoRA tokens, seeds, environment scenario prompts, and negative prompt assembly.
   - `directo/style_bible/__init__.py`: Package exports.
4. Require worker to run tests (`pytest tests/test_style_bible.py tests/test_prompt_builder.py`).
5. Ensure a Forensic Auditor (`teamwork_preview_auditor`) passes clean before completing gate.
6. Deliver handoff report to parent when Milestone 1 is verified.
