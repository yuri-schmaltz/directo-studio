"""4-options pattern: generate N variants per decision, lock the best one.

The pattern, documented in production pipelines (LTX, invideo, Boords):

  1. Every creative decision generates N variants (default 4).
  2. The user is shown a grid and must select one to proceed.
  3. The selected variant is "locked" — its prompt/seed is propagated
     to downstream generations as context, ensuring consistency.
  4. Locked variants are recorded so a later "what if I had chosen
     variant 3 instead?" can be replayed exactly.

This module is the **state tracker** — it doesn't generate images
itself. It coordinates with :class:`directo.queue.PersistentQueue`
and :class:`directo.gallery.Gallery` to:

- Track which variants have been generated for a decision.
- Store the relationship between a parent "decision" and its
  N children "variants".
- Record the lock event (which variant was chosen, by whom, when).
- Provide replay data (exact seeds, prompts, parameters) so the
  choice can be reproduced later.
"""

from __future__ import annotations

import enum
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Self

from directo.observability import get_logger

log = get_logger("directo.variants")


class GenerationStrategy(str, enum.Enum):
    """How to generate the N variants of a decision."""

    SEED_VARIATION = "seed_variation"  # same prompt, different seeds
    PROMPT_VARIATION = "prompt_variation"  # different phrasings, same seed
    MIXED = "mixed"  # different seeds AND slight prompt tweaks
    PARAMETER_SWEEP = "parameter_sweep"  # same prompt/seed, vary cfg/steps


@dataclass
class Variant:
    """A single variant within a :class:`VariantSet`."""

    index: int
    image_id: str | None = None  # FK into Gallery
    seed: int | None = None
    params: dict[str, Any] = field(default_factory=dict)
    prompt: str = ""
    note: str = ""


class VariantLock(str, enum.Enum):
    """Lock state of a :class:`VariantSet`."""

    OPEN = "open"          # no decision yet
    LOCKED = "locked"      # one variant was chosen; others can be discarded
    REJECTED = "rejected"  # the user rejected all variants; re-roll


@dataclass
class VariantSet:
    """A set of N variants for a single creative decision.

    Stored in SQLite (see :class:`VariantStore`) for persistence and
    replay. The dataclass form is the in-memory representation.
    """

    id: str
    decision_key: str                    # e.g. "scene_03_shot_a"
    prompt_template: str                 # the base prompt before variation
    project: str | None = None
    strategy: GenerationStrategy = GenerationStrategy.SEED_VARIATION
    variants: list[Variant] = field(default_factory=list)
    lock: VariantLock = VariantLock.OPEN
    locked_index: int | None = None
    locked_at: float | None = None
    locked_by: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["strategy"] = self.strategy.value
        d["lock"] = self.lock.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VariantSet:
        d = dict(data)
        d["strategy"] = GenerationStrategy(d.get("strategy", "seed_variation"))
        d["lock"] = VariantLock(d.get("lock", "open"))
        d["variants"] = [Variant(**v) for v in d.get("variants", [])]
        return cls(**d)

    # ----------------- Lock logic -----------------

    def is_complete(self) -> bool:
        """A set is "complete" when all N variants are filled in."""
        return len(self.variants) > 0 and all(v.image_id is not None for v in self.variants)

    def lock_variant(self, index: int, locked_by: str = "user") -> None:
        """Lock the variant at ``index`` as the chosen one.

        Idempotent: locking the same index twice is a no-op.
        Raises ``ValueError`` if the index is out of range or no
        variant exists at that index.
        """
        if not 0 <= index < len(self.variants):
            raise ValueError(f"variant index {index} out of range (have {len(self.variants)})")
        if self.variants[index].image_id is None:
            raise ValueError(f"variant {index} has no image yet")
        if self.lock == VariantLock.LOCKED:
            if self.locked_index == index:
                return  # idempotent
            raise RuntimeError(
                f"variant set already locked to {self.locked_index}; unlock first"
            )
        self.lock = VariantLock.LOCKED
        self.locked_index = index
        self.locked_at = time.time()
        self.locked_by = locked_by
        self.updated_at = time.time()
        log.bind(set_id=self.id).info(
            f"variant {index} locked as the chosen one", decision=self.decision_key
        )

    def unlock(self) -> None:
        """Reverse a previous lock, returning the set to OPEN state."""
        if self.lock != VariantLock.LOCKED:
            return
        log.bind(set_id=self.id).info(
            f"variant {self.locked_index} unlocked", decision=self.decision_key
        )
        self.lock = VariantLock.OPEN
        self.locked_index = None
        self.locked_at = None
        self.locked_by = None
        self.updated_at = time.time()

    def reject_all(self) -> None:
        """Mark the set as rejected — nothing was good enough."""
        self.lock = VariantLock.REJECTED
        self.updated_at = time.time()

    def locked_variant(self) -> Variant | None:
        if self.lock != VariantLock.LOCKED or self.locked_index is None:
            return None
        return self.variants[self.locked_index]


# ----------------- Persistence -----------------


