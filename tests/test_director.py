"""Tests for the director module (Phase 4)."""

import math
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from directo.director import (
    AnimaticBuilder,
    AnimaticClip,
    AnimaticProject,
    Character,
    CreativeDirector,
    LatentSpaceExplorer,
    MoodboardBuilder,
    ProjectMemory,
    StyleGuide,
    TemplateBackend,
    from_gallery,
)

# ============================================================
# ProjectMemory
# ============================================================


def test_project_memory_crud(tmp_path):
    mem = ProjectMemory(tmp_path / "m.db")
    pid = mem.create_project("Dragon's Perch", "A dragon perches", "Short film")
    assert pid
    p = mem.get_project(pid)
    assert p["name"] == "Dragon's Perch"
    assert p["concept"].startswith("A dragon")
    mem.update_project(pid, concept="updated")
    assert mem.get_project(pid)["concept"] == "updated"
    mem.close()


def test_project_memory_list():
    with ProjectMemory(":memory:") as mem:
        mem.create_project("a")
        mem.create_project("b")
        ps = mem.list_projects()
        assert len(ps) == 2


def test_project_memory_record_decision():
    with ProjectMemory(":memory:") as mem:
        from directo.director.agent import Decision
        d = Decision(id="", decision_key="hero_look", choice="green scales, scarred")
        mem.record_decision(d)
        decisions = mem.get_decisions("any")
        assert any(x.decision_key == "hero_look" for x in decisions)


# ============================================================
# CreativeDirector
# ============================================================


def test_director_create_project_and_add_character():
    mem = ProjectMemory(":memory:")
    director = CreativeDirector(mem, TemplateBackend())
    pid = director.new_project("Test", concept="A test", logline="A test short")
    director.add_character(pid, Character(
        name="Hero", description="brave", visual_traits=["green eyes", "scarred face"]
    ))
    p = mem.get_project(pid)
    assert len(p["characters"]) == 1
    assert p["characters"][0]["name"] == "Hero"
    mem.close()


def test_director_set_style():
    mem = ProjectMemory(":memory:")
    director = CreativeDirector(mem, TemplateBackend())
    pid = director.new_project("Test")
    director.set_style(pid, StyleGuide(
        palette=["#2c1810", "#d4a574"],
        lighting="low-key chiaroscuro",
        camera="anamorphic 35mm",
        mood="ominous",
    ))
    p = mem.get_project(pid)
    assert p["style"]["lighting"] == "low-key chiaroscuro"
    assert p["style"]["camera"] == "anamorphic 35mm"
    mem.close()


def test_director_enrich_prompt_offline_fallback():
    mem = ProjectMemory(":memory:")
    director = CreativeDirector(mem, TemplateBackend())
    pid = director.new_project("Test")
    style = StyleGuide(
        palette=["#2c1810", "#d4a574"],
        camera="anamorphic 35mm",
        lighting="chiaroscuro",
    )
    director.set_style(pid, style)
    enriched = director.enrich_prompt(pid, "a dragon on a cliff")
    # Offline enrich should pull camera + lighting into the prompt
    assert "anamorphic" in enriched or "chiaroscuro" in enriched or "palette" in enriched
    mem.close()


def test_director_plan_shot_list_fallback():
    mem = ProjectMemory(":memory:")
    director = CreativeDirector(mem, TemplateBackend())
    pid = director.new_project("Test")
    shots = director.plan_shot_list(pid, "8-shot reveal sequence", num_shots=6)
    assert len(shots) == 6
    assert all("shot" in s for s in shots)
    mem.close()


def test_director_record_decision():
    mem = ProjectMemory(":memory:")
    director = CreativeDirector(mem, TemplateBackend())
    pid = director.new_project("Test")
    director.record_decision(pid, "hero_costume", "leather + chainmail", rationale="medieval feel")
    decisions = director.list_decisions(pid)
    assert any(d.decision_key == "hero_costume" for d in decisions)
    mem.close()


def test_director_ask():
    mem = ProjectMemory(":memory:")
    director = CreativeDirector(mem, TemplateBackend())
    pid = director.new_project("Test", concept="a quiet morning")
    answer = director.ask(pid, "what's the lighting?")
    # Template backend just returns the input — but it should be a non-empty string
    assert isinstance(answer, str)
    assert answer
    mem.close()


# ============================================================
# Slerp
# ============================================================


def test_slerp_endpoints():
    explorer = LatentSpaceExplorer(":memory:")
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert all(abs(x - y) < 1e-3 for x, y in zip(explorer.slerp(a, b, 0.0), a))
    assert all(abs(x - y) < 1e-3 for x, y in zip(explorer.slerp(a, b, 1.0), b))


def test_slerp_midpoint_unit_norm():
    """At t=0.5, the slerp on the unit sphere should have norm ≈ 1."""
    explorer = LatentSpaceExplorer(":memory:")
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    mid = explorer.slerp(a, b, 0.5)
    norm = math.sqrt(sum(x * x for x in mid))
    assert 0.9 < norm < 1.1  # rescaled to mid-magnitude


