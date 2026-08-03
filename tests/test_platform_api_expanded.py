"""Expanded test suite for directo.platform.api REST & WebSocket endpoints."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from directo.platform.api import create_app


@pytest.fixture
def api_client(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        yield client, tmp_path


def test_health_and_ollama_endpoints(api_client):
    client, _ = api_client
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    resp_ollama = client.get("/health/ollama")
    assert resp_ollama.status_code == 200
    assert "available" in resp_ollama.json()


def test_presets_endpoints_expanded(api_client):
    client, _ = api_client
    resp = client.get("/api/presets")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) > 0

    preset_id = items[0]["id"]
    get_resp = client.get(f"/api/presets/{preset_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == preset_id

    # 404 test
    assert client.get("/api/presets/non_existent_preset_999").status_code == 404

    # Enhance test
    enh_resp = client.post(f"/api/presets/{preset_id}/enhance", json={"prompt": "cyberpunk city", "enhance": False})
    assert enh_resp.status_code == 200
    assert "rendered" in enh_resp.json()


def test_canvas_endpoints(api_client):
    client, _ = api_client
    # List empty
    res = client.get("/api/canvases?project=proj1")
    assert res.status_code == 200
    assert len(res.json()["items"]) == 0

    # Save canvas
    canvas_payload = {
        "id": "canvas_101",
        "project": "proj1",
        "title": "Main Canvas",
        "panels": [],
        "grid": [1, 1],
    }
    save_res = client.post("/api/canvases", json=canvas_payload)
    assert save_res.status_code == 200
    assert save_res.json()["id"] == "canvas_101"

    # Get canvas
    get_res = client.get("/api/canvases/canvas_101")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Main Canvas"

    # 404 test
    assert client.get("/api/canvases/missing_canvas").status_code == 404


def test_projects_crud_endpoints(api_client):
    client, _ = api_client
    # Create project
    create_res = client.post("/api/projects", json={
        "name": "Sci-Fi Film",
        "concept": "AI dystopian world",
        "logline": "A rogue AI seeks humanity",
    })
    assert create_res.status_code == 200
    pid = create_res.json()["id"]

    # List projects
    list_res = client.get("/api/projects")
    assert list_res.status_code == 200
    projects = list_res.json()["items"]
    assert any(p["id"] == pid for p in projects)

    # Update project
    up_res = client.patch(f"/api/projects/{pid}", json={"name": "Sci-Fi Film Director's Cut"})
    assert up_res.status_code == 200
    assert up_res.json()["name"] == "Sci-Fi Film Director's Cut"

    # Enrich prompt
    enrich_res = client.post(f"/api/projects/{pid}/enrich-prompt", json={"prompt": "hero looking at horizon"})
    assert enrich_res.status_code == 200
    assert "enriched" in enrich_res.json()

    # Delete project
    del_res = client.delete(f"/api/projects/{pid}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # 404 on deleted
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_openmontage_bridge_endpoints(api_client):
    client, _ = api_client
    # Pipelines
    p_res = client.get("/api/openmontage/pipelines")
    assert p_res.status_code == 200
    assert p_res.json()["count"] > 0

    # Render prepare
    r_res = client.post("/api/openmontage/render", json={
        "project_id": "cyber_01",
        "pipeline_id": "cyberpunk_trailer",
        "prompt": "neon alley scene",
    })
    assert r_res.status_code == 200
    assert "job_id" in r_res.json()

    # Reference video deconstruction
    v_res = client.post("/api/openmontage/reference-video", json={
        "url": "https://youtube.com/watch?v=demo",
        "topic": "cinematic lighting",
    })
    assert v_res.status_code == 200
    assert "analysis" in v_res.json()
    assert "concepts" in v_res.json()


def test_style_bible_export_format(api_client):
    client, _ = api_client
    # Create style bible
    sb_res = client.post("/api/style-bible", json={
        "id": "sb_cyber",
        "name": "Cyberpunk Style",
        "aesthetic": "Neon and dark rain",
    })
    assert sb_res.status_code == 200

    # Export YAML
    exp_yaml = client.get("/api/style-bible/sb_cyber/export?format=yaml")
    assert exp_yaml.status_code == 200
    assert exp_yaml.headers["content-type"].startswith("application/yaml")

    # Export JSON
    exp_json = client.get("/api/style-bible/sb_cyber/export?format=json")
    assert exp_json.status_code == 200
    assert exp_json.headers["content-type"].startswith("application/json")


def test_settings_api(api_client):
    client, tmp_path = api_client
    get_s = client.get("/api/settings")
    assert get_s.status_code == 200
    assert "llm_backend" in get_s.json()

    save_s = client.post("/api/settings", json={
        "llm_backend": "ollama",
        "ollama_host": "http://localhost:11434",
        "ollama_model": "mistral",
    })
    assert save_s.status_code == 200
    assert save_s.json()["saved"] is True

    # List ollama models mock test
    m_res = client.get("/api/settings/ollama-models?host=http://localhost:11434")
    assert m_res.status_code == 200
    assert isinstance(m_res.json(), list)


def test_storyboard_pdf_errors(api_client):
    client, _ = api_client
    # 400 bad layout
    res_bad = client.post("/api/storyboard/pdf", json={"project": "p1", "layout": "invalid_layout"})
    assert res_bad.status_code == 400

    # 404 no images
    res_empty = client.post("/api/storyboard/pdf", json={"project": "p1", "layout": "2up"})
    assert res_empty.status_code == 404
