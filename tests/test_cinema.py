"""Tests for the cinema module (Phase 3)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from directo.cinema import (
    CanvasStore,
    CinemaEngine,
    Panel,
    RuleKind,
    Scene,
    StoryboardCanvas,
    parse_fountain,
    parse_plain_text,
    parse_script,
    parse_script_text,
    scenes_to_prompts,
)
from directo.cinema.engine import _builtin_rules


# ============================================================
# Cinema rules engine
# ============================================================


def test_engine_has_builtin_rules():
    engine = CinemaEngine()
    assert engine.rule_count >= 18  # era + physics + cinema + consistency


def test_era_rule_blocks_smartphone_in_1920s():
    engine = CinemaEngine()
    report = engine.evaluate(
        "a man on a rooftop using a smartphone",
        context={"era": "1920-1930"},
    )
    assert report.blocked
    assert any("smartphone" in w for w in report.warnings)


def test_era_rule_passes_compatible_prompt():
    engine = CinemaEngine()
    report = engine.evaluate(
        "a man on a rooftop, 1920s clothing",
        context={"era": "1920-1930"},
    )
    assert not report.blocked


def test_physics_rule_blocks_underwater_fire():
    engine = CinemaEngine()
    report = engine.evaluate("a man breathing fire underwater in a sunken ship")
    assert report.blocked
    assert any("fire" in w.lower() and "water" in w.lower() for w in report.warnings)


def test_cinematography_suggestion_short_prompt():
    engine = CinemaEngine()
    report = engine.evaluate("dragon")
    # Short prompt → suggestions
    assert report.suggestions
    assert "lighting" in report.suggestions[0] or "lens" in report.suggestions[0]


def test_cinematography_suggestion_long_prompt_skipped():
    engine = CinemaEngine()
    # Comprehensive prompt with all cinema cues present
    long = ("a dragon on a cliff at dawn, 35mm lens, golden hour lighting, "
            "low angle cinematic shot, 2.39:1 anamorphic, warm color grade")
    report = engine.evaluate(long)
    # All the cinema cues are there → no suggests
    assert not report.suggestions


def test_consistency_injection():
    engine = CinemaEngine()
    report = engine.evaluate(
        "the hero stands tall",
        context={"character": "a green-scaled dragon with torn wing"},
    )
    assert "green-scaled dragon" in report.augmented_prompt
    assert any("inject" in r.message.lower() for r in report.results)


def test_skip_suggests_context():
    engine = CinemaEngine()
    report = engine.evaluate("dragon", context={"skip_suggests": True})
    assert not report.suggestions


def test_auto_apply_suggests_can_be_disabled():
    engine = CinemaEngine()
    report = engine.evaluate("dragon", context={"auto_apply_suggests": False})
    # Suggestions still computed but not auto-applied
    assert report.suggestions
    assert all(s not in report.augmented_prompt for s in report.suggestions)


def test_custom_rule_added():
    engine = CinemaEngine()
    from directo.cinema.engine import RuleResult, Rule

    def no_purple(prompt: str, context: dict) -> list[RuleResult]:
        if "purple" in prompt.lower():
            return [RuleResult(
                rule_id="no-purple", rule_name="no purple",
                kind=RuleKind.WARN, message="purple is forbidden",
            )]
        return []

    engine.add_rule(no_purple)
    report = engine.evaluate("a purple dragon")
    assert any("purple" in w.lower() for w in report.warnings)


def test_remove_rule():
    engine = CinemaEngine()
    before = engine.rule_count
    engine.remove_rule(lambda r: r is engine._rules[0])  # remove first
    assert engine.rule_count == before - 1


# ============================================================
# Storyboard canvas
# ============================================================


def test_canvas_add_and_move_panel():
    canvas = StoryboardCanvas(id="c1", project="p", title="test")
    p = canvas.add_panel(x=100, y=200, width=320, height=180)
    assert p.id in canvas.panels
    assert p.x == 100
    canvas.move_panel(p.id, 500, 600)
    assert canvas.panels[p.id].x == 500
    assert canvas.panels[p.id].y == 600


def test_canvas_resize_panel():
    canvas = StoryboardCanvas(id="c1", project="p")
    p = canvas.add_panel()
    canvas.resize_panel(p.id, 640, 360)
    assert canvas.panels[p.id].width == 640


def test_canvas_remove_panel():
    canvas = StoryboardCanvas(id="c1", project="p")
    p = canvas.add_panel()
    assert canvas.remove_panel(p.id) is True
    assert canvas.remove_panel(p.id) is False


def test_canvas_set_image_records_history():
    canvas = StoryboardCanvas(id="c1", project="p")
    p = canvas.add_panel()
    canvas.set_panel_image(p.id, "img-1")
    canvas.set_panel_image(p.id, "img-2")
    rec = canvas.panels[p.id]
    assert rec.image_id == "img-2"
    assert "img-1" in rec.history_image_ids


def test_canvas_panels_in_rect():
    canvas = StoryboardCanvas(id="c1", project="p")
    canvas.add_panel(x=0, y=0, width=100, height=100)
    canvas.add_panel(x=500, y=500, width=100, height=100)
    in_view = canvas.panels_in_rect(0, 0, 200, 200)
    assert len(in_view) == 1  # only the (0,0) panel
    out_of_view = canvas.panels_in_rect(200, 200, 100, 100)
    assert len(out_of_view) == 0  # neither panel is in this far-away region


def test_canvas_to_grid():
    canvas = StoryboardCanvas(id="c1", project="p")
    for i in range(6):
        canvas.add_panel(shot_label=f"S{i+1:02d}")
    grid = canvas.to_grid(cols=3)
    assert len(grid) == 6


def test_canvas_store_round_trip():
    with CanvasStore(":memory:") as store:
        c = StoryboardCanvas(id="c1", project="p", title="My Canvas")
        c.add_panel(shot_label="S01", x=10, y=20)
        c.add_panel(shot_label="S02", x=350, y=20)
        store.save(c)
        loaded = store.get("c1")
        assert loaded is not None
        assert loaded.title == "My Canvas"
        assert len(loaded.panels) == 2
        assert "S01" in {p.shot_label for p in loaded.panels.values()}


def test_canvas_store_list_for_project():
    with CanvasStore(":memory:") as store:
        store.save(StoryboardCanvas(id="c1", project="alpha"))
        store.save(StoryboardCanvas(id="c2", project="alpha"))
        store.save(StoryboardCanvas(id="c3", project="beta"))
        alpha = store.list_for_project("alpha")
        assert len(alpha) == 2
        beta = store.list_for_project("beta")
        assert len(beta) == 1


# ============================================================
# Script parser
# ============================================================


SAMPLE_FOUNTAIN = """Title: Test Script

