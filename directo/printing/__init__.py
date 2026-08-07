"""Storyboard PDF export.

Generates print-ready storyboard PDFs from a list of gallery images.
Layouts:
- 1-up (one panel per page) — director review, pitch decks
- 2-up (two panels per page) — standard storyboard
- 4-up (four panels per page) — compact review
- contact-sheet (grid of thumbnails) — overview

Each panel shows: the image, the prompt (truncated), model, seed,
rating, and an optional shot label.
"""

from directo.printing.storyboard import (
    StoryboardConfig,
    StoryboardExporter,
    StoryboardLayout,
    StoryboardPanel,
)

__all__ = [
    "StoryboardConfig",
    "StoryboardExporter",
    "StoryboardLayout",
    "StoryboardPanel",
]
