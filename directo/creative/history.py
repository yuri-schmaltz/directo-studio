"""Per-job image history with restore.

When a generation job runs more than once (different seeds, parameter
tweaks, "let me try that again with one more step"), every iteration's
output is automatically archived here. You can:

- Browse the last N attempts for a given job.
- Compare two attempts side-by-side.
- "Restore" an older attempt by re-importing its image into the
  Gallery as the "current" one (without re-running the model).
- See aggregate stats per job: success rate, average duration, most
  recent rating.

This module is intentionally a thin layer on top of the Gallery. It
records ``(job_id, image_id, iteration, params, parent_image_id)``
so you can always reconstruct a timeline.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from directo.gallery import Gallery, ImageRecord
from directo.observability import get_logger

log = get_logger("directo.history")


@dataclass
class HistoryEntry:
    """A single image in a job's history."""

    id: str
    job_id: str
    image_id: str
    iteration: int
    parent_image_id: str | None = None
    note: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    is_current: bool = True
    created_at: float = field(default_factory=time.time)


class ImageHistory:
    """Per-job image history, backed by SQLite."""

    def __init__(self, db_path: str | Path = "directo_history.db") -> None:
        self._db_path = str(db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id                TEXT PRIMARY KEY,
                    job_id            TEXT NOT NULL,
                    image_id          TEXT NOT NULL,
                    iteration         INTEGER NOT NULL,
                    parent_image_id   TEXT,
                    note              TEXT NOT NULL DEFAULT '',
                    params_json       TEXT NOT NULL DEFAULT '{}',
                    is_current        INTEGER NOT NULL DEFAULT 1,
                    created_at        REAL NOT NULL DEFAULT (unixepoch('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_history_job
                    ON history (job_id, iteration DESC);
                CREATE INDEX IF NOT EXISTS idx_history_current
                    ON history (job_id, is_current);
                """
            )

    # ----------------- Record -----------------

    def record(
        self,
        job_id: str,
        image_id: str,
        *,
        iteration: int | None = None,
        parent_image_id: str | None = None,
        note: str = "",
        params: dict[str, Any] | None = None,
    ) -> str:
        """Record an image as part of a job's history.

        - If ``iteration`` is not given, it's auto-incremented from the
          previous max iteration for that job.
        - The new entry is marked ``is_current=1`` and the previous
          current entry (if any) is marked ``is_current=0``.
        """
        with self._lock:
            if iteration is None:
                row = self._conn.execute(
                    "SELECT COALESCE(MAX(iteration), 0) AS n FROM history WHERE job_id = ?",
                    (job_id,),
                ).fetchone()
                iteration = (row["n"] if row else 0) + 1

            # Demote previous current
            self._conn.execute(
                "UPDATE history SET is_current = 0 WHERE job_id = ? AND is_current = 1",
                (job_id,),
            )

            entry_id = uuid.uuid4().hex
            self._conn.execute(
                """
                INSERT INTO history
                    (id, job_id, image_id, iteration, parent_image_id, note,
                     params_json, is_current)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    entry_id, job_id, image_id, iteration,
                    parent_image_id, note,
                    json.dumps(params or {}),
                ),
            )
        log.bind(job_id=job_id, iteration=iteration).info(
            f"history entry recorded", image_id=image_id[:8]
        )
        return entry_id

    # ----------------- Lookup -----------------

    def get_job_history(self, job_id: str) -> list[HistoryEntry]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM history WHERE job_id = ? ORDER BY iteration ASC",
                (job_id,),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_current(self, job_id: str) -> HistoryEntry | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM history WHERE job_id = ? AND is_current = 1",
                (job_id,),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def get_iteration(self, job_id: str, iteration: int) -> HistoryEntry | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM history WHERE job_id = ? AND iteration = ?",
                (job_id, iteration),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    # ----------------- Restore / switch -----------------

    def set_current(self, job_id: str, iteration: int, *, by: str = "user") -> HistoryEntry | None:
        """Mark a specific iteration as the current one.

        Other iterations are demoted. This does NOT copy the image —
        it just flips the "current" flag so the UI knows to surface
        this version. Use :meth:`restore` if you also want to
        re-add the image to the Gallery as a new top-level record.
        """
        with self._lock:
            target = self._conn.execute(
                "SELECT id FROM history WHERE job_id = ? AND iteration = ?",
                (job_id, iteration),
            ).fetchone()
            if target is None:
                return None
            self._conn.execute(
                "UPDATE history SET is_current = 0 WHERE job_id = ?",
                (job_id,),
            )
            self._conn.execute(
                "UPDATE history SET is_current = 1 WHERE id = ?",
                (target["id"],),
            )
        log.bind(job_id=job_id, iteration=iteration, by=by).info("history current iteration set")
        return self.get_iteration(job_id, iteration)

    def restore(
        self,
        job_id: str,
        iteration: int,
        gallery: Gallery,
        *,
        by: str = "user",
    ) -> str:
        """Restore an older iteration by re-adding its image to the Gallery.

        Returns the new Gallery image id. The image file on disk is
        **copied** to a new path (``<stem>_restored<N><ext>``) so the
        restored record can coexist with the original (which is
        protected by the Gallery's UNIQUE constraint on path). The
        rating/tags of the new record are preserved from the original.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM history WHERE job_id = ? AND iteration = ?",
                (job_id, iteration),
            ).fetchone()
        if row is None:
            raise ValueError(f"no history for job {job_id} iteration {iteration}")
        entry = self._row_to_entry(row)

        original = gallery.get(entry.image_id)
        if original is None:
            raise ValueError(f"original image {entry.image_id} not found in gallery")

        # Copy the file to a new path so the Gallery UNIQUE constraint
        # is honored.
        from shutil import copy2
        src = Path(original.path)
        new_path = src.with_name(f"{src.stem}_restored{iteration}{src.suffix}")
        if new_path == src:
            new_path = src.with_name(f"{src.stem}_restored{iteration}_x{src.suffix}")
        copy2(src, new_path)

        restored = ImageRecord(
            path=str(new_path),
            job_id=original.job_id,
            project=original.project,
            prompt=original.prompt,
            negative_prompt=original.negative_prompt,
            model=original.model,
            sampler=original.sampler,
            scheduler=original.scheduler,
            cfg_scale=original.cfg_scale,
            steps=original.steps,
            seed=original.seed,
            width=original.width,
            height=original.height,
            node=original.node,
            rating=original.rating,
            color_tag=original.color_tag,
            tags=list(original.tags) + ["restored"],
            notes=(original.notes + f"\nrestored from iteration {iteration}").strip(),
            favorite=original.favorite,
            phash=original.phash,
        )
        new_id = gallery.add(restored)
        log.bind(job_id=job_id, iteration=iteration, by=by).info(
            f"image restored", new_id=new_id[:8]
        )
        return new_id

    # ----------------- Compare -----------------

    def diff(
        self, job_id: str, iter_a: int, iter_b: int
    ) -> dict[str, Any]:
        """Return a dict comparing two iterations of the same job."""
        a = self.get_iteration(job_id, iter_a)
        b = self.get_iteration(job_id, iter_b)
        if a is None or b is None:
            raise ValueError(f"missing iteration: a={iter_a}, b={iter_b}")
        # Compute diff of params
        all_keys = set(a.params) | set(b.params)
        param_diff = {}
        for k in all_keys:
            va = a.params.get(k)
            vb = b.params.get(k)
            if va != vb:
                param_diff[k] = {"a": va, "b": vb}
        return {
            "job_id": job_id,
            "a": {"iteration": a.iteration, "image_id": a.image_id, "params": a.params},
            "b": {"iteration": b.iteration, "image_id": b.image_id, "params": b.params},
            "param_diff": param_diff,
        }

    # ----------------- Stats -----------------

    def stats(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) AS n FROM history WHERE job_id = ?", (job_id,)
            ).fetchone()["n"]
            current = self._conn.execute(
                "SELECT image_id FROM history WHERE job_id = ? AND is_current = 1",
                (job_id,),
            ).fetchone()
        return {
            "job_id": job_id,
            "iterations": total,
            "current_image_id": current["image_id"] if current else None,
        }

    def _row_to_entry(self, row: sqlite3.Row) -> HistoryEntry:
        return HistoryEntry(
            id=row["id"],
            job_id=row["job_id"],
            image_id=row["image_id"],
            iteration=row["iteration"],
            parent_image_id=row["parent_image_id"],
            note=row["note"],
            params=json.loads(row["params_json"]) if row["params_json"] else {},
            is_current=bool(row["is_current"]),
            created_at=row["created_at"],
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "ImageHistory":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
