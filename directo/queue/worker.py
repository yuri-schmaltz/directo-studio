"""Async worker that pulls jobs from a :class:`PersistentQueue` and runs them.

The worker is intentionally tiny — its only job is the claim/run/report
loop. The actual work is done by handlers registered via
:meth:`Worker.register`.

Usage:
    >>> queue = PersistentQueue("directo.db")
    >>> worker = Worker(queue, worker_id="worker-1", poll_interval=0.5)
    >>> worker.register("image.generate", handle_image_generation)
    >>> await worker.run()  # blocks until cancelled
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from directo.observability import bind_context, correlation_id_var, get_logger
from directo.queue.job import Job
from directo.queue.persistent_queue import PersistentQueue

log = get_logger("directo.worker")

Handler = Callable[[Job], Awaitable[dict[str, Any] | None]]


class Worker:
    """Single-worker event loop that drains the queue.

    A real Directo deployment runs N of these (typically N = number of
    GPU nodes). Each worker has a unique ``worker_id`` so logs and
    audit can trace who did what.
    """

    def __init__(
        self,
        queue: PersistentQueue,
        *,
        worker_id: str | None = None,
        poll_interval: float = 0.5,
        heartbeat_every: float = 30.0,
        node: str | None = None,
    ) -> None:
        self._queue = queue
        self._worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self._poll_interval = poll_interval
        self._heartbeat_every = heartbeat_every
        self._node = node
        self._handlers: dict[str, Handler] = {}
        self._stop = asyncio.Event()
        self._active_task: asyncio.Task | None = None

    # ----------------- Registration -----------------

    def register(self, kind: str, handler: Handler) -> None:
        """Register an async handler for a given job kind."""
        if not asyncio.iscoroutinefunction(handler):
            raise TypeError(f"Handler for {kind!r} must be async (defined with 'async def')")
        self._handlers[kind] = handler
        log.info(f"handler registered for kind={kind!r}")

    # ----------------- Lifecycle -----------------

    def stop(self) -> None:
        """Request the worker to stop after the current job."""
        self._stop.set()

    async def run(self) -> None:
        """Main loop. Returns when :meth:`stop` is called."""
        log.info(f"worker {self._worker_id} starting (node={self._node or 'any'})")
        while not self._stop.is_set():
            try:
                job = await asyncio.to_thread(self._queue.claim, self._worker_id, self._node)
            except Exception:
                log.exception("claim failed; backing off")
                await asyncio.sleep(self._poll_interval * 5)
                continue

            if job is None:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval)
                except TimeoutError:
                    pass
                continue

            # Spawn the handler as a task so we can honor stop().
            self._active_task = asyncio.create_task(self._execute(job))
            done, _ = await asyncio.wait(
                {self._active_task}, timeout=self._poll_interval * 0.1
            )
            if not done:
                # Job still in progress; loop again and the next iteration
                # will heartbeat.
                pass

        # Drain: wait for the current job to finish before returning.
        if self._active_task is not None and not self._active_task.done():
            log.info(f"worker {self._worker_id} draining in-flight job")
            try:
                await asyncio.wait_for(self._active_task, timeout=30.0)
            except TimeoutError:
                log.warning("in-flight job did not finish in 30s; leaving in queue")
        log.info(f"worker {self._worker_id} stopped")

    async def _execute(self, job: Job) -> None:
        """Run a single job: dispatch, heartbeat, report."""
        handler = self._handlers.get(job.kind)
        if handler is None:
            err = f"no handler registered for kind={job.kind!r}"
            log.bind(job_id=job.id).error(err)
            await asyncio.to_thread(self._queue.fail, job.id, err, requeue=False)
            return

        cid = job.correlation_id or uuid.uuid4().hex
        correlation_id_var.set(cid)
        with bind_context(job_id=job.id, kind=job.kind, correlation_id=cid, worker=self._worker_id):
            log.info(f"job started (attempt {job.retry_count + 1}/{job.max_retries + 1})")
            start = time.perf_counter()
            try:
                if job.timeout_seconds is not None:
                    result = await asyncio.wait_for(handler(job), timeout=job.timeout_seconds)
                else:
                    result = await handler(job)
                duration = time.perf_counter() - start
                await asyncio.to_thread(self._queue.complete, job.id, result)
                log.info(f"job completed in {duration:.2f}s")
            except TimeoutError:
                duration = time.perf_counter() - start
                err = f"job timed out after {job.timeout_seconds}s (ran {duration:.2f}s)"
                log.error(err)
                await asyncio.to_thread(self._queue.fail, job.id, err)
            except Exception as exc:
                duration = time.perf_counter() - start
                err = f"{type(exc).__name__}: {exc}"
                log.exception(f"job failed after {duration:.2f}s")
                await asyncio.to_thread(self._queue.fail, job.id, err)
            finally:
                correlation_id_var.set(None)
