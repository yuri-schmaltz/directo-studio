"""Tests for storyboard PDF export."""

import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from directo.printing import (
    StoryboardConfig,
    StoryboardExporter,
    StoryboardLayout,
    StoryboardPanel,
)


@pytest.fixture
def sample_pngs(tmp_path) -> list[Path]:
    paths = []
    for i in range(4):
        p = tmp_path / f"img_{i}.png"
        Image.new("RGB", (640, 360), color=(i * 60, i * 30, i * 90)).save(p)
        paths.append(p)
    return paths


def test_export_one_up(tmp_path, sample_pngs):
    output = tmp_path / "storyboard.pdf"
    exporter = StoryboardExporter(StoryboardConfig(
        layout=StoryboardLayout.ONE_UP, project_title="Test"
    ))
    panels = [
        StoryboardPanel(image_path=str(p), shot_label=f"S{i+1:02d}", caption=f"shot {i}", rating=3)
        for i, p in enumerate(sample_pngs)
    ]
    result = exporter.export(panels, output)
    assert result.exists()
    assert result.stat().st_size > 1000
    # Quick magic-number check
    with open(result, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_export_two_up(tmp_path, sample_pngs):
    output = tmp_path / "two_up.pdf"
    exporter = StoryboardExporter(StoryboardConfig(layout=StoryboardLayout.TWO_UP))
    exporter.export([str(p) for p in sample_pngs], output)
    assert output.exists()


def test_export_four_up(tmp_path, sample_pngs):
    output = tmp_path / "four_up.pdf"
    exporter = StoryboardExporter(StoryboardConfig(layout=StoryboardLayout.FOUR_UP))
    exporter.export([str(p) for p in sample_pngs], output)
    assert output.exists()


def test_export_contact_sheet(tmp_path, sample_pngs):
    output = tmp_path / "contact.pdf"
    exporter = StoryboardExporter(StoryboardConfig(layout=StoryboardLayout.CONTACT))
    exporter.export([str(p) for p in sample_pngs], output)
    assert output.exists()


def test_export_handles_missing_image_gracefully(tmp_path):
    p = tmp_path / "ok.png"
    Image.new("RGB", (32, 32), (50, 50, 50)).save(p)
    output = tmp_path / "with_missing.pdf"
    exporter = StoryboardExporter()
    exporter.export(
        [str(p), str(tmp_path / "does_not_exist.png")],
        output,
    )
    assert output.exists()


def test_export_accepts_strings_only(tmp_path, sample_pngs):
    output = tmp_path / "strings.pdf"
    exporter = StoryboardExporter()
    exporter.export([str(p) for p in sample_pngs], output)
    assert output.exists()
