"""SQLite-backed persistent job queue.

A FIFO queue with priorities, retries, exponential backoff, scheduled
delayed jobs, and a dead-letter queue (DLQ). Designed for concurrent
access from multiple workers (across processes if needed) via SQLite's
WAL mode.

Key behaviors:
- ``enqueue`` is non-blocking and atomic.
- ``claim`` is atomic and selects the highest-priority, oldest pending
  job whose ``scheduled_at`` is in the past. Uses
  ``BEGIN IMMEDIATE`` to avoid races.
- ``complete`` / ``fail`` update the job state and (for failures)
  schedule a retry up to ``max_retries``, then move to DLQ.
- ``reap_stale`` finds RUNNING jobs that have not heartbeat-recently
  and re-enqueues them. This is the crash-recovery primitive: if a
  worker dies mid-job, the watchdog puts the job back in the queue.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from directo.observability import MetricsCollector, bind_context, get_logger
from directo.platform.db import get_db_connection
from directo.queue.job import Job, JobState

log = get_logger("directo.queue")


class PersistentQueue:
    """SQLite-backed job queue with priorities, retries, and DLQ.

    :param db_path: path to SQLite file. Use ``":memory:"`` for tests
        (but note: in-memory queues are per-process and don't survive
        crashes — that's the whole point of persistence).
    :param stale_timeout_seconds: if a RUNNING job hasn't heartbeat in
        this many seconds, it is considered abandoned and reaped.
    """

    def __init__(
        self,
        db_path: str | Path = "directo_queue.db",
        *,
        stale_timeout_seconds: float = 300.0,
        metrics: MetricsCollector | None = None,
    ) -> None:
        self._db_path = str(db_path)
        self._stale_timeout = stale_timeout_seconds
        self._metrics = metrics or MetricsCollector()
        self._lock = threading.RLock()

        self._conn = get_db_connection(
            self._db_path,
            check_same_thread=False,
            isolation_level=None,  # autocommit; we use explicit BEGIN
            timeout=30.0,
        )
        self._migrate()

    # ----------------- Schema -----------------

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id              TEXT PRIMARY KEY,
                    kind            TEXT NOT NULL,
                    payload_json    TEXT NOT NULL,
                    correlation_id  TEXT,
                    project         TEXT,
                    user            TEXT,
                    node            TEXT NOT NULL DEFAULT 'default',
                    priority        INTEGER NOT NULL DEFAULT 100,
                    scheduled_at    REAL,
                    max_retries     INTEGER NOT NULL DEFAULT 3,
                    retry_count     INTEGER NOT NULL DEFAULT 0,
                    last_error      TEXT,
                    backoff_seconds REAL NOT NULL DEFAULT 2.0,
                    timeout_seconds REAL,
                    state           TEXT NOT NULL DEFAULT 'pending',
                    created_at      REAL NOT NULL DEFAULT (unixepoch('now')),
                    updated_at      REAL NOT NULL DEFAULT (unixepoch('now')),
                    started_at      REAL,
                    finished_at     REAL,
                    heartbeat_at    REAL,
                    result_json     TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_state_priority
                    ON jobs (state, priority, created_at);

                CREATE INDEX IF NOT EXISTS idx_jobs_scheduled
                    ON jobs (scheduled_at) WHERE scheduled_at IS NOT NULL;

                CREATE INDEX IF NOT EXISTS idx_jobs_node_state
                    ON jobs (node, state);
                """
            )

    # ----------------- Enqueue -----------------

    def enqueue(self, job: Job) -> str:
        """Add a job to the queue. Returns the job id."""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO jobs (
                    id, kind, payload_json, correlation_id, project, user, node,
                    priority, scheduled_at, max_retries, retry_count, backoff_seconds,
                    timeout_seconds, state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.kind,
                    json.dumps(job.payload, default=str),
                    job.correlation_id,
                    job.project,
                    job.user,
                    job.node,
                    job.priority,
                    job.scheduled_at,
                    job.max_retries,
                    job.retry_count,
                    job.backoff_seconds,
                    job.timeout_seconds,
                    JobState.PENDING.value,
                ),
            )
            self._refresh_metrics()
            log.bind(job_id=job.id, kind=job.kind).info(
                "job enqueued", priority=job.priority, node=job.node
            )
            return job.id

    def enqueue_many(self, jobs: Iterable[Job]) -> list[str]:
        """Bulk-enqueue jobs in a single transaction."""
        ids: list[str] = []
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                for job in jobs:
                    self.enqueue(job)
                    ids.append(job.id)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        return ids

    # ----------------- Claim -----------------

    def claim(self, worker_id: str, node: str | None = None) -> Job | None:
        """Atomically claim the next available job for this worker.

        Returns ``None`` if no job is available. The job is moved to
        RUNNING with a fresh ``heartbeat_at`` so the watchdog knows
        it's alive.

        :param worker_id: free-form identifier for the calling worker
            (used in logs/audit)
        :param node: optional node filter — only claim jobs targeting
            this node. ``None`` = any node.
        """
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                where = "state = ? AND (scheduled_at IS NULL OR scheduled_at <= ?)"
                params: list[Any] = [JobState.PENDING.value, time.time()]
                if node is not None:
                    where += " AND node = ?"
                    params.append(node)
                row = self._conn.execute(
                    f"""
                    SELECT * FROM jobs
                    WHERE {where}
                    ORDER BY priority ASC, created_at ASC
                    LIMIT 1
                    """,
                    params,
                ).fetchone()
                if row is None:
                    self._conn.execute("COMMIT")
                    return None
                now = time.time()
                self._conn.execute(
                    """
                    UPDATE jobs
                    SET state = ?, started_at = ?, heartbeat_at = ?, updated_at = ?,
                        last_error = NULL
                    WHERE id = ?
                    """,
                    (JobState.RUNNING.value, now, now, now, row["id"]),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

        job = self._row_to_job(row)
        # row was loaded BEFORE we updated state; refresh from DB
        return self.get(job.id)

    # ----------------- Heartbeat / progress -----------------

    def heartbeat(self, job_id: str) -> None:
        """Update the heartbeat timestamp for a running job.

        Workers should call this every 30-60s while a job is in flight
        to prevent the watchdog from reaping it.
        """
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET heartbeat_at = ? WHERE id = ? AND state = ?",
                (time.time(), job_id, JobState.RUNNING.value),
            )

    # ----------------- Completion / failure -----------------

    def complete(self, job_id: str, result: dict[str, Any] | None = None) -> None:
        """Mark a job as completed (terminal state)."""
        now = time.time()
        with self._lock:
            self._conn.execute(
                """
                UPDATE jobs
                SET state = ?, finished_at = ?, updated_at = ?, result_json = ?
                WHERE id = ? AND state = ?
                """,
                (JobState.COMPLETED.value, now, now,
                 json.dumps(result, default=str) if result else None,
                 job_id, JobState.RUNNING.value),
            )
            self._refresh_metrics()
        log.bind(job_id=job_id).info("job completed")

    def fail(self, job_id: str, error: str, *, requeue: bool = True) -> None:
        """Mark a job as failed.

        If ``requeue=True`` and retries remain, the job is re-enqueued
        with exponential backoff. Otherwise it goes to the DLQ.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT retry_count, max_retries, backoff_seconds FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return
            retry_count = row["retry_count"]
            max_retries = row["max_retries"]
            backoff = row["backoff_seconds"]

            if requeue and retry_count < max_retries:
                next_at = time.time() + backoff * (2 ** retry_count)
                self._conn.execute(
                    """
                    UPDATE jobs
                    SET state = ?, scheduled_at = ?, retry_count = retry_count + 1,
                        last_error = ?, heartbeat_at = NULL, updated_at = ?
                    WHERE id = ?
                    """,
                    (JobState.PENDING.value, next_at, error, time.time(), job_id),
                )
                log.bind(job_id=job_id).warning(
                    f"job failed, retry {retry_count + 1}/{max_retries} in {next_at - time.time():.1f}s: {error}"
                )
            else:
                self._conn.execute(
                    """
                    UPDATE jobs
                    SET state = ?, finished_at = ?, updated_at = ?, last_error = ?,
                        heartbeat_at = NULL
                    WHERE id = ?
                    """,
                    (JobState.FAILED.value, time.time(), time.time(), error, job_id),
                )
                log.bind(job_id=job_id).error(f"job failed permanently (DLQ): {error}")
            self._refresh_metrics()

    def cancel(self, job_id: str) -> bool:
        """Cancel a job. Returns True if the job was cancellable."""
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE jobs
                SET state = ?, updated_at = ?
                WHERE id = ? AND state IN (?, ?)
                """,
                (JobState.CANCELLED.value, time.time(),
                 job_id, JobState.PENDING.value, JobState.RUNNING.value),
            )
            return cur.rowcount > 0

    # ----------------- Watchdog -----------------

    def reap_stale(self) -> int:
        """Re-queue jobs whose worker has not heartbeat recently.

        Returns the number of jobs reaped. Call this from a periodic
        background task (every 30-60s).
        """
        cutoff = time.time() - self._stale_timeout
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE jobs
                SET state = ?, last_error = 'reaped: worker timeout', heartbeat_at = NULL,
                    retry_count = retry_count + 1, updated_at = ?
                WHERE state = ? AND (heartbeat_at IS NULL OR heartbeat_at < ?)
                """,
                (JobState.PENDING.value, time.time(), JobState.RUNNING.value, cutoff),
            )
            count = cur.rowcount
            if count:
                log.warning(f"reaped {count} stale jobs (worker timeout)")
            return count

    # ----------------- Queries -----------------

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def list_by_state(self, state: JobState, limit: int = 100) -> list[Job]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM jobs WHERE state = ? ORDER BY created_at DESC LIMIT ?",
                (state.value, limit),
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def depth(self, state: JobState | None = None) -> int:
        with self._lock:
            if state is None:
                row = self._conn.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COUNT(*) AS n FROM jobs WHERE state = ?", (state.value,)
                ).fetchone()
            return row["n"] if row else 0

    def stats(self) -> dict[str, int]:
        """Return a dict of {state: count} for dashboard display."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT state, COUNT(*) AS n FROM jobs GROUP BY state"
            ).fetchall()
        return {r["state"]: r["n"] for r in rows}

    # ----------------- Maintenance -----------------

    def purge_terminal(self, older_than_seconds: float = 86400 * 7) -> int:
        """Delete terminal jobs older than the given age. Returns count deleted."""
        cutoff = time.time() - older_than_seconds
        with self._lock:
            cur = self._conn.execute(
                """
                DELETE FROM jobs
                WHERE state IN (?, ?, ?)
                  AND COALESCE(finished_at, updated_at) < ?
                """,
                (JobState.COMPLETED.value, JobState.FAILED.value,
                 JobState.CANCELLED.value, cutoff),
            )
            return cur.rowcount

    # ----------------- Internals -----------------

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
        result = json.loads(row["result_json"]) if row["result_json"] else None
        return Job(
            id=row["id"],
            kind=row["kind"],
            payload=payload,
            correlation_id=row["correlation_id"],
            project=row["project"],
            user=row["user"],
            node=row["node"],
            priority=row["priority"],
            scheduled_at=row["scheduled_at"],
            max_retries=row["max_retries"],
            retry_count=row["retry_count"],
            last_error=row["last_error"],
            backoff_seconds=row["backoff_seconds"],
            timeout_seconds=row["timeout_seconds"],
            state=JobState(row["state"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            result=result,
        )

    def _refresh_metrics(self) -> None:
        try:
            for state in JobState:
                self._metrics.set_queue_depth(state.value, self.depth(state))
        except Exception:  # pragma: no cover
            pass

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "PersistentQueue":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


