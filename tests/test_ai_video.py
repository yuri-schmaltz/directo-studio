"""Tests for the pluggable AI Video Backend and animatic generation."""

import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from directo.director.animatic import AIVideoBackend, AnimaticClip


def test_ai_video_backend_mock(tmp_path):
    # Create a dummy source image
    img_path = tmp_path / "source.png"
    Image.new("RGB", (100, 100), (255, 0, 0)).save(img_path)

    clip = AnimaticClip(
        image_path=str(img_path),
        duration_s=1.0,
        narration="Hello from mock AI video backend",
    )

    backend = AIVideoBackend(name="mock")
    assert backend.is_available()

    output_path = tmp_path / "output.mp4"
    result = backend.render_clip(clip, str(output_path), fps=10, resolution=(320, 240))
    assert Path(result).exists()
    assert Path(result).stat().st_size > 0

@pytest.fixture
def api_client(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from directo.platform.api import create_app
    app = create_app(db_dir=tmp_path)
    return TestClient(app)

def test_api_animatics_endpoint(api_client, tmp_path):
    # Create dummy images
    img1 = tmp_path / "img1.png"
    Image.new("RGB", (100, 100), (0, 255, 0)).save(img1)
    img2 = tmp_path / "img2.png"
    Image.new("RGB", (100, 100), (0, 0, 255)).save(img2)

    payload = {
        "project_id": "test_project",
        "title": "My Test Animatic",
        "clips": [
            {
                "image_path": str(img1),
                "duration_s": 1.0,
                "narration": "Clip one",
            },
            {
                "image_path": str(img2),
                "duration_s": 1.0,
                "narration": "Clip two",
            }
        ],
        "backend": "mock",
        "output_path": str(tmp_path / "animatic_out.mp4")
    }

    r = api_client.post("/api/animatics", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "job_id" in data
    assert data["status"] == "enqueued"

    # Get the job status from the API
    job_id = data["job_id"]
    rj = api_client.get(f"/api/jobs/{job_id}")
    assert rj.status_code == 200
    job_data = rj.json()
    assert job_data["kind"] == "animatic.generate"
