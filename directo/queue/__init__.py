"""Persistent job queue with crash recovery.

Provides:
- :class:`Job` and :class:`JobState` — the data model
- :class:`PersistentQueue` — SQLite-backed FIFO queue with priorities,
  retries, exponential backoff, and a dead-letter queue (DLQ)
- :class:`Worker` — an async worker that pulls jobs and runs them

The queue is the heart of the Directo orchestrator. Every generation
job, every LLM prompt enhancement, every export to PDF flows through
this queue. By persisting it in SQLite, a crash or restart loses no
in-flight work, and stuck jobs are automatically reaped.
"""

from directo.queue.job import Job, JobState
from directo.queue.persistent_queue import PersistentQueue
from directo.queue.worker import Worker

__all__ = ["Job", "JobState", "PersistentQueue", "Worker"]
