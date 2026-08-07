"""Storyboard Canvas state model.

A "canvas" is an infinite workspace where the user lays out
**panels** (frames of a storyboard) and arranges them spatially.
Each panel is a stateful object with:

- Position (x, y) and size (width, height) on the canvas.
- A reference to its current image (Gallery image_id).
- A per-panel workflow (the queue Job that generated it).
- A per-panel image history (uses :class:`ImageHistory`).
- Markdown notes for the director.

The canvas is the **state**; the rendering is the frontend's job.
This module gives you the data model + persistence so that any UI
(Miro-like, Figma-like, simple grid) can be built on top.

A canvas is a JSON document; round-trip through SQLite for
multi-user persistence.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Self

from directo.observability import get_logger

log = get_logger("directo.cinema.canvas")


@dataclass
class Panel:
    """A single panel on the storyboard canvas."""

    id: str
    shot_label: str = ""               # "SHOT 12A", etc.
    title: str = ""
    notes: str = ""
    x: float = 0.0                     # canvas coordinates
    y: float = 0.0
    width: float = 320.0
    height: float = 180.0
    z_index: int = 0
    image_id: str | None = None        # current Gallery image
    job_id: str | None = None          # generation job
    workflow: dict[str, Any] = field(default_factory=dict)
    locked: bool = False
    visible: bool = True
    color: str = "#7c5cff"             # panel border color
    history_image_ids: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Panel:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class StoryboardCanvas:
    """The full canvas state."""

    id: str
    project: str
    title: str = ""
    description: str = ""
    width: float = 4000.0              # virtual canvas size
    height: float = 3000.0
    background: str = "#0a0a0f"
    panels: dict[str, Panel] = field(default_factory=dict)
    camera: dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0, "zoom": 1.0})
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "panels": {pid: p.to_dict() for pid, p in self.panels.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoryboardCanvas:
        panels_data = data.pop("panels", {})
        if isinstance(panels_data, list):
            panels_data = {p["id"]: p for p in panels_data if isinstance(p, dict) and "id" in p}
        canvas = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        canvas.panels = {pid: Panel.from_dict(p) for pid, p in panels_data.items()}
        return canvas

    # ----------------- Panel operations -----------------

    def add_panel(self, **fields: Any) -> Panel:
        pid = fields.pop("id", uuid.uuid4().hex[:12])
        panel = Panel(id=pid, **fields)
        self.panels[pid] = panel
        self.updated_at = time.time()
        log.bind(canvas=self.id, panel=pid).info(
            f"panel added at ({panel.x:.0f},{panel.y:.0f})"
        )
        return panel

    def remove_panel(self, panel_id: str) -> bool:
        if panel_id in self.panels:
            del self.panels[panel_id]
            self.updated_at = time.time()
            return True
        return False

    def move_panel(self, panel_id: str, x: float, y: float) -> None:
        if p := self.panels.get(panel_id):
            p.x, p.y = x, y
            p.updated_at = time.time()
            self.updated_at = time.time()

    def resize_panel(self, panel_id: str, width: float, height: float) -> None:
        if p := self.panels.get(panel_id):
            p.width, p.height = max(20, width), max(20, height)
            p.updated_at = time.time()
            self.updated_at = time.time()

    def set_panel_image(self, panel_id: str, image_id: str) -> None:
        if p := self.panels.get(panel_id):
            if p.image_id and p.image_id != image_id:
                p.history_image_ids.append(p.image_id)
            p.image_id = image_id
            p.updated_at = time.time()
            self.updated_at = time.time()

    def panels_in_rect(
        self, x: float, y: float, w: float, h: float
    ) -> list[Panel]:
        """Return panels whose bounding box intersects the given viewport rect."""
        out: list[Panel] = []
        for p in self.panels.values():
            if p.x + p.width < x or p.x > x + w:
                continue
            if p.y + p.height < y or p.y > y + h:
                continue
            out.append(p)
        return out

    def to_grid(self, cols: int = 4) -> list[Panel]:
        """Return panels laid out in a regular grid (for static export)."""
        if not self.panels:
            return []
        sorted_panels = sorted(self.panels.values(), key=lambda p: (p.y, p.x))
        cell_w = 320.0
        cell_h = 180.0
        for i, p in enumerate(sorted_panels):
            p.x = (i % cols) * cell_w
            p.y = (i // cols) * cell_h
        return sorted_panels


class CanvasStore:
    """SQLite-backed persistence for :class:`StoryboardCanvas`."""

    def __init__(self, db_path: str | Path = "directo_canvases.db") -> None:
        self._db_path = str(db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS canvases (
                    id              TEXT PRIMARY KEY,
                    project         TEXT NOT NULL,
                    title           TEXT NOT NULL DEFAULT '',
                    description     TEXT NOT NULL DEFAULT '',
                    width           REAL NOT NULL DEFAULT 4000,
                    height          REAL NOT NULL DEFAULT 3000,
                    background      TEXT NOT NULL DEFAULT '#0a0a0f',
                    panels_json     TEXT NOT NULL DEFAULT '{}',
                    camera_json     TEXT NOT NULL DEFAULT '{"x":0,"y":0,"zoom":1.0}',
                    metadata_json   TEXT NOT NULL DEFAULT '{}',
                    created_at      REAL NOT NULL DEFAULT (unixepoch('now')),
                    updated_at      REAL NOT NULL DEFAULT (unixepoch('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_canvases_project ON canvases (project);
                """
            )

    def save(self, canvas: StoryboardCanvas) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO canvases (
                    id, project, title, description, width, height, background,
                    panels_json, camera_json, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project = excluded.project,
                    title = excluded.title,
                    description = excluded.description,
                    width = excluded.width,
                    height = excluded.height,
                    background = excluded.background,
                    panels_json = excluded.panels_json,
                    camera_json = excluded.camera_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    canvas.id, canvas.project, canvas.title, canvas.description,
                    canvas.width, canvas.height, canvas.background,
                    json.dumps({pid: p.to_dict() for pid, p in canvas.panels.items()}),
                    json.dumps(canvas.camera), json.dumps(canvas.metadata),
                    canvas.created_at, canvas.updated_at,
                ),
            )

    def get(self, canvas_id: str) -> StoryboardCanvas | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM canvases WHERE id = ?", (canvas_id,)
            ).fetchone()
        return self._row_to_canvas(row) if row else None

    def list_for_project(self, project: str, limit: int = 50) -> list[StoryboardCanvas]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM canvases WHERE project = ? "
                "ORDER BY updated_at DESC LIMIT ?",
                (project, limit),
            ).fetchall()
        return [self._row_to_canvas(r) for r in rows]

    def delete(self, canvas_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM canvases WHERE id = ?", (canvas_id,))
            return cur.rowcount > 0

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) AS n FROM canvases").fetchone()["n"]

    def _row_to_canvas(self, row: sqlite3.Row) -> StoryboardCanvas:
        panels_raw = json.loads(row["panels_json"]) if row["panels_json"] else {}
        return StoryboardCanvas(
            id=row["id"], project=row["project"], title=row["title"],
            description=row["description"], width=row["width"], height=row["height"],
            background=row["background"],
            panels={pid: Panel.from_dict(p) for pid, p in panels_raw.items()},
            camera=json.loads(row["camera_json"]) if row["camera_json"] else {"x": 0, "y": 0, "zoom": 1.0},
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