def test_slerp_collinear_falls_back_to_lerp():
    explorer = LatentSpaceExplorer(":memory:")
    a = [1.0, 0.0]
    b = [2.0, 0.0]
    mid = explorer.slerp(a, b, 0.5)
    # Should be close to lerp(1.5, 0)
    assert abs(mid[0] - 1.5) < 0.1
    assert abs(mid[1]) < 0.1


def test_slerp_grid_dimensions():
    explorer = LatentSpaceExplorer(":memory:")
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    grid = explorer.grid(a, b, rows=3, cols=4)
    assert grid.rows == 3
    assert grid.cols == 4
    # All cells should have 3 dims
    for row in grid.grid:
        for cell in row:
            assert len(cell) == 3


def test_slerp_grid_first_and_last():
    explorer = LatentSpaceExplorer(":memory:")
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    grid = explorer.grid(a, b, rows=1, cols=3)
    # 1x3 grid: t values 0, 0.5, 1
    first = grid.grid[0][0]
    last = grid.grid[0][2]
    assert first[0] > last[0]  # decreasing
    assert first[1] < last[1]


def test_slerp_save_and_find_by_name():
    explorer = LatentSpaceExplorer(":memory:")
    a_id = explorer.save([1.0, 0.0, 0.0], name="alpha", project="p1")
    b_id = explorer.save([0.0, 1.0, 0.0], name="beta", project="p1")
    assert a_id and b_id
    found = explorer.find_by_name("alpha", project="p1")
    assert found is not None
    assert found["name"] == "alpha"
    assert found["vector"] == [1.0, 0.0, 0.0]


# ============================================================
# Moodboard
# ============================================================


def test_moodboard_basic(tmp_path):
    # Create 3 colored images
    paths = []
    for i, color in enumerate([(220, 100, 50), (50, 100, 220), (100, 200, 100)]):
        p = tmp_path / f"ref_{i}.png"
        Image.new("RGB", (128, 128), color=color).save(p)
        paths.append(p)
    builder = MoodboardBuilder()
    mb = builder.build(paths, title="Test mood", output_dir=tmp_path)
    assert mb.title == "Test mood"
    assert len(mb.palette) > 0
    assert all(c.startswith("#") for c in mb.palette)
    assert len(mb.keywords) > 0
    assert mb.anchor_image_path is not None
    assert Path(mb.anchor_image_path).exists()


def test_moodboard_no_images_raises():
    builder = MoodboardBuilder()
    with pytest.raises(ValueError):
        builder.build([])


def test_moodboard_keywords_warm_cold(tmp_path):
    from directo.director.moodboard import _heuristic_keywords
    warm = tmp_path / "warm_sunset.png"
    cold = tmp_path / "cold_winter.png"
    Image.new("RGB", (32, 32), (220, 100, 50)).save(warm)
    Image.new("RGB", (32, 32), (50, 100, 220)).save(cold)
    kw_warm = _heuristic_keywords(warm)
    kw_cold = _heuristic_keywords(cold)
    # Heuristic picks up "warm" for red-dominant and "cool" for blue-dominant
    assert isinstance(kw_warm, list)
    assert isinstance(kw_cold, list)
    assert "warm" in kw_warm
    assert "cool" in kw_cold


# ============================================================
# Animatic
# ============================================================


@pytest.fixture
def sample_images(tmp_path):
    paths = []
    for i in range(3):
        p = tmp_path / f"frame_{i}.png"
        Image.new("RGB", (640, 360), (i * 80, i * 40, i * 30)).save(p)
        paths.append(p)
    return paths


def test_animatic_from_gallery(tmp_path, sample_images):
    from directo.gallery import ImageRecord
    records = [ImageRecord(path=str(p)) for p in sample_images]
    proj = from_gallery(records, title="Test")
    assert len(proj.clips) == 3
    assert all(c.duration_s > 0 for c in proj.clips)


def test_animatic_builds_ken_burns(tmp_path, sample_images):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    proj = AnimaticProject(
        id="anim1", title="Test", fps=12, resolution=(320, 180),
        clips=[
            AnimaticClip(image_path=str(sample_images[0]), duration_s=0.5),
            AnimaticClip(image_path=str(sample_images[1]), duration_s=0.5),
        ],
    )
    out = tmp_path / "animatic.mp4"
    builder = AnimaticBuilder()
    result = builder.build(proj, out)
    assert result.exists()
    assert result.stat().st_size > 0
    # Verify it's a valid MP4 (ffprobe or just file magic)
    with open(result, "rb") as f:
        sig = f.read(12)
    # MP4 files start with "....ftyp" at offset 4
    assert b"ftyp" in sig


def test_animatic_builder_falls_back_when_backend_unavailable():
    """If the chosen backend is unavailable, the builder tries KenBurns."""
    class UnavailableBackend:
        name = "unavail"
        def is_available(self): return False
        def render_clip(self, *a, **k): raise RuntimeError("nope")

    builder = AnimaticBuilder(backend=UnavailableBackend())
    # Should have fallen back to ken-burns (or its unavailability should be a separate concern)
    assert builder.backend_name == "ken-burns"


def test_animatic_clip_default_zoom():
    c = AnimaticClip(image_path="x.png")
    assert c.zoom_start == 1.0
    assert c.zoom_end == 1.0
    assert c.duration_s == 2.0
