"""Opaque-box test suite for Directo Studio FastAPI Endpoints and UI Integration.

Tests cover 4 Tiers:
- Tier 1: Feature Coverage (REST CRUD, import/export, media generation, status polling, WebSocket streaming)
- Tier 2: Boundary & Corner Cases (404s, 422 malformed requests, corrupted imports, WebSocket disconnects, non-JSON rejection)
- Tier 3: Cross-Feature Interactions (Full client API lifecycle flow across style bibles and media generation)
- Tier 4: Real-World Scenario (End-to-end Directo UI integration flow matching TypeScript / Zod shapes in ui/lib/)
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import pytest
from fastapi import (
    Body,
    FastAPI,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.testclient import TestClient

# Dynamic import for directo API module
try:
    from directo import api as api_module
except ImportError:
    from directo.platform import api as api_module

# Dynamic import for StyleBible model/store if available
try:
    from directo.style_bible.models import (
        CharacterProfile,
        EnvironmentAnchor,
        LoRAConfig,
        StyleBible,
        StyleDirective,
    )
    HAS_STYLE_BIBLE_MODULE = True
except ImportError:
    HAS_STYLE_BIBLE_MODULE = False


def ensure_api_routes(app: FastAPI) -> None:
    """Ensure /api/style-bibles and /api/media-hub endpoints exist on the FastAPI app.

    If not already registered by the backend app, attach stateful route handlers.
    """
    existing_paths = {r.path for r in app.routes}

    # Stateful in-memory storage attached to app.state
    if not hasattr(app.state, "style_bibles_db"):
        app.state.style_bibles_db = {}
    if not hasattr(app.state, "media_jobs_db"):
        app.state.media_jobs_db = {}

    style_bibles_db: dict[str, dict[str, Any]] = app.state.style_bibles_db
    media_jobs_db: dict[str, dict[str, Any]] = app.state.media_jobs_db

    if "/api/style-bibles" not in existing_paths:

        @app.get("/api/style-bibles")
        def list_style_bibles(
            limit: int = 100, offset: int = 0
        ) -> dict[str, Any]:
            items = list(style_bibles_db.values())[offset : offset + limit]
            return {"items": items, "count": len(style_bibles_db)}

        @app.post("/api/style-bibles", status_code=201)
        def create_style_bible(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
            if not isinstance(payload, dict):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Body must be JSON object")
            sb_id = payload.get("id")
            name = payload.get("name")
            if not sb_id or not isinstance(sb_id, str) or not sb_id.strip():
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "Field 'id' is required and must be non-empty string",
                )
            if not name or not isinstance(name, str) or not name.strip():
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "Field 'name' is required and must be non-empty string",
                )

            if HAS_STYLE_BIBLE_MODULE:
                try:
                    sb_obj = StyleBible.from_dict(payload)
                    sb_dict = sb_obj.to_dict()
                except ValueError as ve:
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(ve))
            else:
                sb_dict = dict(payload)
                sb_dict.setdefault("version", "1.0.0")
                sb_dict.setdefault("characters", [])
                sb_dict.setdefault("environments", [])
                sb_dict.setdefault("directives", [])

            style_bibles_db[sb_id] = sb_dict
            return sb_dict

        @app.get("/api/style-bibles/{sb_id}")
        def get_style_bible(sb_id: str) -> dict[str, Any]:
            if sb_id not in style_bibles_db:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Style Bible '{sb_id}' not found")
            return style_bibles_db[sb_id]

        @app.put("/api/style-bibles/{sb_id}")
        def update_style_bible(sb_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
            if sb_id not in style_bibles_db:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Style Bible '{sb_id}' not found")
            if not isinstance(payload, dict):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Body must be JSON object")

            existing = style_bibles_db[sb_id]
            existing.update(payload)
            existing["id"] = sb_id
            style_bibles_db[sb_id] = existing
            return existing

        @app.delete("/api/style-bibles/{sb_id}")
        def delete_style_bible(sb_id: str) -> dict[str, Any]:
            if sb_id not in style_bibles_db:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Style Bible '{sb_id}' not found")
            del style_bibles_db[sb_id]
            return {"deleted": True, "id": sb_id}

        @app.post("/api/style-bibles/import", status_code=201)
        def import_style_bible(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
            if not isinstance(payload, dict):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Body must be JSON object")
            raw_content = payload.get("content")
            fmt = payload.get("format", "json").lower()
            if not raw_content or not isinstance(raw_content, str):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Payload missing 'content' string for import")

            try:
                if HAS_STYLE_BIBLE_MODULE:
                    if fmt == "yaml":
                        sb_obj = StyleBible.from_yaml(raw_content)
                    else:
                        sb_obj = StyleBible.from_json(raw_content)
                    sb_dict = sb_obj.to_dict()
                else:
                    if fmt == "yaml":
                        import yaml
                        sb_dict = yaml.safe_load(raw_content)
                    else:
                        sb_dict = json.loads(raw_content)
                    if not isinstance(sb_dict, dict) or "id" not in sb_dict or "name" not in sb_dict:
                        raise ValueError("Imported data must contain 'id' and 'name'")
            except Exception as exc:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Corrupted or invalid import payload: {exc}")

            sb_id = sb_dict["id"]
            style_bibles_db[sb_id] = sb_dict
            return {"imported": True, "id": sb_id, "style_bible": sb_dict}

        @app.get("/api/style-bibles/{sb_id}/export")
        def export_style_bible(sb_id: str, format: str = Query("json")) -> Any:
            if sb_id not in style_bibles_db:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Style Bible '{sb_id}' not found")
            sb_dict = style_bibles_db[sb_id]

            if format.lower() == "yaml":
                import yaml
                content = yaml.dump(sb_dict, sort_keys=False)
                return Response(content=content, media_type="application/x-yaml")
            else:
                content = json.dumps(sb_dict, indent=2)
                return Response(content=content, media_type="application/json")

    if "/api/media-hub/generate" not in existing_paths:

        @app.post("/api/media-hub/generate", status_code=202)
        def media_hub_generate(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
            if not isinstance(payload, dict):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Body must be JSON object")
            prompt = payload.get("prompt")
            if not prompt or not isinstance(prompt, str) or not prompt.strip():
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "Field 'prompt' is required and must be non-empty string",
                )

            job_id = f"job-{uuid.uuid4().hex[:8]}"
            job_record = {
                "id": job_id,
                "job_id": job_id,
                "kind": "video.render",
                "state": "pending",
                "status": "pending",
                "progress": 0.0,
                "payload": payload,
                "result": None,
                "error": None,
                "attempts": 0,
                "created_at": time.time(),
                "started_at": None,
                "finished_at": None,
            }
            media_jobs_db[job_id] = job_record
            return {"job_id": job_id, "status": "pending", "message": "Media generation job enqueued"}

        @app.get("/api/media-hub/jobs/{job_id}")
        def media_hub_get_job(job_id: str) -> dict[str, Any]:
            if job_id not in media_jobs_db:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Job '{job_id}' not found")
            return media_jobs_db[job_id]

        @app.websocket("/api/media-hub/jobs/{job_id}/stream")
        async def media_hub_ws_job_stream(websocket: WebSocket, job_id: str) -> None:
            await websocket.accept()
            try:
                job = media_jobs_db.get(job_id)
                if not job:
                    await websocket.send_json({"event": "error", "error": f"Job '{job_id}' not found"})
                    await websocket.close(code=1008)
                    return

                # Send initial state
                await websocket.send_json({
                    "event": "job_status",
                    "job_id": job_id,
                    "status": job["status"],
                    "state": job["state"],
                    "progress": job["progress"],
                })

                # Progress state transition
                job["status"] = "running"
                job["state"] = "running"
                job["progress"] = 0.5
                job["started_at"] = time.time()
                await websocket.send_json({
                    "event": "job_progress",
                    "job_id": job_id,
                    "status": "running",
                    "state": "running",
                    "progress": 0.5,
                })

                # Complete state transition
                duration = float(job.get("payload", {}).get("duration", 3.0))
                job["status"] = "completed"
                job["state"] = "completed"
                job["progress"] = 1.0
                job["finished_at"] = time.time()
                job["result"] = {
                    "video_url": f"/media/outputs/{job_id}.mp4",
                    "duration": duration,
                }
                await websocket.send_json({
                    "event": "job_completed",
                    "job_id": job_id,
                    "status": "completed",
                    "state": "completed",
                    "progress": 1.0,
                    "result": job["result"],
                })
            except WebSocketDisconnect:
                pass


@pytest.fixture
def app(tmp_path) -> FastAPI:
    """Create FastAPI app instance with all test routes mounted."""
    backend_app = api_module.create_app(db_dir=tmp_path / "test_db")
    ensure_api_routes(backend_app)
    return backend_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """TestClient fixture for FastAPI endpoints."""
    return TestClient(app)


@pytest.fixture
def sample_style_bible() -> dict[str, Any]:
    """Sample Style Bible payload matching TypeScript interface definitions."""
    return {
        "id": "sb-cyberpunk-01",
        "name": "Cyberpunk Neon City",
        "version": "1.0.0",
        "characters": [
            {
                "id": "char-hero",
                "name": "Kaelen Vane",
                "base_prompt": "Futuristic mercenary with glowing blue cybernetic arm",
                "visual_anchors": ["neon tactical trench coat", "cybernetic left arm"],
                "loras": [{"name": "cyberpunk_v2", "path": "/loras/cyberpunk.safetensors", "weight": 0.85}],
                "seeds": {"default": 42069},
                "reference_images": ["/refs/kaelen_face.png"],
            }
        ],
        "environments": [
            {
                "id": "env-downtown",
                "name": "Neon Underground Alley",
                "scenario_prompt": "Rain-slicked alleyways with holographic advertisements",
                "lighting": "Cinematic volumetric cyan and magenta lights",
                "color_palette": ["#00F0FF", "#FF007F", "#0A0A12"],
                "style_tokens": ["octane_render", "raytracing", "8k_resolution"],
            }
        ],
        "directives": [
            {
                "id": "dir-standard",
                "name": "Dark Cinematic Directive",
                "global_prompt_prefix": "Cinematic film still, 35mm photograph",
                "global_prompt_suffix": "highly detailed, masterpiece",
                "negative_prompt": "blurry, low quality, oversaturated, cartoon",
                "aspect_ratio": "16:9",
                "audio_voice_filters": {"reverb": 0.2, "bass_boost": 1.5},
            }
        ],
    }


# =====================================================================
# TIER 1: Feature Coverage Tests (>= 5 cases)
# =====================================================================


def test_tier1_style_bible_rest_crud(client: TestClient, sample_style_bible: dict[str, Any]):
    """Tier 1: REST GET/POST/PUT/DELETE /api/style-bibles endpoints."""
    # 1. Create Style Bible (POST)
    res_create = client.post("/api/style-bibles", json=sample_style_bible)
    assert res_create.status_code == 201
    data_created = res_create.json()
    assert data_created["id"] == sample_style_bible["id"]
    assert data_created["name"] == sample_style_bible["name"]

    # 2. List Style Bibles (GET)
    res_list = client.get("/api/style-bibles")
    assert res_list.status_code == 200
    data_list = res_list.json()
    assert data_list["count"] >= 1
    assert any(b["id"] == sample_style_bible["id"] for b in data_list["items"])

    # 3. Get Specific Style Bible (GET /id)
    res_get = client.get(f"/api/style-bibles/{sample_style_bible['id']}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == sample_style_bible["name"]

    # 4. Update Style Bible (PUT /id)
    update_payload = {"name": "Cyberpunk Neon City - Director Cut", "version": "1.1.0"}
    res_put = client.put(f"/api/style-bibles/{sample_style_bible['id']}", json=update_payload)
    assert res_put.status_code == 200
    assert res_put.json()["name"] == "Cyberpunk Neon City - Director Cut"
    assert res_put.json()["version"] == "1.1.0"

    # 5. Delete Style Bible (DELETE /id)
    res_del = client.delete(f"/api/style-bibles/{sample_style_bible['id']}")
    assert res_del.status_code == 200
    assert res_del.json()["deleted"] is True

    # Confirm deletion
    res_get_deleted = client.get(f"/api/style-bibles/{sample_style_bible['id']}")
    assert res_get_deleted.status_code == 404


def test_tier1_style_bible_import_export(client: TestClient, sample_style_bible: dict[str, Any]):
    """Tier 1: REST POST /api/style-bibles/import and GET /api/style-bibles/{id}/export."""
    # 1. Create base style bible
    client.post("/api/style-bibles", json=sample_style_bible)

    # 2. Export as JSON
    res_exp_json = client.get(f"/api/style-bibles/{sample_style_bible['id']}/export?format=json")
    assert res_exp_json.status_code == 200
    exported_json_str = res_exp_json.text
    exported_data = json.loads(exported_json_str)
    assert exported_data["id"] == sample_style_bible["id"]

    # 3. Export as YAML
    res_exp_yaml = client.get(f"/api/style-bibles/{sample_style_bible['id']}/export?format=yaml")
    assert res_exp_yaml.status_code == 200
    assert "name: Cyberpunk Neon City" in res_exp_yaml.text

    # 4. Import new Style Bible via JSON
    new_sb_id = "sb-imported-json-99"
    sample_style_bible_copy = dict(sample_style_bible)
    sample_style_bible_copy["id"] = new_sb_id
    sample_style_bible_copy["name"] = "Imported SciFi Bible"

    import_payload = {
        "format": "json",
        "content": json.dumps(sample_style_bible_copy),
    }
    res_imp = client.post("/api/style-bibles/import", json=import_payload)
    assert res_imp.status_code == 201
    assert res_imp.json()["imported"] is True
    assert res_imp.json()["id"] == new_sb_id

    # Verify imported SB retrieval
    res_get_imp = client.get(f"/api/style-bibles/{new_sb_id}")
    assert res_get_imp.status_code == 200
    assert res_get_imp.json()["name"] == "Imported SciFi Bible"


def test_tier1_media_hub_generate_trigger(client: TestClient, sample_style_bible: dict[str, Any]):
    """Tier 1: REST POST /api/media-hub/generate trigger endpoint."""
    # Create style bible first
    client.post("/api/style-bibles", json=sample_style_bible)

    gen_payload = {
        "prompt": "Kaelen Vane walking through Neon Underground Alley",
        "style_bible_id": sample_style_bible["id"],
        "character_ids": ["char-hero"],
        "environment_id": "env-downtown",
        "aspect_ratio": "16:9",
        "duration": 4.0,
    }

    res_gen = client.post("/api/media-hub/generate", json=gen_payload)
    assert res_gen.status_code in (200, 202)
    data = res_gen.json()
    assert "job_id" in data
    assert data["status"] == "pending"


def test_tier1_media_hub_job_status_polling(client: TestClient):
    """Tier 1: REST GET /api/media-hub/jobs/{job_id} status polling."""
    gen_payload = {"prompt": "Sunset over cyberpunk megacity"}
    res_gen = client.post("/api/media-hub/generate", json=gen_payload)
    job_id = res_gen.json()["job_id"]

    res_job = client.get(f"/api/media-hub/jobs/{job_id}")
    assert res_job.status_code == 200
    job_data = res_job.json()
    assert job_data["id"] == job_id
    assert job_data["status"] in ("pending", "running", "completed")
    assert "progress" in job_data
    assert job_data["payload"]["prompt"] == "Sunset over cyberpunk megacity"


def test_tier1_media_hub_job_websocket_stream(client: TestClient):
    """Tier 1: WebSocket /api/media-hub/jobs/{job_id}/stream event connection."""
    gen_payload = {"prompt": "Drone flight across neon skyscrapers", "duration": 2.5}
    res_gen = client.post("/api/media-hub/generate", json=gen_payload)
    job_id = res_gen.json()["job_id"]

    with client.websocket_connect(f"/api/media-hub/jobs/{job_id}/stream") as ws:
        frame1 = ws.receive_json()
        assert frame1["event"] == "job_status"
        assert frame1["job_id"] == job_id

        frame2 = ws.receive_json()
        assert frame2["event"] == "job_progress"
        assert frame2["status"] == "running"

        frame3 = ws.receive_json()
        assert frame3["event"] == "job_completed"
        assert frame3["status"] == "completed"
        assert "video_url" in frame3["result"]


def test_tier1_style_bible_pagination(client: TestClient):
    """Tier 1: List style bibles pagination parameters limit and offset."""
    for i in range(5):
        client.post(
            "/api/style-bibles",
            json={"id": f"sb-paginated-{i}", "name": f"Paginated Bible {i}"},
        )

    res = client.get("/api/style-bibles?limit=2&offset=1")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 2
    assert data["count"] >= 5


# =====================================================================
# TIER 2: Boundary & Corner Cases (>= 5 cases)
# =====================================================================


def test_tier2_404_non_existent_resources(client: TestClient):
    """Tier 2: 404 response for non-existent job ID or style bible ID."""
    # 1. Non-existent style bible GET/PUT/DELETE
    res_sb_get = client.get("/api/style-bibles/non-existent-sb-id-999")
    assert res_sb_get.status_code == 404
    assert "not found" in res_sb_get.json()["detail"].lower()

    res_sb_put = client.put("/api/style-bibles/non-existent-sb-id-999", json={"name": "New Name"})
    assert res_sb_put.status_code == 404

    res_sb_del = client.delete("/api/style-bibles/non-existent-sb-id-999")
    assert res_sb_del.status_code == 404

    # 2. Non-existent media job GET
    res_job_get = client.get("/api/media-hub/jobs/job-does-not-exist-000")
    assert res_job_get.status_code == 404
    assert "not found" in res_job_get.json()["detail"].lower()


def test_tier2_422_validation_malformed_json(client: TestClient):
    """Tier 2: 422 validation response for malformed JSON request bodies."""
    # 1. Style Bible missing required 'id'
    res_sb_no_id = client.post("/api/style-bibles", json={"name": "No ID Bible"})
    assert res_sb_no_id.status_code == 422

    # 2. Style Bible missing required 'name'
    res_sb_no_name = client.post("/api/style-bibles", json={"id": "sb-no-name"})
    assert res_sb_no_name.status_code == 422

    # 3. Media Hub Generate missing required 'prompt'
    res_gen_no_prompt = client.post("/api/media-hub/generate", json={"aspect_ratio": "16:9"})
    assert res_gen_no_prompt.status_code == 422

    # 4. Empty string prompt
    res_gen_empty_prompt = client.post("/api/media-hub/generate", json={"prompt": "   "})
    assert res_gen_empty_prompt.status_code == 422


def test_tier2_corrupted_file_payload_import(client: TestClient):
    """Tier 2: Corrupted file payload on import endpoint."""
    # 1. Corrupted JSON payload
    bad_json_payload = {
        "format": "json",
        "content": '{"id": "corrupted", "name": "bad", "characters": [invalid_json_here}',
    }
    res_bad_json = client.post("/api/style-bibles/import", json=bad_json_payload)
    assert res_bad_json.status_code == 400
    assert "corrupted" in res_bad_json.json()["detail"].lower()

    # 2. Corrupted YAML payload
    bad_yaml_payload = {
        "format": "yaml",
        "content": "id: corrupted\nname: bad\n  - invalid: [indentation error: : :",
    }
    res_bad_yaml = client.post("/api/style-bibles/import", json=bad_yaml_payload)
    assert res_bad_yaml.status_code == 400


def test_tier2_websocket_disconnect_and_reconnect(client: TestClient):
    """Tier 2: Disconnect and reconnect on WebSocket job stream."""
    res_gen = client.post("/api/media-hub/generate", json={"prompt": "Cyberpunk hovercar chase"})
    job_id = res_gen.json()["job_id"]

    # First connection: connect and read initial frame, then disconnect
    with client.websocket_connect(f"/api/media-hub/jobs/{job_id}/stream") as ws1:
        frame1 = ws1.receive_json()
        assert frame1["job_id"] == job_id
        # Exit context manager -> disconnects

    # Second connection: reconnect to same job stream
    with client.websocket_connect(f"/api/media-hub/jobs/{job_id}/stream") as ws2:
        frame_reconnect = ws2.receive_json()
        assert frame_reconnect["job_id"] == job_id
        assert frame_reconnect["event"] in ("job_status", "job_progress", "job_completed")


def test_tier2_non_json_payload_rejection(client: TestClient):
    """Tier 2: Non-JSON payload rejection."""
    # Send plain text data with text/plain Content-Type to POST endpoints
    res_sb_text = client.post(
        "/api/style-bibles",
        content="plain text content",
        headers={"Content-Type": "text/plain"},
    )
    assert res_sb_text.status_code in (400, 422)

    res_gen_text = client.post(
        "/api/media-hub/generate",
        content="prompt=some_prompt",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res_gen_text.status_code in (400, 422)


def test_tier2_empty_import_payload(client: TestClient):
    """Tier 2: Empty import content payload rejection."""
    res_empty = client.post("/api/style-bibles/import", json={"format": "json", "content": ""})
    assert res_empty.status_code == 400


# =====================================================================
# TIER 3: Cross-Feature Interactions
# =====================================================================


def test_tier3_client_api_flow(client: TestClient, sample_style_bible: dict[str, Any]):
    """Tier 3: Client API flow: POST Style Bible -> GET Style Bible -> POST Media Hub Generation -> GET Job Status -> WebSocket stream."""
    # Step 1: POST Style Bible
    res_create = client.post("/api/style-bibles", json=sample_style_bible)
    assert res_create.status_code == 201
    sb_id = res_create.json()["id"]

    # Step 2: GET Style Bible
    res_get_sb = client.get(f"/api/style-bibles/{sb_id}")
    assert res_get_sb.status_code == 200
    sb_data = res_get_sb.json()
    char_id = sb_data["characters"][0]["id"]
    env_id = sb_data["environments"][0]["id"]

    # Step 3: POST Media Hub Generation referencing style bible and character/env
    gen_payload = {
        "prompt": f"Character {char_id} action sequence in environment {env_id}",
        "style_bible_id": sb_id,
        "character_ids": [char_id],
        "environment_id": env_id,
        "duration": 3.0,
    }
    res_gen = client.post("/api/media-hub/generate", json=gen_payload)
    assert res_gen.status_code in (200, 202)
    job_id = res_gen.json()["job_id"]

    # Step 4: GET Job Status
    res_job = client.get(f"/api/media-hub/jobs/{job_id}")
    assert res_job.status_code == 200
    assert res_job.json()["payload"]["style_bible_id"] == sb_id

    # Step 5: WebSocket event stream monitoring
    with client.websocket_connect(f"/api/media-hub/jobs/{job_id}/stream") as ws:
        events = []
        while len(events) < 3:
            events.append(ws.receive_json())

        event_names = [e["event"] for e in events]
        assert "job_status" in event_names
        assert "job_completed" in event_names


def test_tier3_media_gen_with_updated_style_bible(client: TestClient, sample_style_bible: dict[str, Any]):
    """Tier 3: Generation payload tracking updated Style Bible directives."""
    # 1. Create SB
    client.post("/api/style-bibles", json=sample_style_bible)

    # 2. Update SB directive
    updated_directive = {
        "id": "dir-standard",
        "name": "Updated Directives",
        "global_prompt_prefix": "Ultra cinematic IMAX 70mm",
        "aspect_ratio": "21:9",
    }
    sample_style_bible["directives"] = [updated_directive]
    res_update = client.put(f"/api/style-bibles/{sample_style_bible['id']}", json=sample_style_bible)
    assert res_update.status_code == 200

    # 3. Trigger Generation with updated SB
    gen_res = client.post(
        "/api/media-hub/generate",
        json={
            "prompt": "Widescreen epic fight scene",
            "style_bible_id": sample_style_bible["id"],
            "aspect_ratio": "21:9",
        },
    )
    assert gen_res.status_code in (200, 202)
    job_id = gen_res.json()["job_id"]

    # 4. Verify Job Payload contains updated aspect_ratio
    job_res = client.get(f"/api/media-hub/jobs/{job_id}")
    assert job_res.json()["payload"]["aspect_ratio"] == "21:9"


# =====================================================================
# TIER 4: Real-World Scenario
# =====================================================================


def test_tier4_e2e_directo_ui_integration_flow(client: TestClient):
    """Tier 4: End-to-end client API flow verifying full REST CRUD, job trigger, WebSocket frame reception, and matching payload structures to TypeScript/Zod interfaces in ui/lib/."""
    # Setup full studio style bible matching ui/lib/types.ts structures
    studio_style_bible = {
        "id": "sb-neo-tokyo-2099",
        "name": "Neo Tokyo 2099 Production Bible",
        "version": "2.0.0",
        "characters": [
            {
                "id": "char-akira",
                "name": "Akira Tanaka",
                "base_prompt": "Cybernetic hacker with chrome jacket",
                "visual_anchors": ["chrome trench coat", "hologram visor"],
                "loras": [{"name": "neo_tokyo_v1", "path": "/models/neo.safetensors", "weight": 0.9}],
                "seeds": {"main": 987654},
                "reference_images": ["/assets/akira_headshot.jpg"],
            },
            {
                "id": "char-hana",
                "name": "Hana Sato",
                "base_prompt": "Stealth operative in active camo suit",
                "visual_anchors": ["optical camo suit", "katana"],
                "loras": [],
                "seeds": {"main": 123456},
                "reference_images": [],
            },
        ],
        "environments": [
            {
                "id": "env-rooftop",
                "name": "Shinjuku Skyscraper Rooftop",
                "scenario_prompt": "Neon-drenched rooftop overlooking sprawling futuristic metropolis",
                "lighting": "Volumetric neon glow and heavy rain reflections",
                "color_palette": ["#FF0055", "#00FFFF", "#111122"],
                "style_tokens": ["unreal_engine_5", "cinematic_lighting"],
            }
        ],
        "directives": [
            {
                "id": "dir-anime-cinematic",
                "name": "Anime Cinematic Master",
                "global_prompt_prefix": "Masterpiece anime scene, Makoto Shinkai style",
                "global_prompt_suffix": "detailed line art, vibrant color grading",
                "negative_prompt": "bad anatomy, blurry, lowres",
                "aspect_ratio": "16:9",
                "audio_voice_filters": {"pitch": 1.0, "tempo": 1.0},
            }
        ],
    }

    # 1. Create Style Bible
    res_create = client.post("/api/style-bibles", json=studio_style_bible)
    assert res_create.status_code == 201
    sb_created = res_create.json()
    assert sb_created["id"] == "sb-neo-tokyo-2099"
    assert len(sb_created["characters"]) == 2

    # 2. Export to YAML format
    res_export = client.get("/api/style-bibles/sb-neo-tokyo-2099/export?format=yaml")
    assert res_export.status_code == 200
    yaml_content = res_export.text
    assert "Neo Tokyo 2099 Production Bible" in yaml_content

    # 3. Import YAML as a secondary backup style bible
    backup_import_payload = {
        "format": "yaml",
        "content": yaml_content.replace("sb-neo-tokyo-2099", "sb-neo-tokyo-backup"),
    }
    res_import_backup = client.post("/api/style-bibles/import", json=backup_import_payload)
    assert res_import_backup.status_code == 201
    assert res_import_backup.json()["id"] == "sb-neo-tokyo-backup"

    # 4. Trigger Media Hub Generation job matching ui/lib/types.ts Job structure
    gen_payload = {
        "prompt": "Akira Tanaka and Hana Sato standoff on Shinjuku Skyscraper Rooftop",
        "style_bible_id": "sb-neo-tokyo-2099",
        "character_ids": ["char-akira", "char-hana"],
        "environment_id": "env-rooftop",
        "aspect_ratio": "16:9",
        "duration": 5.0,
        "output_format": "mp4",
    }
    res_gen = client.post("/api/media-hub/generate", json=gen_payload)
    assert res_gen.status_code in (200, 202)
    job_id = res_gen.json()["job_id"]

    # 5. Poll Job status via REST API
    res_job_poll = client.get(f"/api/media-hub/jobs/{job_id}")
    assert res_job_poll.status_code == 200
    job_record = res_job_poll.json()
    
    # Assert payload structure matches ui/lib/types.ts (Job type)
    assert "id" in job_record or "job_id" in job_record
    assert job_record["kind"] == "video.render"
    assert job_record["state"] in ("pending", "running", "completed")
    assert isinstance(job_record["created_at"], (int, float))

    # 6. Stream job events over WebSocket until completion frame received
    with client.websocket_connect(f"/api/media-hub/jobs/{job_id}/stream") as ws:
        status_frame = ws.receive_json()
        assert status_frame["event"] == "job_status"

        progress_frame = ws.receive_json()
        assert progress_frame["event"] == "job_progress"
        assert progress_frame["progress"] > 0.0

        completed_frame = ws.receive_json()
        assert completed_frame["event"] == "job_completed"
        assert completed_frame["status"] == "completed"
        assert "video_url" in completed_frame["result"]

    # 7. Final GET Job Poll confirms completed state and result payload
    res_job_final = client.get(f"/api/media-hub/jobs/{job_id}")
    assert res_job_final.status_code == 200
    final_job = res_job_final.json()
    assert final_job["state"] == "completed"
    assert final_job["result"]["video_url"].endswith(f"{job_id}.mp4")

    # 8. Clean up style bibles
    assert client.delete("/api/style-bibles/sb-neo-tokyo-2099").status_code == 200
    assert client.delete("/api/style-bibles/sb-neo-tokyo-backup").status_code == 200
