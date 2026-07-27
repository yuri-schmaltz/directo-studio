# Technical Analysis & Design: StyleBibleStore & Package Export Structure

**Author**: Explorer 2 (Milestone 1)  
**Target Modules**: `directo/style_bible/store.py`, `directo/style_bible/__init__.py`  
**Date**: 2026-07-26  

---

## 1. Executive Summary

This report establishes the technical design and detailed code specification for `StyleBibleStore` (`directo/style_bible/store.py`) and the package export structure for `directo/style_bible/__init__.py`. 

`StyleBibleStore` serves as the SQLite-backed persistence layer for Style Bibles in Directo Studio. It enables thread-safe creation, retrieval, updating, deletion, listing, and multi-format (JSON/YAML) import/export of `StyleBible` instances.

---

## 2. Analysis of Existing Codebase Persistence Patterns

Inspection of existing stores in Directo (`directo/gallery/store.py`, `directo/creative/history.py`, and `directo/platform/migrations.py`) reveals key architectural conventions:

1. **Connection Management & Thread Safety**:
   - Stores initialize `threading.RLock()` to serialize SQLite operations across threads.
   - Database connections use `sqlite3.connect(..., check_same_thread=False, isolation_level=None)`.
   - Connections set `row_factory = sqlite3.Row` to allow dictionary-like row access by column name.
   - Path parameters accept both `str` and `pathlib.Path`, with `:memory:` supported as default or for fast testing.

2. **Schema Definition & Initialization**:
   - `_init_db()` (or `_migrate()`) is called automatically upon instantiation inside `self._lock`.
   - Tables are defined using `CREATE TABLE IF NOT EXISTS`.
   - Primary keys use string UUIDs or explicit string IDs (`id TEXT PRIMARY KEY`).
   - Timestamps are stored as `REAL` numbers representing Unix epoch time (using `time.time()` or SQLite `unixepoch('now')`).

3. **Data Serialization**:
   - Complex nested domains (like tags, params, or complete entities) are stored as raw JSON strings (`data` or `*_json` columns).
   - Top-level attributes (ID, name, version, timestamps) are stored in explicit columns with indexes for high-speed listing and filtering without parsing JSON blobs.

---

## 3. SQLite Database Schema Specification

Table Name: `style_bibles`

### 3.1 DDL Schema Definition
```sql
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
```

### 3.2 Field Description
| Field Name | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | Unique identifier for the Style Bible (e.g., `"cyberpunk_2099"`). |
| `name` | TEXT | NOT NULL | Human-readable name of the Style Bible. |
| `version` | TEXT | NOT NULL DEFAULT '1.0.0' | Version string (e.g. `"1.0.0"` or `"2.1"`). |
| `data` | TEXT | NOT NULL | Complete serialized JSON representation of `StyleBible`. |
| `created_at` | REAL | NOT NULL | Creation timestamp (Unix epoch seconds). |
| `updated_at` | REAL | NOT NULL | Last modification timestamp (Unix epoch seconds). |

---

## 4. `StyleBibleStore` API Design & Core Operations

Class: `StyleBibleStore` in `directo/style_bible/store.py`.

### 4.1 Core Methods

#### `__init__(self, db_path: str | Path = ":memory:") -> None`
- Initializes `self._db_path = str(db_path)`.
- Instantiates `self._lock = threading.RLock()`.
- Connects to SQLite: `sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)`.
- Configures `self._conn.row_factory = sqlite3.Row`.
- Executes `self._init_db()` to construct tables and indexes idempotently.

#### `save_bible(self, bible: StyleBible) -> None`
- Validates input parameter `bible`.
- Obtains current epoch time: `now = time.time()`.
- Serializes `bible` to JSON string: `json_data = bible.to_json()`.
- Executes UPSERT SQL statement under lock:
  ```sql
  INSERT INTO style_bibles (id, name, version, data, created_at, updated_at)
  VALUES (?, ?, ?, ?, ?, ?)
  ON CONFLICT(id) DO UPDATE SET
      name = excluded.name,
      version = excluded.version,
      data = excluded.data,
      updated_at = excluded.updated_at;
  ```
  *(Note: If updating an existing record, `created_at` remains intact while `updated_at` is updated to `now`.)*

#### `load_bible(self, id: str) -> Optional[StyleBible]`
- Executes under lock: `SELECT data FROM style_bibles WHERE id = ?`.
- If row exists: deserializes JSON string using `StyleBible.from_json(row["data"])` and returns the `StyleBible` object.
- If row does not exist: returns `None`.

#### `list_bibles(self) -> List[Dict[str, Any]]`
- Executes under lock: `SELECT id, name, version, data, created_at, updated_at FROM style_bibles ORDER BY updated_at DESC`.
- For each record, deserializes or inspects summary metadata to construct a dictionary:
  ```python
  {
      "id": row["id"],
      "name": row["name"],
      "version": row["version"],
      "character_count": len(bible.characters),
      "environment_count": len(bible.environments),
      "directive_count": len(bible.directives),
      "created_at": row["created_at"],
      "updated_at": row["updated_at"],
  }
  ```
