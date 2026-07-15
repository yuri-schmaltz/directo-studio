"""Cost tracking for jobs and projects.

A real Directo deployment burns real money:

- GPU time (per node, billed by the second)
- LLM API calls (per token, varying by model)
- Storage (per GB, per month)
- Bandwidth (per GB egress)

The :class:`CostTracker` records these costs and produces reports.

Cost data is recorded once per job (final cost) AND incrementally
(streaming) so dashboards can show live cost. Costs are tagged with:

- ``project`` — for project-level accounting
- ``kind`` — gpu_seconds | llm_tokens | storage_gb | bandwidth_gb | etc.
- ``provider`` — "runpod", "openai", "anthropic", etc.
- ``job_id`` — link to a specific generation

Reports answer questions like:
- "How much did this project cost in the last month?"
- "What's my average cost per image generation?"
- "Which model is the most cost-effective?"

The tracker is storage-only — it doesn't auto-measure GPU time. You
record costs explicitly via :meth:`record_gpu` / :meth:`record_llm` /
:meth:`record_storage` etc. (Or hook it into the queue's job-completion
callback.)
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
from typing import Any, Iterable

from directo.observability import get_logger

log = get_logger("directo.platform.costs")


class CostKind(str, enum.Enum):
    GPU_SECONDS = "gpu_seconds"        # billed by GPU-time
    LLM_TOKENS = "llm_tokens"          # billed by LLM token
    STORAGE_GB = "storage_gb"          # per GB stored
    BANDWIDTH_GB = "bandwidth_gb"      # per GB transferred
    BANDWIDTH_BYTES = "bandwidth_bytes"  # per byte transferred
    COMFYUI_NODE_HOUR = "node_hour"   # ComfyUI server time
    API_REQUEST = "api_request"        # flat-fee API calls


# Unit prices (USD). These are SUGGESTED defaults; production should
# override with their actual negotiated rates. Storing prices in code
# means reports work even without configuration.
DEFAULT_PRICES: dict[CostKind, float] = {
    CostKind.GPU_SECONDS: 0.0007,        # ~$2.50/hour for an A100-class GPU
    CostKind.LLM_TOKENS: 0.000015,       # ~$15 per 1M input tokens (gpt-4o-mini)
    CostKind.STORAGE_GB: 0.023,          # S3 standard
    CostKind.BANDWIDTH_BYTES: 0.09 / (1024 ** 3),  # $0.09/GB → per byte
    CostKind.COMFYUI_NODE_HOUR: 0.50,
    CostKind.API_REQUEST: 0.001,
}


@dataclass
class CostRecord:
    """A single cost entry."""

    id: str
    project: str | None
    job_id: str | None
    kind: CostKind
    provider: str
    quantity: float
    unit_price_usd: float
    total_usd: float
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d


class CostTracker:
    """Persistent cost recorder + reporter."""

    def __init__(self, db_path: str | Path = "directo_costs.db") -> None:
        self._db_path = str(db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS costs (
                    id              TEXT PRIMARY KEY,
                    project         TEXT,
                    job_id          TEXT,
                    kind            TEXT NOT NULL,
                    provider        TEXT NOT NULL DEFAULT '',
                    quantity        REAL NOT NULL,
                    unit_price_usd  REAL NOT NULL,
                    total_usd       REAL NOT NULL,
                    metadata_json   TEXT NOT NULL DEFAULT '{}',
                    timestamp       REAL NOT NULL DEFAULT (unixepoch('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_costs_project_ts
                    ON costs (project, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_costs_job ON costs (job_id);
                CREATE INDEX IF NOT EXISTS idx_costs_kind_ts ON costs (kind, timestamp DESC);
                """
            )

    # ----------------- Recording -----------------

    def _record(
        self,
        kind: CostKind,
        quantity: float,
        *,
        project: str | None = None,
        job_id: str | None = None,
        provider: str = "",
        unit_price: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CostRecord:
        price = unit_price if unit_price is not None else DEFAULT_PRICES[kind]
        total = quantity * price
        rec = CostRecord(
            id=f"cost-{uuid.uuid4().hex[:12]}",
            project=project, job_id=job_id, kind=kind, provider=provider,
            quantity=quantity, unit_price_usd=price, total_usd=total,
            metadata=metadata or {},
        )
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO costs (id, project, job_id, kind, provider, quantity, unit_price_usd, total_usd, metadata_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rec.id, rec.project, rec.job_id, rec.kind.value, rec.provider,
                 rec.quantity, rec.unit_price_usd, rec.total_usd,
                 json.dumps(rec.metadata, default=str), rec.timestamp),
            )
        log.bind(kind=kind.value, project=project, job_id=job_id).info(
            f"cost recorded: {rec.total_usd:.4f} USD ({rec.quantity} × ${price})"
        )
        return rec

    def record_gpu(self, seconds: float, *, project: str | None = None, job_id: str | None = None,
                   node: str = "default", unit_price: float | None = None) -> CostRecord:
        return self._record(CostKind.GPU_SECONDS, seconds, project=project, job_id=job_id,
                            provider=node, unit_price=unit_price,
                            metadata={"node": node})

    def record_llm(self, tokens: int, *, project: str | None = None, job_id: str | None = None,
                   model: str = "gpt-4o-mini", unit_price: float | None = None) -> CostRecord:
        return self._record(CostKind.LLM_TOKENS, tokens, project=project, job_id=job_id,
                            provider=model, unit_price=unit_price,
                            metadata={"model": model, "tokens": tokens})

    def record_storage(self, gb: float, *, project: str | None = None) -> CostRecord:
        return self._record(CostKind.STORAGE_GB, gb, project=project, provider="storage")

    def record_bandwidth(self, gb: float, *, project: str | None = None) -> CostRecord:
        return self._record(CostKind.BANDWIDTH_BYTES, gb, project=project, provider="egress")

    # ----------------- Reporting -----------------

    def total(self, project: str | None = None, since: float | None = None) -> float:
        clauses, params = [], []
        if project:
            clauses.append("project = ?")
            params.append(project)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            row = self._conn.execute(
                f"SELECT COALESCE(SUM(total_usd), 0) AS t FROM costs {where}", params
            ).fetchone()
        return row["t"]

    def by_project(self, since: float | None = None) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT project, COUNT(*) AS entries, SUM(quantity) AS total_qty,
                       SUM(total_usd) AS total_cost
                FROM costs {where}
                GROUP BY project
                ORDER BY total_cost DESC
                """, params
            ).fetchall()
        return [dict(r) for r in rows]

    def by_kind(self, project: str | None = None, since: float | None = None) -> list[dict[str, Any]]:
        clauses, params = [], []
        if project:
            clauses.append("project = ?")
            params.append(project)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT kind, COUNT(*) AS entries, SUM(quantity) AS total_qty,
                       SUM(total_usd) AS total_cost
                FROM costs {where}
                GROUP BY kind
                ORDER BY total_cost DESC
                """, params
            ).fetchall()
        return [dict(r) for r in rows]

    def by_job(self, project: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        clauses = ["job_id IS NOT NULL"]
        params: list[Any] = []
        if project:
            clauses.append("project = ?")
            params.append(project)
        where = " AND ".join(clauses)
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT job_id, project, COUNT(*) AS entries,
                       SUM(total_usd) AS total_cost
                FROM costs
                WHERE {where}
                GROUP BY job_id
                ORDER BY total_cost DESC
                LIMIT ?
                """, params + [limit]
            ).fetchall()
        return [dict(r) for r in rows]

    def timeseries(
        self, *, project: str | None = None, since: float | None = None,
        bucket_seconds: int = 3600,  # 1 hour
    ) -> list[dict[str, Any]]:
        clauses, params = [], []
        if project:
            clauses.append("project = ?")
            params.append(project)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT CAST(timestamp / ? AS INTEGER) * ? AS bucket,
                       SUM(total_usd) AS cost
                FROM costs {where}
                GROUP BY bucket
                ORDER BY bucket
                """, [bucket_seconds, bucket_seconds] + params
            ).fetchall()
        return [dict(r) for r in rows]

    def set_prices(self, **overrides: float) -> None:
        """Override the default price for a kind.

        Example: ``set_prices(gpu_seconds=0.0005)``.
        """
        for k, v in overrides.items():
            try:
                DEFAULT_PRICES[CostKind(k)] = float(v)
            except (ValueError, KeyError) as exc:
                raise ValueError(f"unknown cost kind: {k}") from exc

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
