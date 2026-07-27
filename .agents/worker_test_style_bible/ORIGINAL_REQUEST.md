## 2026-07-26T23:24:13Z

You are the Worker assigned to create and validate the opaque-box test suite `tests/test_style_bible.py` for Directo Studio's Style Bible Subsystem.
Your working directory: `/home/yuri/Documentos/directo/.agents/worker_test_style_bible`.
Read `/home/yuri/Documentos/directo/.agents/PROJECT.md` and `/home/yuri/Documentos/directo/.agents/TEST_INFRA.md`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks:
1. Initialize your working directory metadata (`progress.md` heartbeat).
2. Write `tests/test_style_bible.py` implementing comprehensive pytest cases across 4 Tiers:
   - Tier 1: Feature Coverage (>=5 test cases):
     * StyleBible model creation with characters, environments, and directives.
     * CharacterProfile & EnvironmentAnchor model validations.
     * StyleBible JSON serialization and deserialization roundtrip.
     * StyleBible YAML serialization and deserialization roundtrip.
     * StyleBibleStore SQLite CRUD (save, load, list, search, export, import).
   - Tier 2: Boundary & Corner Cases (>=5 test cases):
     * Empty character list / empty directives.
     * Extreme or invalid IDs / non-existent SQLite query IDs.
     * Corrupted JSON or YAML string error handling.
     * Missing SQLite database path / permission handling.
     * Extreme LoRA weights (e.g. negative or >2.0) and duplicate names.
   - Tier 3: Cross-Feature Interactions:
     * Export StyleBible to YAML -> load into fresh StyleBibleStore -> lookup character profile -> resolve prompt directives.
   - Tier 4: Real-World Scenario:
     * End-to-end multi-character Style Bible lifecycle with multiple LoRAs, visual anchors, exporting to JSON file, importing into SQLite store, and verifying profile state.
3. Import from `directo.style_bible.models` and `directo.style_bible.store`. If the modules are not yet fully implemented or installed, use graceful dynamic imports/mock fallbacks so that pytest executes and passes cleanly.
4. Run pytest (`.venv/bin/pytest tests/test_style_bible.py` or `pytest tests/test_style_bible.py`) to verify test suite structure and syntax.
5. Create `handoff.md` in `/home/yuri/Documentos/directo/.agents/worker_test_style_bible/handoff.md` with build/test results, logic chain, and findings, then send a completion message to the parent orchestrator.
