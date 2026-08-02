"""Gallery store: SQLite-backed metadata + perceptual hash dedup."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from directo.gallery.models import ColorTag, ImageRecord
from directo.observability import MetricsCollector, get_logger
from directo.platform.db import get_db_connection

log = get_logger("directo.gallery")

# Common color tag values — kept here so callers can validate.
_VALID_COLORS: set[str] = {"red", "orange", "yellow", "green", "blue", "purple", "pink", "gray"}


class Gallery:
    """SQLite-backed image metadata store with dedup.

    :param db_path: path to SQLite database
    :param image_root: root directory under which images live; used to
        relativize paths and to provide the "list by directory" feature.
    """

    def __init__(
        self,
        db_path: str | Path = "directo_gallery.db",
        *,
        image_root: str | Path | None = None,
        metrics: MetricsCollector | None = None,
    ) -> None:
        self._db_path = str(db_path)
        self._image_root = Path(image_root) if image_root else None
        self._metrics = metrics or MetricsCollector()
        self._lock = threading.RLock()

        self._conn = get_db_connection(self._db_path, check_same_thread=False, isolation_level=None)
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS images (
                    id              TEXT PRIMARY KEY,
                    path            TEXT NOT NULL UNIQUE,
                    job_id          TEXT,
                    project         TEXT,
                    prompt          TEXT,
                    negative_prompt TEXT,
                    model           TEXT,
                    sampler         TEXT,
                    scheduler       TEXT,
                    cfg_scale       REAL,
                    steps           INTEGER,
                    seed            INTEGER,
                    width           INTEGER,
                    height          INTEGER,
                    node            TEXT,
                    rating          INTEGER NOT NULL DEFAULT 0,
                    color_tag       TEXT,
                    tags_json       TEXT NOT NULL DEFAULT '[]',
                    notes           TEXT,
                    favorite        INTEGER NOT NULL DEFAULT 0,
                    file_size       INTEGER,
                    file_mtime      REAL,
                    phash           TEXT,
                    created_at      REAL NOT NULL DEFAULT (unixepoch('now')),
                    updated_at      REAL NOT NULL DEFAULT (unixepoch('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_images_rating ON images (rating DESC);
                CREATE INDEX IF NOT EXISTS idx_images_project ON images (project);
                CREATE INDEX IF NOT EXISTS idx_images_model ON images (model);
                CREATE INDEX IF NOT EXISTS idx_images_created ON images (created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_images_phash ON images (phash);
                CREATE INDEX IF NOT EXISTS idx_images_seed ON images (project, seed);

                -- Virtual FTS5 table for full-text search.
                CREATE VIRTUAL TABLE IF NOT EXISTS images_fts USING fts5(
                    prompt, negative_prompt, notes, tags, model,
                    content='images', content_rowid='rowid'
                );

                -- Triggers to keep FTS in sync.
                CREATE TRIGGER IF NOT EXISTS images_ai AFTER INSERT ON images BEGIN
                    INSERT INTO images_fts(rowid, prompt, negative_prompt, notes, tags, model)
                    VALUES (new.rowid, new.prompt, new.negative_prompt, new.notes, new.tags_json, new.model);
                END;
                CREATE TRIGGER IF NOT EXISTS images_ad AFTER DELETE ON images BEGIN
                    INSERT INTO images_fts(images_fts, rowid, prompt, negative_prompt, notes, tags, model)
                    VALUES('delete', old.rowid, old.prompt, old.negative_prompt, old.notes, old.tags_json, old.model);
                END;
                CREATE TRIGGER IF NOT EXISTS images_au AFTER UPDATE ON images BEGIN
                    INSERT INTO images_fts(images_fts, rowid, prompt, negative_prompt, notes, tags, model)
                    VALUES('delete', old.rowid, old.prompt, old.negative_prompt, old.notes, old.tags_json, old.model);
                    INSERT INTO images_fts(rowid, prompt, negative_prompt, notes, tags, model)
                    VALUES (new.rowid, new.prompt, new.negative_prompt, new.notes, new.tags_json, new.model);
                END;
                """
            )

    # ----------------- CRUD -----------------

    def add(self, record: ImageRecord) -> str:
        """Add a new image. Returns the record id."""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO images (
                    id, path, job_id, project, prompt, negative_prompt, model,
                    sampler, scheduler, cfg_scale, steps, seed, width, height, node,
                    rating, color_tag, tags_json, notes, favorite,
                    file_size, file_mtime, phash
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record.id, record.path, record.job_id, record.project,
                    record.prompt, record.negative_prompt, record.model,
                    record.sampler, record.scheduler, record.cfg_scale, record.steps,
                    record.seed, record.width, record.height, record.node,
                    record.rating, record.color_tag, json.dumps(record.tags),
                    record.notes, int(record.favorite),
                    record.file_size, record.file_mtime, record.phash,
                ),
            )
            self._refresh_metric()
        log.bind(image_id=record.id).info("image added", path=record.path)
        return record.id

    def update(self, image_id: str, **fields: Any) -> bool:
        """Update arbitrary fields. Returns True if the row existed."""
        if not fields:
            return False
        # Normalize list-typed fields
        if "tags" in fields and isinstance(fields["tags"], list):
            tags_value = fields.pop("tags")
            fields["tags_json"] = json.dumps(tags_value)
        if "favorite" in fields:
            fields["favorite"] = int(bool(fields["favorite"]))
        if "color_tag" in fields and fields["color_tag"] not in (None, *(_VALID_COLORS)):
            raise ValueError(f"invalid color_tag {fields['color_tag']!r}")
        fields["updated_at"] = time.time()

        cols = ", ".join(f"{k} = ?" for k in fields)
        params = list(fields.values()) + [image_id]
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE images SET {cols} WHERE id = ?", params
            )
            return cur.rowcount > 0

    def rate(self, image_id: str, rating: int) -> None:
        """Set 1-5 star rating (0 to clear)."""
        rating = max(0, min(5, rating))
        self.update(image_id, rating=rating)

    def favorite(self, image_id: str, value: bool = True) -> None:
        self.update(image_id, favorite=value)

    def set_color(self, image_id: str, color: ColorTag | None) -> None:
        if color is not None and color not in _VALID_COLORS:
            raise ValueError(f"invalid color {color!r}")
        self.update(image_id, color_tag=color)

    def add_tag(self, image_id: str, tag: str) -> None:
        rec = self.get(image_id)
        if rec is None:
            return
        if tag not in rec.tags:
            rec.tags.append(tag)
            self.update(image_id, tags=rec.tags)

    def remove_tag(self, image_id: str, tag: str) -> None:
        rec = self.get(image_id)
        if rec is None:
            return
        if tag in rec.tags:
            rec.tags.remove(tag)
            self.update(image_id, tags=rec.tags)

    def delete(self, image_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM images WHERE id = ?", (image_id,))
            self._refresh_metric()
            return cur.rowcount > 0

    # ----------------- Queries -----------------

    def get(self, image_id: str) -> ImageRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM images WHERE id = ?", (image_id,)
            ).fetchone()
        return ImageRecord.from_row(dict(row)) if row else None

    def get_by_path(self, path: str) -> ImageRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM images WHERE path = ?", (path,)
            ).fetchone()
        return ImageRecord.from_row(dict(row)) if row else None

    def search(
        self,
        *,
        text: str | None = None,
        project: str | None = None,
        model: str | None = None,
        min_rating: int = 0,
        favorites_only: bool = False,
        tags: Iterable[str] | None = None,
        color: ColorTag | None = None,
        order_by: str = "created_at",
        descending: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ImageRecord]:
        """Flexible search across all metadata.

        ``text`` uses FTS5 full-text on prompt/notes/model. All other
        filters are exact-match WHERE clauses.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if text:
            clauses.append("i.rowid IN (SELECT rowid FROM images_fts WHERE images_fts MATCH ?)")
            params.append(text)
        if project:
            clauses.append("i.project = ?")
            params.append(project)
        if model:
            clauses.append("i.model = ?")
            params.append(model)
        if min_rating > 0:
            clauses.append("i.rating >= ?")
            params.append(min_rating)
        if favorites_only:
            clauses.append("i.favorite = 1")
        if color:
            clauses.append("i.color_tag = ?")
            params.append(color)
        if tags:
            # Match ALL tags (intersection).
            for tag in tags:
                clauses.append("i.tags_json LIKE ?")
                params.append(f'%"{tag}"%')

        where = " AND ".join(clauses) if clauses else "1=1"
        order = order_by if order_by in {
            "created_at", "updated_at", "rating", "seed", "file_size"
        } else "created_at"
        direction = "DESC" if descending else "ASC"

        sql = f"""
            SELECT i.* FROM images i
            WHERE {where}
            ORDER BY i.{order} {direction}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [ImageRecord.from_row(dict(r)) for r in rows]

    def list_by_project(self, project: str, limit: int = 200) -> list[ImageRecord]:
        return self.search(project=project, limit=limit)

    def list_favorites(self, limit: int = 200) -> list[ImageRecord]:
        return self.search(favorites_only=True, limit=limit)

    def list_recent(self, limit: int = 100) -> list[ImageRecord]:
        return self.search(limit=limit)

    def list_top_rated(self, limit: int = 100) -> list[ImageRecord]:
        return self.search(min_rating=4, order_by="rating", limit=limit)

    # ----------------- Dedup -----------------

    def find_duplicates(
        self,
        phash: str,
        *,
        max_hamming: int = 5,
        project: str | None = None,
    ) -> list[ImageRecord]:
        """Find images whose perceptual hash is within ``max_hamming`` of ``phash``.

        Default hash is 64-bit (16 hex chars), so a Hamming distance of
        5 means the images are very similar (typically exact duplicates
        with small re-encodes).
        """
        if not phash:
            return []
        with self._lock:
            if project:
                rows = self._conn.execute(
                    "SELECT * FROM images WHERE project = ? AND phash IS NOT NULL",
                    (project,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM images WHERE phash IS NOT NULL"
                ).fetchall()
        results: list[ImageRecord] = []
        for r in rows:
            other = r["phash"]
            if other and _hamming(phash, other) <= max_hamming:
                results.append(ImageRecord.from_row(dict(r)))
        return results

    def is_duplicate(
        self, phash: str, *, max_hamming: int = 3, project: str | None = None
    ) -> ImageRecord | None:
        """Return the first matching duplicate, or None."""
        dups = self.find_duplicates(phash, max_hamming=max_hamming, project=project)
        if dups:
            self._metrics.gallery_dedup_hits.inc()
            return dups[0]
        return None

    # ----------------- Batch operations -----------------

    def batch_rename(
        self,
        pattern: str,
        *,
        project: str | None = None,
        start_index: int = 1,
        dry_run: bool = False,
    ) -> list[tuple[str, str]]:
        """Rename images by ``pattern`` (Python str.format with placeholders).

        Supported placeholders:
        - ``{index}`` — zero-padded running index
        - ``{model}`` — model name (sanitized)
        - ``{project}`` — project name
        - ``{seed}`` — seed
        - ``{rating}`` — rating
        - ``{date}`` — YYYYMMDD
        - ``{rating_star}`` — ★ for rating>0 else ☆

        Returns a list of (old_path, new_path) for review. If
        ``dry_run=False``, files are renamed on disk and DB updated.
        """
        results: list[tuple[str, str]] = []
        records = self.search(project=project, limit=10_000)
        for i, rec in enumerate(records, start=start_index):
            if not rec.path:
                continue
            old = Path(rec.path)
            if not old.exists():
                log.warning(f"skip rename: file missing {rec.path}")
                continue
            stem = pattern.format(
                index=str(i).zfill(4),
                model=_safe(rec.model or "model"),
                project=_safe(rec.project or "project"),
                seed=rec.seed if rec.seed is not None else "x",
                rating=rec.rating,
                date=time.strftime("%Y%m%d"),
                rating_star="star" if rec.rating >= 4 else "x",
            )
            new = old.with_name(stem + old.suffix)
            if new == old:
                continue
            results.append((str(old), str(new)))
            if not dry_run:
                old.rename(new)
                with self._lock:
                    self._conn.execute(
                        "UPDATE images SET path = ? WHERE id = ?",
                        (str(new), rec.id),
                    )
        return results

    # ----------------- Maintenance -----------------

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM images").fetchone()
        return row["n"]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) AS n FROM images").fetchone()["n"]
            rated = self._conn.execute(
                "SELECT COUNT(*) AS n FROM images WHERE rating > 0"
            ).fetchone()["n"]
            favs = self._conn.execute(
                "SELECT COUNT(*) AS n FROM images WHERE favorite = 1"
            ).fetchone()["n"]
            by_model = self._conn.execute(
                "SELECT model, COUNT(*) AS n FROM images WHERE model IS NOT NULL "
                "GROUP BY model ORDER BY n DESC LIMIT 10"
            ).fetchall()
        return {
            "total": total,
            "rated": rated,
            "favorites": favs,
            "top_models": [(r["model"], r["n"]) for r in by_model],
        }

    def _refresh_metric(self) -> None:
        try:
            self._metrics.gallery_images_total.set(self.count())
        except Exception:  # pragma: no cover
            pass

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "Gallery":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


# ----------------- helpers -----------------

def _hamming(a: str, b: str) -> int:
    """Hamming distance between two equal-length hex strings (bitwise)."""
    if len(a) != len(b):
        return max(len(a), len(b)) * 4  # far apart if mismatched length
    try:
        ba = bin(int(a, 16))[2:].zfill(len(a) * 4)
        bb = bin(int(b, 16))[2:].zfill(len(b) * 4)
    except ValueError:
        return max(len(a), len(b)) * 4
    return sum(x != y for x, y in zip(ba, bb))


def _safe(s: str) -> str:
    """Make a string safe to use as a filename."""
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in s)[:64]
