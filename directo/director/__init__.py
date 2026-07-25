"""Director module (Phase 4): creative direction primitives.

Modules:
- :mod:`directo.director.agent`     — Creative Director LLM agent
- :mod:`directo.director.moodboard` — Moodboard auto-generator
- :mod:`directo.director.slerp`     — Latent space variation explorer
- :mod:`directo.director.animatic`  — Animatic generator
"""

from directo.director.agent import (
    Character,
    CreativeDirector,
    Decision,
    LLMBackend,
    ProjectMemory,
    StyleGuide,
)
from directo.director.backends import TemplateBackend, make_backend
from directo.director.moodboard import (
    MoodAnchor,
    Moodboard,
    MoodboardBuilder,
)
from directo.director.slerp import (
    LatentSpaceExplorer,
    SlerpGrid,
)
from directo.director.animatic import (
    AnimaticBuilder,
    AnimaticClip,
    AnimaticProject,
    AIVideoBackend,
    from_gallery,
)

__all__ = [
    # agent
    "Character", "CreativeDirector", "Decision", "LLMBackend",
    "ProjectMemory", "StyleGuide",
    # backends
    "TemplateBackend", "make_backend",
    # moodboard
    "MoodAnchor", "Moodboard", "MoodboardBuilder",
    # slerp
    "LatentSpaceExplorer", "SlerpGrid",
    # animatic
    "AnimaticBuilder", "AnimaticClip", "AnimaticProject", "AIVideoBackend", "from_gallery",
]
