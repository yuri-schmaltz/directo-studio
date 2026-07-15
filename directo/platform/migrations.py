"""Schema migrations for Directo SQLite databases.

Each Directo module that owns a SQLite database (queue, gallery, vault,
…) creates its tables on init via ``CREATE TABLE IF NOT EXISTS``. But
``IF NOT EXISTS`` doesn't migrate — it only creates. As Directo evolves,
columns get added, indexes change, data shape evolves.

The :class:`MigrationManager` provides a lightweight forward-only
migration system:

- A migration is a versioned (id, name, up_sql) tuple.
- Migrations are applied in order; each is recorded in a ``migrations``
  table inside the target DB.
- Idempotent: re-running the same migration is a no-op.
- Forward-only: no rollback (use backup instead).
- Modular: each module registers its own migrations.

The list of migrations for a module is a list of :class:`Migration`
in code. New versions are appended; never edit a published migration.

Usage in a module::

    from directo.platform.migrations import Migration, register_migrations

    MIGRATIONS = [
        Migration(2, "add_dedup_hits_to_gallery", "ALTER TABLE images ADD COLUMN dedup_hits INTEGER DEFAULT 0"),
        Migration(3, "add_index_phash", "CREATE INDEX IF NOT EXISTS idx_phash ON images(phash)"),
    ]
    register_migrations("gallery", MIGRATIONS)

Then anywhere in the app::

    from directo.platform.migrations import MigrationManager
    mgr = MigrationManager("gallery", db_path)
    mgr.run_pending()
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from directo.observability import get_logger

log = get_logger("directo.platform.migrations")


# Registry: module name -> list of Migration
_REGISTRY: dict[str, list["Migration"]] = {}


@dataclass
class Migration:
    """A single forward-only schema change.

    :param version: monotonically increasing integer (1, 2, 3, ...)
    :param name: human-readable label
    :param up_sql: SQL to apply (may be multiple statements separated by ``;``)
    """

    version: int
    name: str
    up_sql: str

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("migration version must be >= 1")


def register_migrations(module: str, migrations: Iterable[Migration]) -> None:
    """Register migrations for a module. Idempotent; replaces previous registration."""
    _REGISTRY[module] = list(migrations)


def list_registered_migrations(module: str) -> list[Migration]:
    return list(_REGISTRY.get(module, []))


class MigrationError(RuntimeError):
    """Raised when a migration fails to apply."""


class MigrationManager:
    """Applies pending migrations to a single database."""

    def __init__(self, module: str, db_path: str | Path) -> None:
        self.module = module
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        # Open with autocommit for explicit transaction control
        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,
            timeout=30.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS directo_migrations (
                    module       TEXT NOT NULL,
                    version      INTEGER NOT NULL,
                    name         TEXT NOT NULL,
                    applied_at   REAL NOT NULL DEFAULT (unixepoch('now')),
                    duration_ms  REAL,
                    PRIMARY KEY (module, version)
                )
                """
            )

    def applied_versions(self) -> list[int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT version FROM directo_migrations WHERE module = ? ORDER BY version",
                (self.module,),
            ).fetchall()
        return [r["version"] for r in rows]

    def pending(self) -> list[Migration]:
        registered = _REGISTRY.get(self.module, [])
        applied = set(self.applied_versions())
        return [m for m in registered if m.version not in applied]

    def current_version(self) -> int:
        applied = self.applied_versions()
        return max(applied) if applied else 0

    def run_pending(self) -> list[Migration]:
        """Apply all pending migrations. Returns the list of applied migrations."""
        pending = self.pending()
        if not pending:
            log.bind(module=self.module).info("no pending migrations")
            return []
        log.bind(module=self.module).info(f"applying {len(pending)} pending migrations")
        applied: list[Migration] = []
        for m in pending:
            self._apply_one(m)
            applied.append(m)
        return applied

    def _apply_one(self, m: Migration) -> None:
        # Sanity check: cannot apply v(N) if higher versions already exist
        existing = self.applied_versions()
        if existing and m.version <= max(existing):
            raise MigrationError(
                f"cannot apply {m.version} (already applied or out of order); existing={existing}"
            )
        # Also: cannot apply v(N) without v(N-1) already applied
        if m.version > 1 and (m.version - 1) not in existing:
            raise MigrationError(
                f"cannot apply {m.version}: version {m.version - 1} not yet applied; existing={existing}"
            )
        log.bind(module=self.module, version=m.version, name=m.name).info("applying migration")
        start = time.perf_counter()
        with self._lock:
            try:
                # executescript handles its own transaction
                self._conn.executescript(m.up_sql)
                self._conn.execute(
                    "INSERT INTO directo_migrations (module, version, name, duration_ms) "
                    "VALUES (?, ?, ?, ?)",
                    (self.module, m.version, m.name, (time.perf_counter() - start) * 1000),
                )
                self._conn.commit()
            except Exception as exc:
                try:
                    self._conn.rollback()
                except sqlite3.OperationalError:
                    pass
                log.bind(module=self.module, version=m.version).error(
                    f"migration FAILED: {exc}"
                )
                raise MigrationError(f"migration {m.version} ({m.name}) failed: {exc}") from exc

    def history(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM directo_migrations WHERE module = ? ORDER BY version",
                (self.module,),
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
