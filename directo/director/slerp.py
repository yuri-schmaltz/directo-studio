"""Latent space variation explorer.

Slerp (spherical linear interpolation) lets you blend two latents
along a great-circle arc on the unit sphere. This is the canonical
way to "explore between" two generated images in Stable Diffusion /
FLUX / ComfyUI.

The :class:`LatentSpaceExplorer` keeps a registry of saved latents
(by name or hash) and can produce a grid of N x M intermediate
latents between any two.

Latents are stored as Python lists of floats. The shape doesn't
matter to this module — the underlying generation code is responsible
for reshaping back to ``[C, H, W]`` tensors.

In Directo, a "latent" is what :class:`directo.gallery.Gallery` would
record alongside the image — and what the ComfyUI workflow saves
back when a job completes.
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from directo.observability import get_logger

log = get_logger("directo.director.slerp")


@dataclass
class SlerpGrid:
    """A 2D grid of slerped latents between corners ``a`` and ``b``."""

    id: str
    name: str
    a: list[float]                 # latent vector A
    b: list[float]                 # latent vector B
    grid: list[list[list[float]]]  # [row][col][dim]
    weights: list[list[float]]     # [row][col] — the t value at each cell
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def rows(self) -> int:
        return len(self.grid)

    @property
    def cols(self) -> int:
        return len(self.grid[0]) if self.grid else 0

    def flatten(self) -> list[list[float]]:
        """Return the grid as a flat list of (latent, weight) pairs in row-major order."""
        out: list[list[float]] = []
        for row in self.grid:
            out.extend(row)
        return out


class LatentSpaceExplorer:
    """Registry + slerp engine for saved latents.

    Latents are stored as JSON-encoded lists. The shape is opaque to
    this class — only the dimensionality matters.
    """

    def __init__(self, db_path: str | Path = "directo_latents.db") -> None:
        self._db_path = str(db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS latents (
                    id              TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    image_id        TEXT,
                    project         TEXT,
                    model           TEXT,
                    seed            INTEGER,
                    shape_json      TEXT,
                    dim             INTEGER NOT NULL,
                    vector_json     TEXT NOT NULL,
                    metadata_json   TEXT NOT NULL DEFAULT '{}',
                    created_at      REAL NOT NULL DEFAULT (unixepoch('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_latents_name ON latents (name);
                CREATE INDEX IF NOT EXISTS idx_latents_project ON latents (project);
                """
            )

    # ----------------- Store latents -----------------

    def save(
        self,
        vector: list[float],
        *,
        name: str = "",
        image_id: str | None = None,
        project: str | None = None,
        model: str | None = None,
        seed: int | None = None,
        shape: list[int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Save a latent vector for later slerping."""
        latent_id = f"lat-{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO latents (id, name, image_id, project, model, seed, shape_json, dim, vector_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    latent_id, name or latent_id, image_id, project, model, seed,
                    json.dumps(shape) if shape else None,
                    len(vector),
                    json.dumps(vector),
                    json.dumps(metadata or {}),
                ),
            )
        log.bind(latent=latent_id, name=name).info(f"latent saved (dim={len(vector)})")
        return latent_id

    def get(self, latent_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM latents WHERE id = ?", (latent_id,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def find_by_name(self, name: str, project: str | None = None) -> dict[str, Any] | None:
        sql = "SELECT * FROM latents WHERE name = ?"
        params: list[Any] = [name]
        if project:
            sql += " AND project = ?"
            params.append(project)
        with self._lock:
            row = self._conn.execute(
                sql + " ORDER BY created_at DESC LIMIT 1", params
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_for_project(self, project: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM latents WHERE project = ? ORDER BY created_at DESC LIMIT ?",
                (project, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["vector"] = json.loads(d.pop("vector_json"))
        d["shape"] = json.loads(d["shape_json"]) if d["shape_json"] else None
        d["metadata"] = json.loads(d["metadata_json"])
        return d

    # ----------------- Slerp -----------------

    def slerp(
        self, a: list[float], b: list[float], t: float
    ) -> list[float]:
        """Spherical linear interpolation between two latents at parameter t.

        ``t=0`` returns ``a``; ``t=1`` returns ``b``. The interpolation
        follows the great-circle arc on the unit sphere, which is what
        you want for normalized latent vectors.
        """
        if len(a) != len(b):
            raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
        # 1. Compute norms
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(x * x for x in b)) or 1.0
        # 2. Normalize
        an = [x / na for x in a]
        bn = [x / nb for x in b]
        # 3. Cosine of angle between them
        dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(an, bn))))
        omega = math.acos(dot)
        sin_omega = math.sin(omega)
        if sin_omega < 1e-6:
            # Vectors are nearly collinear; fall back to lerp
            return [a[i] * (1 - t) + b[i] * t for i in range(len(a))]
        # 4. Slerp formula
        wa = math.sin((1 - t) * omega) / sin_omega
        wb = math.sin(t * omega) / sin_omega
        out: list[float] = []
        for i in range(len(a)):
            v = wa * an[i] + wb * bn[i]
            # Re-scale to mid-magnitude (geometric mean)
            target_norm = math.sqrt(na * nb)
            out.append(v * target_norm)
        return out

    def grid(
        self,
        a: list[float],
        b: list[float],
        *,
        rows: int = 4,
        cols: int = 4,
    ) -> SlerpGrid:
        """Build a ``rows x cols`` grid interpolating between a and b.

        Cell ``(i, j)`` is at parameter ``t = (i * cols + j) / (rows*cols - 1)``
        along the slerp path from a to b.

        For non-linear blending, consider running :meth:`slerp` with
        custom t values instead of using this helper.
        """
        if rows < 1 or cols < 1:
            raise ValueError("rows and cols must be >= 1")
        total = rows * cols
        grid: list[list[list[float]]] = []
        weights: list[list[float]] = []
        for i in range(rows):
            row_vecs: list[list[float]] = []
            row_weights: list[float] = []
            for j in range(cols):
                t = (i * cols + j) / max(1, total - 1)
                row_vecs.append(self.slerp(a, b, t))
                row_weights.append(t)
            grid.append(row_vecs)
            weights.append(row_weights)
        return SlerpGrid(
            id=f"grid-{uuid.uuid4().hex[:8]}",
            name=f"slerp_{rows}x{cols}",
            a=a, b=b, grid=grid, weights=weights,
        )

    def lerp(
        self, a: list[float], b: list[float], t: float
    ) -> list[float]:
        """Plain linear interpolation (for comparison / when not on the sphere)."""
        if len(a) != len(b):
            raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
        return [a[i] * (1 - t) + b[i] * t for i in range(len(a))]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "LatentSpaceExplorer":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
