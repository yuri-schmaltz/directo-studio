## 2026-07-26T20:24:13Z
You are the Worker assigned to create and validate the opaque-box test suite `tests/test_prompt_builder.py` for Directo Studio's Prompt Builder Subsystem.
Your working directory: `/home/yuri/Documentos/directo/.agents/worker_test_prompt_builder`.
Read `/home/yuri/Documentos/directo/.agents/PROJECT.md` and `/home/yuri/Documentos/directo/.agents/TEST_INFRA.md`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks:
1. Initialize your working directory metadata (`progress.md` heartbeat).
2. Write `tests/test_prompt_builder.py` implementing comprehensive pytest cases across 4 Tiers:
   - Tier 1: Feature Coverage (>=5 test cases):
     * Character visual anchor prompt injection.
     * Environment anchor lighting/scenario injection.
     * LoRA weight formatting syntax (`<lora:name:weight>`).
     * Seed setting (fixed and variation seeds).
     * Style tokens and negative prompt composition.
   - Tier 2: Boundary & Corner Cases (>=5 test cases):
     * Prompt build with no characters selected.
     * Unknown character ID or environment ID error handling.
     * Empty action prompt handling.
     * Special characters, emojis, non-ASCII in prompts.
     * Extreme LoRA weights and empty style tokens.
   - Tier 3: Cross-Feature Interactions:
     * PromptBuilder combining 2 CharacterProfiles + EnvironmentAnchor + Global StyleDirective into unified `PromptResult`.
   - Tier 4: Real-World Scenario:
     * Complex cinematic prompt generation for multi-character scene with visual anchors, multiple LoRAs, fixed seeds, and global negative prompt overrides.
3. Import from `directo.style_bible.prompt_builder` and models. Use graceful dynamic imports/mock fallbacks if necessary for test execution stability.
4. Run pytest (`.venv/bin/pytest tests/test_prompt_builder.py` or `pytest tests/test_prompt_builder.py`) to verify test suite structure and syntax.
5. Create `handoff.md` in `/home/yuri/Documentos/directo/.agents/worker_test_prompt_builder/handoff.md` with build/test results, logic chain, and findings, then send a completion message to the parent orchestrator.
