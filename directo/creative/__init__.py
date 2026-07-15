"""Creative primitives — Phase 1 of the Directo roadmap.

The modules here turn the Phase 0 infrastructure into a productive
creative tool. They are designed to work **on top of** the existing
queue + gallery + vault, not replace them.

Modules
-------
- :mod:`directo.creative.variants` — the "4-options pattern". Generate
  N variants of a decision, present them in a grid, lock the best one.
  Documented as a critical pattern in production: ``4 options per
  asset, lock one before moving on``.

- :mod:`directo.creative.references` — a personal style/character/
  composition reference library. Drop a PNG, get a CLIP embedding,
  use it as input to IP-Adapter, ControlNet, or any other pipeline.
  Find similar references by cosine similarity.

- :mod:`directo.creative.history` — per-job image history. Re-roll a
  job and never lose the previous outputs. Browse, restore, and
  compare past attempts.

- :mod:`directo.creative.views` — multi-view gallery renderer. The
  Gallery already has all the metadata; this module turns it into
  a self-contained HTML page in any of: grid, masonry, list,
  timeline.
"""

from directo.creative.variants import (
    VariantSet,
    Variant,
    VariantLock,
    GenerationStrategy,
    VariantStore,
    plan_seeds,
)
from directo.creative.references import ReferenceLibrary, Reference, ReferenceKind
from directo.creative.history import ImageHistory
from directo.creative.views import GalleryView, ViewLayout

__all__ = [
    "VariantSet",
    "Variant",
    "VariantLock",
    "GenerationStrategy",
    "VariantStore",
    "plan_seeds",
    "ReferenceLibrary",
    "Reference",
    "ReferenceKind",
    "ImageHistory",
    "GalleryView",
    "ViewLayout",
]