INT. KITCHEN - DAY

A man stands at the stove, frying eggs. Steam rises.

WIFE
(softly)
Coffee's ready.

He turns, surprised. A beat.

WIFE (CONT'D)
You're burning the eggs.

EXT. STREET - NIGHT

A car pulls up to a curb. The headlights die.

INT. OFFICE - DAY

The same man, older now, sits behind a desk.

BOSS
You wanted to see me?
"""


def test_parse_fountain_scene_count():
    scenes = parse_fountain(SAMPLE_FOUNTAIN)
    assert len(scenes) == 3


def test_parse_fountain_slugline_parsing():
    scenes = parse_fountain(SAMPLE_FOUNTAIN)
    kitchen = scenes[0]
    assert kitchen.location.upper() == "KITCHEN"
    assert kitchen.time_of_day.upper() == "DAY"
    assert kitchen.interior is True


def test_parse_fountain_ext_scene():
    scenes = parse_fountain(SAMPLE_FOUNTAIN)
    street = scenes[1]
    assert street.interior is False
    assert street.time_of_day.upper() == "NIGHT"


def test_parse_fountain_dialogue():
    scenes = parse_fountain(SAMPLE_FOUNTAIN)
    kitchen = scenes[0]
    assert len(kitchen.dialogue) == 2
    assert kitchen.dialogue[0].character == "WIFE"
    assert "Coffee" in kitchen.dialogue[0].text


def test_parse_fountain_characters():
    scenes = parse_fountain(SAMPLE_FOUNTAIN)
    chars: set[str] = set()
    for s in scenes:
        chars.update(s.characters)
    assert "WIFE" in chars
    assert "BOSS" in chars


def test_parse_fountain_to_prompt():
    scenes = parse_fountain(SAMPLE_FOUNTAIN)
    p = scenes[0].to_prompt()
    assert "KITCHEN" in p.upper() or "DAY" in p.upper()


def test_parse_plain_text_one_scene_per_paragraph():
    text = "First paragraph about a scene.\n\nSecond paragraph about another scene."
    scenes = parse_plain_text(text, paragraphs_per_scene=1)
    assert len(scenes) == 2


def test_parse_plain_text_groups_paragraphs():
    text = "Para 1.\n\nPara 2.\n\nPara 3."
    scenes = parse_plain_text(text, paragraphs_per_scene=2)
    assert len(scenes) == 2
    assert "Para 1" in scenes[0].action
    assert "Para 2" in scenes[0].action
    assert "Para 3" in scenes[1].action


def test_parse_script_text_detects_fountain():
    scenes = parse_script_text(SAMPLE_FOUNTAIN, hint=".fountain")
    assert len(scenes) == 3


def test_parse_script_text_plain_fallback():
    scenes = parse_script_text("just a single paragraph", hint=".txt")
    assert len(scenes) == 1


def test_scenes_to_prompts():
    scenes = parse_fountain(SAMPLE_FOUNTAIN)
    prompts = scenes_to_prompts(scenes)
    assert len(prompts) == 3
    assert all("slugline" in p for p in prompts)
    assert all("prompt" in p for p in prompts)
    assert all("characters" in p for p in prompts)


def test_parse_script_file(tmp_path):
    f = tmp_path / "test.fountain"
    f.write_text(SAMPLE_FOUNTAIN)
    scenes = parse_script(f)
    assert len(scenes) == 3


def test_parse_markdown_script():
    md_text = """# INT. KITCHEN - DAY

ALICE cooks eggs at the stove.

## EXT. STREET - NIGHT

BOB runs through the dark alley.
"""
    scenes = parse_script_text(md_text, hint=".md")
    assert len(scenes) == 2
    assert scenes[0].location.upper() == "KITCHEN"
    assert scenes[0].interior is True
    assert scenes[1].location.upper() == "STREET"
    assert scenes[1].interior is False
    assert scenes[1].time_of_day.upper() == "NIGHT"
    assert scenes[0].slugline == "INT. KITCHEN - DAY"

