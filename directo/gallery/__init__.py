"""Image gallery with ratings, tags, metadata search, and perceptual dedup.

The :class:`Gallery` stores metadata about generated/saved images in
SQLite. Image pixels are kept on disk (you point to the path); we
store the *metadata* (prompt, model, seed, ratings, tags, color
labels, notes, perceptual hash).

Key features:
- 1-5 star rating
- Free-form tags + predefined color tags
- Full-text metadata search (prompt, model, seed, notes)
- Perceptual hash dedup via ``imagehash`` (pHash / dHash / aHash)
- Multi-view ready: grid, list, masonry, timeline data
- Batch rename utilities
- PNG metadata read/write (Prompt, Model, Seed, etc. as PNG tEXt)
"""

from directo.gallery.models import ImageRecord
from directo.gallery.store import Gallery

__all__ = ["Gallery", "ImageRecord"]
