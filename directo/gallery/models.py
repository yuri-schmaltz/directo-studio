"""Data model for gallery images."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ColorTag = Literal["red", "orange", "yellow", "green", "blue", "purple", "pink", "gray"]


@dataclass
class ImageRecord:
    """Metadata for a single image in the gallery.

    The actual file lives on disk at ``path``. We keep everything else
    in SQLite for fast querying and to support the multi-view UI.
    """

    # identity
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    path: str = ""

    # provenance
    job_id: str | None = None
    project: str | None = None
    prompt: str = ""
    negative_prompt: str = ""
    model: str | None = None
    sampler: str | None = None
    scheduler: str | None = None
    cfg_scale: float | None = None
    steps: int | None = None
    seed: int | None = None
    width: int | None = None
    height: int | None = None
    node: str | None = None

    # curation
    rating: int = 0  # 0-5
    color_tag: ColorTag | None = None
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    favorite: bool = False

    # technical
    file_size: int | None = None
    file_mtime: float | None = None
    phash: str | None = None  # perceptual hash, hex

    # timestamps
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ImageRecord":
        d = dict(row)
        # DB column ``tags_json`` → Python field ``tags`` (list)
        if "tags_json" in d and "tags" not in d:
            raw = d.pop("tags_json") or "[]"
            try:
                d["tags"] = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                d["tags"] = []
        elif isinstance(d.get("tags"), str):
            try:
                d["tags"] = json.loads(d["tags"])
            except json.JSONDecodeError:
                d["tags"] = []
        if d.get("tags") is None:
            d["tags"] = []
        # ``favorite`` is stored as int 0/1, restore bool
        d["favorite"] = bool(d.get("favorite", 0))
        # Drop any unknown keys the DB might have (forward compat)
        valid_keys = {f for f in cls.__dataclass_fields__}
        d = {k: v for k, v in d.items() if k in valid_keys}
        return cls(**d)