class VariantStore:
    """SQLite-backed store for :class:`VariantSet`.

    Independent of the Gallery (it references the Gallery by ``image_id``)
    and the Queue (the actual generation jobs flow through there). This
    module is just the book-keeping for the "which variant was chosen"
    state machine.
    """

    def __init__(self, db_path: str | Path = "directo_variants.db") -> None:
        self._db_path = str(db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS variant_sets (
                    id              TEXT PRIMARY KEY,
                    decision_key    TEXT NOT NULL,
                    project         TEXT,
                    prompt_template TEXT NOT NULL,
                    strategy        TEXT NOT NULL DEFAULT 'seed_variation',
                    lock            TEXT NOT NULL DEFAULT 'open',
                    locked_index    INTEGER,
                    locked_at       REAL,
                    locked_by       TEXT,
                    variants_json   TEXT NOT NULL DEFAULT '[]',
                    metadata_json   TEXT NOT NULL DEFAULT '{}',
                    created_at      REAL NOT NULL DEFAULT (unixepoch('now')),
                    updated_at      REAL NOT NULL DEFAULT (unixepoch('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_variants_decision
                    ON variant_sets (decision_key);
                CREATE INDEX IF NOT EXISTS idx_variants_project_lock
                    ON variant_sets (project, lock);
                """
            )

    # ----------------- CRUD -----------------

    def create(self, vs: VariantSet) -> str:
        """Insert a new variant set. Returns its id."""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO variant_sets
                    (id, decision_key, project, prompt_template, strategy,
                     lock, variants_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vs.id, vs.decision_key, vs.project, vs.prompt_template,
                    vs.strategy.value, vs.lock.value,
                    json.dumps([asdict(v) for v in vs.variants]),
                    json.dumps(vs.metadata),
                ),
            )
        log.bind(set_id=vs.id, decision=vs.decision_key).info(
            f"variant set created ({len(vs.variants)} variants)"
        )
        return vs.id

    def save(self, vs: VariantSet) -> None:
        """Persist the current state of a variant set (after edits)."""
        with self._lock:
            self._conn.execute(
                """
                UPDATE variant_sets
                SET decision_key = ?, project = ?, prompt_template = ?,
                    strategy = ?, lock = ?, locked_index = ?, locked_at = ?,
                    locked_by = ?, variants_json = ?, metadata_json = ?,
                    updated_at = unixepoch('now')
                WHERE id = ?
                """,
                (
                    vs.decision_key, vs.project, vs.prompt_template,
                    vs.strategy.value, vs.lock.value, vs.locked_index,
                    vs.locked_at, vs.locked_by,
                    json.dumps([asdict(v) for v in vs.variants]),
                    json.dumps(vs.metadata),
                    vs.id,
                ),
            )

    def get(self, set_id: str) -> VariantSet | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM variant_sets WHERE id = ?", (set_id,)
            ).fetchone()
        return self._row_to_set(row) if row else None

    def find_by_decision(self, decision_key: str) -> VariantSet | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM variant_sets WHERE decision_key = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (decision_key,),
            ).fetchone()
        return self._row_to_set(row) if row else None

    def list_for_project(
        self, project: str, *, lock: VariantLock | None = None, limit: int = 100
    ) -> list[VariantSet]:
        sql = "SELECT * FROM variant_sets WHERE project = ?"
        params: list[Any] = [project]
        if lock is not None:
            sql += " AND lock = ?"
            params.append(lock.value)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_set(r) for r in rows]

    def list_open(self, project: str | None = None, limit: int = 100) -> list[VariantSet]:
        return self.list_for_project(project, lock=VariantLock.OPEN, limit=limit) \
            if project else \
            self._list_open_any(limit)

    def _list_open_any(self, limit: int) -> list[VariantSet]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM variant_sets WHERE lock = 'open' "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_set(r) for r in rows]

    def delete(self, set_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM variant_sets WHERE id = ?", (set_id,))
            return cur.rowcount > 0

    def stats(self, project: str | None = None) -> dict[str, int]:
        sql = "SELECT lock, COUNT(*) AS n FROM variant_sets"
        params: list[Any] = []
        if project:
            sql += " WHERE project = ?"
            params.append(project)
        sql += " GROUP BY lock"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return {r["lock"]: r["n"] for r in rows}

    def _row_to_set(self, row: sqlite3.Row) -> VariantSet:
        return VariantSet(
            id=row["id"],
            decision_key=row["decision_key"],
            project=row["project"],
            prompt_template=row["prompt_template"],
            strategy=GenerationStrategy(row["strategy"]),
            lock=VariantLock(row["lock"]),
            locked_index=row["locked_index"],
            locked_at=row["locked_at"],
            locked_by=row["locked_by"],
            variants=[Variant(**v) for v in json.loads(row["variants_json"])],
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# ----------------- Strategy helpers -----------------


def plan_seeds(
    base_seed: int | None,
    count: int,
    *,
    strategy: GenerationStrategy = GenerationStrategy.SEED_VARIATION,
) -> list[int]:
    """Return ``count`` seeds following the chosen strategy.

    - ``SEED_VARIATION``: consecutive integers from ``base_seed``.
    - ``PROMPT_VARIATION``: all the same (caller varies the prompt).
    - ``MIXED``: base_seed + stride.
    - ``PARAMETER_SWEEP``: all the same (caller varies the params).
    """
    if base_seed is None:
        base_seed = int(time.time()) % (2**31)
    if strategy in (GenerationStrategy.SEED_VARIATION, GenerationStrategy.MIXED):
        return [base_seed + i for i in range(count)]
    return [base_seed] * count


def new_variant_set_id() -> str:
    return uuid.uuid4().hex
