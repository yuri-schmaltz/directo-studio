## 2026-07-26T20:24:14Z

You are the Worker assigned to create and validate the opaque-box test suite `tests/test_local_gen_api.py` for Directo Studio's FastAPI Endpoints and UI Integration.
Your working directory: `/home/yuri/Documentos/directo/.agents/worker_test_gen_api`.
Read `/home/yuri/Documentos/directo/.agents/PROJECT.md` and `/home/yuri/Documentos/directo/.agents/TEST_INFRA.md`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks:
1. Initialize your working directory metadata (`progress.md` heartbeat).
2. Write `tests/test_local_gen_api.py` implementing comprehensive pytest cases across 4 Tiers using FastAPI TestClient / httpx:
   - Tier 1: Feature Coverage (>=5 test cases):
     * REST GET/POST/PUT/DELETE `/api/style-bibles` endpoints.
     * REST POST `/api/style-bibles/import` and GET `/api/style-bibles/{id}/export`.
     * REST POST `/api/media-hub/generate` trigger endpoint.
     * REST GET `/api/media-hub/jobs/{job_id}` status polling.
     * WebSocket `/api/media-hub/jobs/{job_id}/stream` event connection.
   - Tier 2: Boundary & Corner Cases (>=5 test cases):
     * 404 response for non-existent job ID or style bible ID.
     * 422 validation response for malformed JSON request bodies.
     * Corrupted file payload on import endpoint.
     * Disconnect and reconnect on WebSocket job stream.
     * Non-JSON payload rejection.
   - Tier 3: Cross-Feature Interactions:
     * Client API flow: POST Style Bible -> GET Style Bible -> POST Media Hub Generation -> GET Job Status -> WebSocket event stream.
   - Tier 4: Real-World Scenario:
     * End-to-end client API flow verifying full REST CRUD, job trigger, WebSocket frame reception, and matching payload structures to TypeScript/Zod interfaces in `ui/lib/`.
3. Import from `directo.platform.api` or `directo.api`. Use TestClient or AsyncClient, with graceful dynamic imports/mocks for missing routes or services.
4. Run pytest (`.venv/bin/pytest tests/test_local_gen_api.py` or `pytest tests/test_local_gen_api.py`) to verify test suite structure and syntax.
5. Create `handoff.md` in `/home/yuri/Documentos/directo/.agents/worker_test_gen_api/handoff.md` with build/test results, logic chain, and findings, then send a completion message to the parent orchestrator.
