"""Tests for the persistent queue."""

import asyncio
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from directo.queue import Job, JobState, PersistentQueue, Worker


def test_enqueue_and_claim():
    with PersistentQueue(":memory:") as q:
        job = Job(kind="test.kind", payload={"x": 1})
        q.enqueue(job)
        claimed = q.claim("worker-1")
        assert claimed is not None
        assert claimed.id == job.id
        assert claimed.state == JobState.RUNNING


def test_priority_ordering():
    with PersistentQueue(":memory:") as q:
        low = Job(kind="t", priority=100)
        high = Job(kind="t", priority=1)
        mid = Job(kind="t", priority=50)
        q.enqueue(low)
        q.enqueue(high)
        q.enqueue(mid)
        assert q.claim("w").id == high.id
        assert q.claim("w").id == mid.id
        assert q.claim("w").id == low.id


def test_fifo_within_same_priority():
    with PersistentQueue(":memory:") as q:
        ids = []
        for _ in range(5):
            j = Job(kind="t", priority=10)
            q.enqueue(j)
            ids.append(j.id)
        for expected in ids:
            assert q.claim("w").id == expected


def test_scheduled_jobs_respected():
    with PersistentQueue(":memory:") as q:
        # Future job
        future = Job(kind="t", scheduled_at=time.time() + 3600)
        # Immediate job
        now = Job(kind="t")
        q.enqueue(future)
        q.enqueue(now)
        assert q.claim("w").id == now.id
        assert q.claim("w") is None  # future not ready


def test_complete_terminal():
    with PersistentQueue(":memory:") as q:
        job = Job(kind="t")
        q.enqueue(job)
        claimed = q.claim("w")
        q.complete(claimed.id, result={"ok": True})
        rec = q.get(claimed.id)
        assert rec.state == JobState.COMPLETED
        assert rec.result == {"ok": True}
        assert q.claim("w") is None


def test_fail_then_retry_with_backoff():
    with PersistentQueue(":memory:") as q:
        job = Job(kind="t", max_retries=2, backoff_seconds=0.01)
        q.enqueue(job)
        claimed = q.claim("w")
        q.fail(claimed.id, "error-1")
        # Job is now PENDING with scheduled_at in the future
        rec = q.get(claimed.id)
        assert rec.state == JobState.PENDING
        assert rec.retry_count == 1
        # Wait for backoff window
        time.sleep(0.05)
        # Should be claimable again
        again = q.claim("w")
        assert again.id == claimed.id
        assert again.retry_count == 1
        q.fail(again.id, "error-2")
        rec2 = q.get(claimed.id)
        assert rec2.retry_count == 2
        time.sleep(0.1)
        q.claim("w")  # third attempt
        q.fail(claimed.id, "error-3", requeue=False)  # final
        final = q.get(claimed.id)
        assert final.state == JobState.FAILED


def test_cancel_pending():
    with PersistentQueue(":memory:") as q:
        job = Job(kind="t")
        q.enqueue(job)
        assert q.cancel(job.id) is True
        assert q.get(job.id).state == JobState.CANCELLED


def test_cancel_running():
    with PersistentQueue(":memory:") as q:
        job = Job(kind="t")
        q.enqueue(job)
        q.claim("w")
        assert q.cancel(job.id) is True


def test_reap_stale_jobs():
    with PersistentQueue(":memory:", stale_timeout_seconds=0.5) as q:
        job = Job(kind="t")
        q.enqueue(job)
        q.claim("w")
        # Simulate stale: no heartbeat for 1s
        time.sleep(0.6)
        reaped = q.reap_stale()
        assert reaped == 1
        # Now should be re-claimable
        time.sleep(0.01)
        again = q.claim("w")
        assert again is not None
        assert again.id == job.id


def test_node_filter():
    with PersistentQueue(":memory:") as q:
        q.enqueue(Job(kind="t", node="gpu-a"))
        q.enqueue(Job(kind="t", node="gpu-b"))
        a = q.claim("w", node="gpu-a")
        assert a.node == "gpu-a"
        b = q.claim("w", node="gpu-b")
        assert b.node == "gpu-b"
        assert q.claim("w", node="gpu-a") is None


def test_stats():
    with PersistentQueue(":memory:") as q:
        for _ in range(3):
            j = Job(kind="t")
            q.enqueue(j)
            q.claim("w")
            q.complete(j.id)
        for _ in range(2):
            j = Job(kind="t")
            q.enqueue(j)
        stats = q.stats()
        assert stats.get("completed") == 3
        assert stats.get("pending") == 2


def test_heartbeat_prevents_reaping():
    with PersistentQueue(":memory:", stale_timeout_seconds=0.3) as q:
        job = Job(kind="t")
        q.enqueue(job)
        q.claim("w")
        # Heartbeat before stale
        for _ in range(4):
            time.sleep(0.1)
            q.heartbeat(job.id)
        # Should NOT be reaped
        reaped = q.reap_stale()
        assert reaped == 0


@pytest.mark.asyncio
async def test_worker_runs_handler():
    with PersistentQueue(":memory:") as q:
        results = {}

        async def handler(job: Job):
            results[job.id] = job.payload.get("v")
            return {"ok": True}

        worker = Worker(q, worker_id="w1", poll_interval=0.05)
        worker.register("t", handler)

        task = asyncio.create_task(worker.run())
        q.enqueue(Job(kind="t", payload={"v": 42}))
        await asyncio.sleep(0.2)
        worker.stop()
        await task

        assert 42 in results.values()
        assert q.depth(JobState.COMPLETED) == 1


@pytest.mark.asyncio
async def test_worker_retries_on_failure():
    """A failing handler should trigger retry, then success."""
    with PersistentQueue(":memory:") as q:
        attempts = []

        async def flaky_handler(job: Job):
            attempts.append(job.id)
            if len(attempts) < 2:
                raise RuntimeError("boom")
            return {"ok": True}

        worker = Worker(q, worker_id="w1", poll_interval=0.05)
        worker.register("t", flaky_handler)

        task = asyncio.create_task(worker.run())
        # Override backoff for fast test
        job = Job(kind="t", max_retries=3, backoff_seconds=0.05)
        q.enqueue(job)
        await asyncio.sleep(0.5)
        worker.stop()
        await task

        assert len(attempts) == 2
        assert q.get(job.id).state == JobState.COMPLETED


@pytest.mark.asyncio
async def test_worker_sends_to_dlq_after_max_retries():
    with PersistentQueue(":memory:") as q:
        async def always_fails(job: Job):
            raise RuntimeError("nope")

        worker = Worker(q, worker_id="w1", poll_interval=0.05)
        worker.register("t", always_fails)

        task = asyncio.create_task(worker.run())
        job = Job(kind="t", max_retries=1, backoff_seconds=0.05)
        q.enqueue(job)
        await asyncio.sleep(0.5)
        worker.stop()
        await task

        final = q.get(job.id)
        assert final.state == JobState.FAILED
        assert "nope" in final.last_error
