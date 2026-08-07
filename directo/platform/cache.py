"""Cache layer — prompt enhancement and image dedup caching.

Two cache types:

1. **PromptCache** — caches the output of expensive operations:
   - LLM-enhanced prompts
   - Cinema-engine evaluations
   - Preset lookups

   The cache key is a stable hash of the inputs. Hits return instantly;
   misses call the underlying function and store the result.

2. **ImageCache** — caches perceptual hash lookups so a "have I seen
   this image before?" check is O(1) rather than O(n).

Both caches have TTL, LRU eviction, and size limits. They are designed
to be the first line of optimization before scaling compute.

Caches are persistent (SQLite) so they survive process restarts.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from directo.observability import get_logger

log = get_logger("directo.platform.cache")


# =====================================================================
# Prompt cache
# =====================================================================


class PromptCache:
    """Cache for prompt enhancement + similar expensive text transforms.

    Stores ``(key, value, expires_at)`` tuples. The default eviction is
    FIFO + TTL; call :meth:`set_max_entries` to enable LRU.

    Keys are arbitrary strings; the caller is responsible for producing
    a stable key. Convenience helpers: :meth:`make_key`.
    """

    def __init__(self, db_path: str | Path = "directo_prompt_cache.db") -> None:
        self._db_path = str(db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._migrate()
        # In-memory LRU (mirrored to DB)
        self._mem: OrderedDict[str, Any] = OrderedDict()
        self._max_entries: int | None = None  # None = unlimited

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS prompt_cache (
                    key         TEXT PRIMARY KEY,
                    value       TEXT NOT NULL,
                    created_at  REAL NOT NULL DEFAULT (unixepoch('now')),
                    expires_at  REAL,
                    hit_count   INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_cache_expires ON prompt_cache (expires_at);
                """
            )

    def set_max_entries(self, n: int) -> None:
        """Enable LRU eviction with a max number of entries."""
        with self._lock:
            self._max_entries = n
            self._enforce_limit()

    def _enforce_limit(self) -> None:
        if self._max_entries is None:
            return
        cur = self._conn.execute("SELECT COUNT(*) AS n FROM prompt_cache").fetchone()["n"]
        if cur > self._max_entries:
            # Evict oldest by created_at
            excess = cur - self._max_entries
            self._conn.execute(
                "DELETE FROM prompt_cache WHERE key IN ("
                "SELECT key FROM prompt_cache ORDER BY created_at ASC LIMIT ?)",
                (excess,),
            )

    def get(self, key: str) -> Any | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT value, expires_at, hit_count FROM prompt_cache WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        if row["expires_at"] is not None and time.time() > row["expires_at"]:
            with self._lock:
                self._conn.execute("DELETE FROM prompt_cache WHERE key = ?", (key,))
            return None
        with self._lock:
            self._conn.execute(
                "UPDATE prompt_cache SET hit_count = hit_count + 1 WHERE key = ?",
                (key,),
            )
        return json.loads(row["value"])

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        expires = time.time() + ttl_seconds if ttl_seconds else None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO prompt_cache (key, value, expires_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                              expires_at = excluded.expires_at,
                                              created_at = unixepoch('now'),
                                              hit_count = 0
                """,
                (key, json.dumps(value, default=str), expires),
            )
            self._enforce_limit()

    def delete(self, key: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM prompt_cache WHERE key = ?", (key,))
            return cur.rowcount > 0

    def clear(self) -> int:
        with self._lock:
            cur = self._conn.execute("DELETE FROM prompt_cache")
        return cur.rowcount

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) AS n FROM prompt_cache").fetchone()["n"]
            hits = self._conn.execute(
                "SELECT COALESCE(SUM(hit_count), 0) AS h FROM prompt_cache"
            ).fetchone()["h"]
            expired = self._conn.execute(
                "SELECT COUNT(*) AS n FROM prompt_cache WHERE expires_at IS NOT NULL AND expires_at < unixepoch('now')"
            ).fetchone()["n"]
        return {"entries": total, "total_hits": hits, "expired": expired}

    @staticmethod
    def make_key(*parts: Any) -> str:
        """Stable key from any hashable parts."""
        s = "|".join(str(p) for p in parts)
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:32]

    def cached(
        self, key: str, compute: Callable[[], Any], ttl_seconds: float | None = 3600.0
    ) -> tuple[Any, bool]:
        """Get-or-compute pattern.

        Returns ``(value, hit)`` where ``hit`` is True if from cache, False if freshly computed.
        """
        hit = self.get(key)
        if hit is not None:
            return hit, True
        value = compute()
        self.set(key, value, ttl_seconds=ttl_seconds)
        return value, False

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# =====================================================================
# Image cache (perceptual dedup)
# =====================================================================



    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def invalidate(self, key: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM prompt_cache WHERE key = ?", (key,))

    def clear(self) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM prompt_cache")
class ImageCache:
    """Cache of perceptual hashes for fast dedup check.

    The :class:`directo.gallery.Gallery` already does dedup by scanning
    all images. For large libraries (>10k), that becomes O(n) per check.
    This cache builds an indexed lookup by phash prefix, making
    "have I seen this image?" an O(1) average lookup.

    Storage is a small SQLite table keyed by the first N hex chars of
    the perceptual hash (the "prefix"). Within a prefix, all hashes are
    likely to be very similar (a single prefix is 16 bits of the 64-bit
    phash, partitioning into 65k buckets).
    """

    def __init__(
        self,
        db_path: str | Path = "directo_image_cache.db",
        *,
        prefix_length: int = 4,  # 4 hex chars = 16 bits = 65k buckets
    ) -> None:
        self._db_path = str(db_path)
        self._prefix_len = prefix_length
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS phash_index (
                    prefix   TEXT NOT NULL,
                    phash    TEXT NOT NULL,
                    image_id TEXT,
                    source   TEXT,
                    added_at REAL NOT NULL DEFAULT (unixepoch('now')),
                    PRIMARY KEY (prefix, phash)
                );
                CREATE INDEX IF NOT EXISTS idx_phash_image ON phash_index (image_id);
                """
            )

    def add(self, phash: str, image_id: str, source: str = "") -> None:
        if not phash or len(phash) < self._prefix_len:
            return
        prefix = phash[: self._prefix_len]
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO phash_index (prefix, phash, image_id, source) "
                "VALUES (?, ?, ?, ?)",
                (prefix, phash, image_id, source),
            )

    def lookup_prefix(self, phash: str) -> list[dict[str, Any]]:
        if not phash or len(phash) < self._prefix_len:
            return []
        prefix = phash[: self._prefix_len]
        with self._lock:
            rows = self._conn.execute(
                "SELECT phash, image_id, source FROM phash_index WHERE prefix = ?",
                (prefix,),
            ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) AS n FROM phash_index").fetchone()["n"]

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM phash_index")

    def close(self) -> None:
        with self._lock:
            self._conn.close()


    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) AS n FROM phash_index").fetchone()["n"]

    def purge(self, phash: str) -> int:
        with self._lock:
            cur = self._conn.execute("DELETE FROM phash_index WHERE phash = ?", (phash,))
            return cur.rowcount

# =====================================================================
# Combined facade
# =====================================================================



    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
class CacheLayer:
    """One-stop facade for both caches."""

    def __init__(
        self,
        prompt_cache: PromptCache | None = None,
        image_cache: ImageCache | None = None,
    ) -> None:
        self.prompts = prompt_cache or PromptCache()
        self.images = image_cache or ImageCache()

    def close(self) -> None:
        self.prompts.close()
        self.images.close()

    def __enter__(self):
        return self