- Returns list of metadata summaries.

#### `delete_bible(self, id: str) -> bool`
- Executes under lock: `DELETE FROM style_bibles WHERE id = ?`.
- Returns `True` if `cursor.rowcount > 0`, otherwise `False`.

---

## 5. Import / Export Operations Design

#### `export_bible(self, id: str, format: str = "json") -> str`
- Calls `load_bible(id)`.
- If `bible is None`, raises `KeyError(f"StyleBible with id '{id}' not found")`.
- Normalizes format: `fmt = format.lower().strip()`.
- If `fmt` in `("json", ".json")`: returns `bible.to_json()`.
- If `fmt` in `("yaml", "yml", ".yaml", ".yml")`: returns `bible.to_yaml()`.
- Otherwise, raises `ValueError(f"Unsupported format '{format}'. Supported formats: 'json', 'yaml'.")`.

#### `import_bible(self, content: str, format: str = "json") -> StyleBible`
- Normalizes format: `fmt = format.lower().strip()`.
- If `fmt` in `("json", ".json")`: deserializes via `StyleBible.from_json(content)`.
- If `fmt` in `("yaml", "yml", ".yaml", ".yml")`: deserializes via `StyleBible.from_yaml(content)`.
- Otherwise, raises `ValueError(f"Unsupported format '{format}'. Supported formats: 'json', 'yaml'.")`.
- Persists imported model via `self.save_bible(bible)`.
- Returns the `StyleBible` instance.

---

## 6. Detailed Implementation Specifications

### 6.1 `directo/style_bible/store.py` Specification

```python
"""SQLite persistence and import/export engine for Style Bibles."""

from __future__ import annotations

import json
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
        self._conn = sqlite3.connect(
            self._db_path, check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._init_db()

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
            if self._conn:
                self._conn.close()

    def __enter__(self) -> StyleBibleStore:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def save_bible(self, bible: StyleBible) -> None:
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
        log.bind(bible_id=bible.id).info("Saved Style Bible")

    def load_bible(self, id: str) -> Optional[StyleBible]:
        """Load a Style Bible by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM style_bibles WHERE id = ?", (id,)
            ).fetchone()

        if row is None:
            return None

        return StyleBible.from_json(row["data"])

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

    def delete_bible(self, id: str) -> bool:
        """Delete a Style Bible by ID. Returns True if found and deleted."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM style_bibles WHERE id = ?", (id,)
            )
            return cur.rowcount > 0

    def export_bible(self, id: str, format: str = "json") -> str:
        """Export a Style Bible by ID into raw JSON or YAML string."""
        bible = self.load_bible(id)
        if bible is None:
            raise KeyError(f"StyleBible with id '{id}' not found")

        fmt = format.lower().strip()
        if fmt in ("json", ".json"):
            return bible.to_json()
        elif fmt in ("yaml", "yml", ".yaml", ".yml"):
            return bible.to_yaml()
        else:
            raise ValueError(f"Unsupported format '{format}'. Supported formats: 'json', 'yaml'.")

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
```

---

### 6.2 `directo/style_bible/__init__.py` Specification

```python
"""Style Bible Engine & Prompt Builder subsystem for Directo Studio.

Provides data models, SQLite storage/persistence, prompt construction logic,
and format export/import (JSON/YAML) for creative direction consistency.
"""

from directo.style_bible.models import (
    CharacterProfile,
    EnvironmentAnchor,
    LoRAConfig,
    StyleBible,
    StyleDirective,
)
from directo.style_bible.prompt_builder import PromptBuilder, PromptResult
from directo.style_bible.store import StyleBibleStore

__all__ = [
    "CharacterProfile",
    "EnvironmentAnchor",
    "LoRAConfig",
    "StyleBible",
    "StyleDirective",
    "StyleBibleStore",
    "PromptBuilder",
    "PromptResult",
]
```

---

## 7. Edge Cases & Safety Considerations

1. **Thread Concurrency**: Using `threading.RLock()` across all public DB access methods ensures thread safety when multiple API requests or background tasks interact with `StyleBibleStore`.
2. **Missing Bible Errors**: `load_bible` returns `None` for missing IDs, whereas `export_bible` raises `KeyError` for non-existent IDs.
3. **Invalid JSON/YAML**: `import_bible` relies on `StyleBible.from_json` / `StyleBible.from_yaml` which validate model attributes (e.g. via pydantic or dataclass validation). Parsing errors will be raised cleanly as `ValueError` or `json.JSONDecodeError`.
4. **Upsert Semantics**: Using `ON CONFLICT(id) DO UPDATE` ensures existing records are seamlessly updated without throwing duplicate key exceptions.
5. **Memory DB vs File DB**: Handled transparently by passing `:memory:` or string/Path file system locations.

---

## 8. Conclusion

This design meets all requirements in `PROJECT.md` and `SCOPE.md`, aligns with the existing storage architecture across Directo, and provides a robust foundation for Implementer agents to code `directo/style_bible/store.py` and `directo/style_bible/__init__.py`.
