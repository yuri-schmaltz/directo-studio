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
from directo.director.animatic import (
    AIVideoBackend,
    AnimaticBuilder,
    AnimaticClip,
    AnimaticProject,
    from_gallery,
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

__all__ = [
    "AIVideoBackend",
    # animatic
    "AnimaticBuilder",
    "AnimaticClip",
    "AnimaticProject",
    # agent
    "Character",
    "CreativeDirector",
    "Decision",
    "LLMBackend",
    # slerp
    "LatentSpaceExplorer",
    # moodboard
    "MoodAnchor",
    "Moodboard",
    "MoodboardBuilder",
    "ProjectMemory",
    "SlerpGrid",
    "StyleGuide",
    # backends
    "TemplateBackend",
    "from_gallery",
    "make_backend",
]
