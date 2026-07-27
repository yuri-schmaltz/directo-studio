"""SQLite persistence and import/export engine for Style Bibles."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from directo.observability import get_logger
from directo.style_bible.models import StyleBible

log = get_logger("directo.style_bible.store")


class StyleBibleStore:
    """SQLite-backed store for managing, persisting, and exporting Style Bibles."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._lock = threading.RLock()

        if self._db_path != ":memory:":
            parent_dir = os.path.dirname(self._db_path)
            if parent_dir and not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                except Exception as e:
                    raise sqlite3.OperationalError(
                        f"Cannot create database directory '{parent_dir}': {e}"
                    ) from e

        try:
            self._conn = sqlite3.connect(
                self._db_path, check_same_thread=False, isolation_level=None
            )
            self._conn.row_factory = sqlite3.Row
            self._init_db()
        except sqlite3.OperationalError as e:
            raise sqlite3.OperationalError(
                f"Failed to open SQLite database at '{self._db_path}': {e}"
            ) from e

    def _init_db(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS style_bibles (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    version     TEXT NOT NULL DEFAULT '1.0.0',
                    data        TEXT NOT NULL,
                    created_at  REAL NOT NULL DEFAULT (unixepoch('now')),
                    updated_at  REAL NOT NULL DEFAULT (unixepoch('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_style_bibles_name 
                    ON style_bibles (name);

                CREATE INDEX IF NOT EXISTS idx_style_bibles_updated 
                    ON style_bibles (updated_at DESC);
                """
            )

    def close(self) -> None:
        """Close database connection."""
        with self._lock:
            if hasattr(self, "_conn") and self._conn:
                self._conn.close()

    def __enter__(self) -> StyleBibleStore:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def save_bible(self, bible: StyleBible) -> str:
        """Save or update a Style Bible in SQLite."""
        if not isinstance(bible, StyleBible):
            raise TypeError(f"Expected StyleBible instance, got {type(bible).__name__}")

        now = time.time()
        json_data = bible.to_json()

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO style_bibles (id, name, version, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    version = excluded.version,
                    data = excluded.data,
                    updated_at = excluded.updated_at
                """,
                (bible.id, bible.name, bible.version, json_data, now, now),
            )
        try:
            log.bind(bible_id=bible.id).info("Saved Style Bible")
        except Exception:
            pass
        return bible.id

    def save(self, style_bible: StyleBible) -> str:
        """Alias for save_bible to support existing store API."""
        return self.save_bible(style_bible)

    def load_bible(self, id: str) -> Optional[StyleBible]:
        """Load a Style Bible by ID. Returns None if not found."""
        if not isinstance(id, str) or not id.strip():
            raise ValueError("ID must be a non-empty string.")

        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM style_bibles WHERE id = ?", (id,)
            ).fetchone()

        if row is None:
            return None

        return StyleBible.from_json(row["data"])

    def load(self, bible_id: str) -> StyleBible:
        """Load a Style Bible by ID. Raises KeyError if not found."""
        bible = self.load_bible(bible_id)
        if bible is None:
            raise KeyError(f"StyleBible with ID '{bible_id}' not found.")
        return bible

    def list_bibles(self) -> List[Dict[str, Any]]:
        """List metadata summaries of all saved Style Bibles."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, name, version, data, created_at, updated_at 
                FROM style_bibles 
                ORDER BY updated_at DESC
                """
            ).fetchall()

        results = []
        for row in rows:
            try:
                bible = StyleBible.from_json(row["data"])
                char_count = len(bible.characters)
                env_count = len(bible.environments)
                dir_count = len(bible.directives)
            except Exception:
                char_count = env_count = dir_count = 0

            results.append({
                "id": row["id"],
                "name": row["name"],
                "version": row["version"],
                "character_count": char_count,
                "environment_count": env_count,
                "directive_count": dir_count,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            })
        return results

    def list(self) -> List[Dict[str, Any]]:
        """Alias for list_bibles."""
        return self.list_bibles()

    def delete_bible(self, id: str) -> bool:
        """Delete a Style Bible by ID. Returns True if found and deleted."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM style_bibles WHERE id = ?", (id,)
            )
            return cur.rowcount > 0

    def delete(self, bible_id: str) -> bool:
        """Alias for delete_bible."""
        return self.delete_bible(bible_id)

    def search(self, query: str) -> List[StyleBible]:
        """Search saved Style Bibles matching query string."""
        if not isinstance(query, str) or not query.strip():
            return []

        q_lower = query.strip().lower()
        with self._lock:
            rows = self._conn.execute("SELECT data FROM style_bibles").fetchall()

        results = []
        for row in rows:
            bible = StyleBible.from_json(row["data"])
            match = False
            if q_lower in bible.name.lower() or q_lower in bible.id.lower():
                match = True
            else:
                for c in bible.characters:
                    cname = getattr(c, "name", "")
                    cid = getattr(c, "id", "")
                    cprompt = getattr(c, "base_prompt", "")
                    if q_lower in cname.lower() or q_lower in cid.lower() or q_lower in cprompt.lower():
                        match = True
                        break
                if not match:
                    for e in bible.environments:
                        ename = getattr(e, "name", "")
                        eid = getattr(e, "id", "")
                        eprompt = getattr(e, "scenario_prompt", "")
                        if q_lower in ename.lower() or q_lower in eid.lower() or q_lower in eprompt.lower():
                            match = True
                            break
            if match:
                results.append(bible)
        return results

    def export_bible(self, id: str, format: str = "json") -> str:
        """Export a Style Bible by ID into raw JSON or YAML string."""
        bible = self.load(id)
        fmt = format.lower().strip()
        if fmt in ("json", ".json"):
            return bible.to_json()
        elif fmt in ("yaml", "yml", ".yaml", ".yml"):
            return bible.to_yaml()
        else:
            raise ValueError(f"Unsupported format '{format}'. Supported formats: 'json', 'yaml'.")

    def export_to_file(self, bible_id: str, file_path: str, format: str = "json") -> str:
        """Export a Style Bible to a file."""
        content = self.export_bible(bible_id, format=format)
        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

    def import_bible(self, content: str, format: str = "json") -> StyleBible:
        """Import a Style Bible from a JSON or YAML string and save it."""
        fmt = format.lower().strip()
        if fmt in ("json", ".json"):
            bible = StyleBible.from_json(content)
        elif fmt in ("yaml", "yml", ".yaml", ".yml"):
            bible = StyleBible.from_yaml(content)
        else:
            raise ValueError(f"Unsupported format '{format}'. Supported formats: 'json', 'yaml'.")

        self.save_bible(bible)
        return bible

    def import_from_file(self, file_path: str) -> StyleBible:
        """Import a Style Bible from a file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if file_path.endswith((".yaml", ".yml")):
            bible = StyleBible.from_yaml(content)
        else:
            try:
                bible = StyleBible.from_json(content)
            except Exception:
                bible = StyleBible.from_yaml(content)

        self.save_bible(bible)
        return bible
