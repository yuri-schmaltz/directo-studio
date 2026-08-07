"""Style/character/composition reference library.

A drop-in personal library of "this is the look/character/composition
I want" images. Each reference is stored with three things:

1. The file on disk (the actual image).
2. Metadata: kind, tags, source, notes.
3. A pre-computed embedding (CLIP or a simpler model) so the library
   can answer "find me references similar to this one" without
   re-running the model every time.

The library is the source of truth for **what to feed into IP-Adapter,
ControlNet, reference-only, or any other conditioning pipeline**.

The embedding backend is pluggable. We ship with:

- ``PillowBackend`` — fallback that uses pixel histograms (no model
  required, low quality, always available).
- ``ClipBackend`` — uses OpenCLIP / openai-clip if installed.

In production you'd add a remote backend (e.g. a small embedding
service), but the API stays the same.
"""

from __future__ import annotations

import enum
import hashlib
import json
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, Self

from directo.observability import get_logger

log = get_logger("directo.references")


# ----------------- Domain model -----------------


class ReferenceKind(str, enum.Enum):
    """What a reference image represents."""

    STYLE = "style"
    CHARACTER = "character"
    COMPOSITION = "composition"
    MOOD = "mood"
    OBJECT = "object"
    REFERENCE = "reference"


@dataclass
class Reference:
    """A single reference image in the library."""

    id: str
    path: str
    kind: ReferenceKind = ReferenceKind.REFERENCE
    title: str = ""
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    source: str = "user"  # user/upload/community/synthesis
    width: int | None = None
    height: int | None = None
    embedding: list[float] | None = None
    embedding_model: str | None = None
    file_hash: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    use_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Reference:
        d = dict(data)
        d["kind"] = ReferenceKind(d.get("kind", "reference"))
        d.setdefault("tags", [])
        return cls(**d)


# ----------------- Embedding backends -----------------


class EmbeddingBackend(Protocol):
    """Protocol all reference embedding backends implement."""

    name: str

    def embed(self, image_path: str) -> list[float]: ...
    def similarity(self, a: list[float], b: list[float]) -> float: ...
    def dimension(self) -> int: ...


