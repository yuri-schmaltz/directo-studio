"""Cinema module (Phase 3): differentiators.

Modules:
- :mod:`directo.cinema.engine`  — Cinema prompt rules engine
- :mod:`directo.cinema.canvas`  — Storyboard canvas state model
- :mod:`directo.cinema.parser`  — Script parser (Fountain + plain text)
"""

from directo.cinema.canvas import (
    CanvasStore,
    Panel,
    StoryboardCanvas,
)
from directo.cinema.engine import (
    CinemaEngine,
    EngineReport,
    Rule,
    RuleKind,
    RuleResult,
)
from directo.cinema.parser import (
    DialogueLine,
    Scene,
    load_text_from_file,
    parse_fountain,
    parse_plain_text,
    parse_script,
    parse_script_text,
    scenes_to_prompts,
)

__all__ = [
    # canvas
    "CanvasStore",
    # engine
    "CinemaEngine",
    # parser
    "DialogueLine",
    "EngineReport",
    "Panel",
    "Rule",
    "RuleKind",
    "RuleResult",
    "Scene",
    "StoryboardCanvas",
    "load_text_from_file",
    "parse_fountain",
    "parse_plain_text",
    "parse_script",
    "parse_script_text",
    "scenes_to_prompts",
]
