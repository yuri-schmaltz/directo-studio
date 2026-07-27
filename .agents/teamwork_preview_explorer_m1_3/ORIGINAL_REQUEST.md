## 2026-07-26T23:23:54Z
You are Explorer 3 for Milestone 1: Style Bible Engine & Prompt Builder.
Working directory: /home/yuri/Documentos/directo/.agents/teamwork_preview_explorer_m1_3/

Mission:
1. Read project contracts in /home/yuri/Documentos/directo/.agents/PROJECT.md and /home/yuri/Documentos/directo/.agents/sub_orch_m1/SCOPE.md.
2. Formulate technical design and specification for `directo/style_bible/prompt_builder.py` (`PromptBuilder`):
   - Input: `StyleBible` instance.
   - `build_prompt(character_ids: List[str] = None, environment_id: str = None, directive_id: str = None, action_prompt: str = "") -> PromptResult`
   - Composition logic:
     - Positive prompt: combine directive global_prompt_prefix, character base prompts & visual anchors, action prompt, environment scenario prompt/lighting/color/style tokens, and directive global_prompt_suffix. Also handle formatting LoRA syntax `<lora:name:weight>` or assembling `lora_settings` list.
     - Negative prompt: directive negative_prompt combined with any character/environment negative tokens.
     - `lora_settings`: aggregated list of dicts with name, weight, trigger_words.
     - `seed_settings`: fixed/variation seeds collected from selected characters or directives.
3. Formulate testing strategy for `tests/test_style_bible.py` and `tests/test_prompt_builder.py`:
   - Unit test cases for models (roundtrip JSON/YAML serialization), store (save, load, list, delete, import, export in memory and file DB), and prompt builder (single character, multi-character, with/without environment, with/without directive, negative prompt composition, loras, seeds).
4. Write your analysis to /home/yuri/Documentos/directo/.agents/teamwork_preview_explorer_m1_3/analysis.md and handoff report to /home/yuri/Documentos/directo/.agents/teamwork_preview_explorer_m1_3/handoff.md.
5. Send a summary message to parent sub-orchestrator when complete.