class PillowBackend:
    """Cheap fallback: 64-bin RGB histogram. Always available, low quality.

    Good enough for "is this the same kind of image?" style queries
    while a real CLIP model isn't installed.
    """

    name = "pillow-histogram-64"
    _DIM = 64 * 3  # 64 bins per R, G, B channel

    def dimension(self) -> int:
        return self._DIM

    def embed(self, image_path: str) -> list[float]:
        from PIL import Image
        img = Image.open(image_path).convert("RGB").resize((128, 128))
        hist = img.histogram()  # 256 bins per channel = 768
        # Reduce to 64 bins per channel by summing groups of 4
        reduced: list[float] = []
        for channel in (hist[:256], hist[256:512], hist[512:768]):
            for i in range(0, 256, 4):
                reduced.append(float(sum(channel[i : i + 4])))
        # L2 normalize so cosine similarity is meaningful
        norm = sum(x * x for x in reduced) ** 0.5 or 1.0
        return [x / norm for x in reduced]

    def similarity(self, a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        return sum(x * y for x, y in zip(a, b))  # already L2-normalized


class ClipBackend:
    """Real CLIP embedding via ``open_clip`` (if installed).

    Install with: ``pip install open_clip_torch torch``
    Falls back to a placeholder if the dependency is missing — the
    library stays usable, just with weaker search.
    """

    name = "openclip-vit-b-32"

    def __init__(self) -> None:
        try:
            import open_clip  # type: ignore
            import torch  # type: ignore
            self._model, _, self._preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32", pretrained="laion2b_s34b_b79k"
            )
            self._model.eval()
            self._torch = torch
            self._available = True
        except Exception:  # noqa: BLE001
            log.warning("open_clip not available; ClipBackend disabled")
            self._available = False

    def dimension(self) -> int:
        return 512  # ViT-B-32 output dim

    def embed(self, image_path: str) -> list[float]:
        if not self._available:
            raise RuntimeError("ClipBackend not available; install open_clip_torch")
        from PIL import Image
        img = Image.open(image_path).convert("RGB")
        tensor = self._preprocess(img).unsqueeze(0)
        with self._torch.no_grad():
            features = self._model.encode_image(tensor)
        features = features / features.norm(dim=-1, keepdim=True)
        return features[0].tolist()

    def similarity(self, a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        return sum(x * y for x, y in zip(a, b))  # L2-normalized → dot product


def get_default_backend() -> EmbeddingBackend:
    """Return ClipBackend if available, else PillowBackend."""
    clip = ClipBackend()
    if clip._available:  # type: ignore[attr-defined]
        return clip
    return PillowBackend()


# ----------------- The library -----------------


class ReferenceLibrary:
    """The user's personal reference library.

    A SQLite store + embedding cache. Adding a new reference is O(1)
    (file copy optional, embedding computed lazily or eagerly).
    Searching by similarity runs against the pre-computed embeddings —
    O(N) but fast for libraries up to ~10k entries.
    """

    def __init__(
        self,
        db_path: str | Path = "directo_references.db",
        *,
        storage_dir: str | Path | None = None,
        backend: EmbeddingBackend | None = None,
    ) -> None:
        self._db_path = str(db_path)
        self._storage = Path(storage_dir) if storage_dir else None
        self._backend: EmbeddingBackend = backend or get_default_backend()
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS refs (
                    id              TEXT PRIMARY KEY,
                    path            TEXT NOT NULL,
                    kind            TEXT NOT NULL DEFAULT 'reference',
                    title           TEXT NOT NULL DEFAULT '',
                    tags_json       TEXT NOT NULL DEFAULT '[]',
                    notes           TEXT NOT NULL DEFAULT '',
                    source          TEXT NOT NULL DEFAULT 'user',
                    width           INTEGER,
                    height          INTEGER,
                    embedding_json  TEXT,
                    embedding_model TEXT,
                    file_hash       TEXT,
                    use_count       INTEGER NOT NULL DEFAULT 0,
                    created_at      REAL NOT NULL DEFAULT (unixepoch('now')),
                    updated_at      REAL NOT NULL DEFAULT (unixepoch('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_refs_kind ON refs (kind);
                CREATE INDEX IF NOT EXISTS idx_refs_file_hash ON refs (file_hash);
                """
            )

    # ----------------- Add / remove -----------------

    def add(
        self,
        path: str | Path,
        *,
        kind: ReferenceKind = ReferenceKind.REFERENCE,
        title: str = "",
        tags: Iterable[str] | None = None,
        notes: str = "",
        source: str = "user",
        compute_embedding: bool = True,
    ) -> str:
        """Add a reference to the library.

        The file is optionally copied into ``storage_dir`` so the
        library doesn't break if the source path changes. Set
        ``storage_dir=None`` at construction time to keep references
        where they are.

        Embedding is computed eagerly by default. Pass
        ``compute_embedding=False`` to skip (e.g. for batch imports)
        and call :meth:`backfill_embeddings` later.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"reference image not found: {path}")

        if self._storage:
            target = self._storage / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(path.read_bytes())
            stored_path = str(target)
        else:
            stored_path = str(path)

        # Hash for dedup
        h = hashlib.sha256(Path(stored_path).read_bytes()).hexdigest()[:16]
        with self._lock:
            existing = self._conn.execute(
                "SELECT id FROM refs WHERE file_hash = ?", (h,)
            ).fetchone()
            if existing:
                log.info(f"reference already in library (hash={h}); returning existing id")
                return existing["id"]

        # Optional: width/height
        width: int | None = None
        height: int | None = None
        try:
            from PIL import Image
            with Image.open(stored_path) as img:
                width, height = img.size
        except Exception:  # noqa: BLE001
            pass

        embedding: list[float] | None = None
        if compute_embedding:
            try:
                embedding = self._backend.embed(stored_path)
            except Exception as exc:  # noqa: BLE001
                log.warning(f"embedding failed: {exc}")

        ref_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO refs
                    (id, path, kind, title, tags_json, notes, source,
                     width, height, embedding_json, embedding_model, file_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ref_id, stored_path, kind.value, title,
                    json.dumps(list(tags or [])), notes, source,
                    width, height,
                    json.dumps(embedding) if embedding else None,
                    self._backend.name if embedding else None,
                    h,
                ),
            )
        log.bind(ref_id=ref_id, kind=kind.value).info(
            f"reference added: {title or path.name}", has_embedding=bool(embedding)
        )
        return ref_id

    def remove(self, ref_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM refs WHERE id = ?", (ref_id,))
            return cur.rowcount > 0

    # ----------------- Lookup -----------------

    def get(self, ref_id: str) -> Reference | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM refs WHERE id = ?", (ref_id,)
            ).fetchone()
        return self._row_to_ref(row) if row else None

    def find_by_path(self, path: str) -> Reference | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM refs WHERE path = ?", (path,)
            ).fetchone()
        return self._row_to_ref(row) if row else None

    def list(
        self,
        *,
        kind: ReferenceKind | None = None,
        tag: str | None = None,
        limit: int = 200,
    ) -> list[Reference]:
        clauses: list[str] = []
        params: list[Any] = []
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind.value)
        if tag is not None:
            clauses.append("tags_json LIKE ?")
            params.append(f'%"{tag}"%')
        where = " AND ".join(clauses) if clauses else "1=1"
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM refs WHERE {where} "
                f"ORDER BY updated_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()
        return [self._row_to_ref(r) for r in rows]

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) AS n FROM refs").fetchone()["n"]

    # ----------------- Search -----------------

    def find_similar_to_image(
        self,
        image_path: str,
        *,
        top_k: int = 10,
        kind: ReferenceKind | None = None,
    ) -> list[tuple[Reference, float]]:
        """Embed ``image_path`` and return the top-k most similar refs."""
        query = self._backend.embed(image_path)
        return self.find_similar_to_embedding(query, top_k=top_k, kind=kind)

    def find_similar_to_embedding(
        self,
        query: list[float],
        *,
        top_k: int = 10,
        kind: ReferenceKind | None = None,
    ) -> list[tuple[Reference, float]]:
        sql = (
            "SELECT * FROM refs "
            "WHERE embedding_json IS NOT NULL"
        )
        params: list[Any] = []
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind.value)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        scored: list[tuple[Reference, float]] = []
        for row in rows:
            emb = json.loads(row["embedding_json"])
            score = self._backend.similarity(query, emb)
            scored.append((self._row_to_ref(row), score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # ----------------- Maintenance -----------------

    def increment_use_count(self, ref_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE refs SET use_count = use_count + 1, updated_at = unixepoch('now') WHERE id = ?",
                (ref_id,),
            )

    def backfill_embeddings(self) -> int:
        """Compute embeddings for any reference that lacks one. Returns count."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, path FROM refs WHERE embedding_json IS NULL"
            ).fetchall()
        count = 0
        for row in rows:
            try:
                emb = self._backend.embed(row["path"])
                with self._lock:
                    self._conn.execute(
                        "UPDATE refs SET embedding_json = ?, embedding_model = ? "
                        "WHERE id = ?",
                        (json.dumps(emb), self._backend.name, row["id"]),
                    )
                count += 1
            except Exception as exc:  # noqa: BLE001
                log.warning(f"backfill failed for {row['id']}: {exc}")
        if count:
            log.info(f"backfilled {count} embeddings with {self._backend.name}")
        return count

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) AS n FROM refs").fetchone()["n"]
            embedded = self._conn.execute(
                "SELECT COUNT(*) AS n FROM refs WHERE embedding_json IS NOT NULL"
            ).fetchone()["n"]
            by_kind = self._conn.execute(
                "SELECT kind, COUNT(*) AS n FROM refs GROUP BY kind"
            ).fetchall()
        return {
            "total": total,
            "with_embedding": embedded,
            "backend": self._backend.name,
            "by_kind": {r["kind"]: r["n"] for r in by_kind},
        }

    def _row_to_ref(self, row: sqlite3.Row) -> Reference:
        return Reference(
            id=row["id"],
            path=row["path"],
            kind=ReferenceKind(row["kind"]),
            title=row["title"],
            tags=json.loads(row["tags_json"]) if row["tags_json"] else [],
            notes=row["notes"],
            source=row["source"],
            width=row["width"],
            height=row["height"],
            embedding=json.loads(row["embedding_json"]) if row["embedding_json"] else None,
            embedding_model=row["embedding_model"],
            file_hash=row["file_hash"],
            use_count=row["use_count"],
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
