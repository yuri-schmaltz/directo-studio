"""Job data model and state machine."""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


class JobState(str, enum.Enum):
    """Lifecycle states of a job in the queue."""

    PENDING = "pending"      # waiting to be picked up
    RUNNING = "running"      # currently being executed
    COMPLETED = "completed"  # finished successfully
    FAILED = "failed"        # failed permanently (in DLQ)
    RETRYING = "retrying"    # temporarily failed, scheduled for retry
    CANCELLED = "cancelled"  # cancelled by user, never re-run

    @property
    def is_terminal(self) -> bool:
        return self in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED)


@dataclass
class Job:
    """A unit of work to be executed by a :class:`Worker`.

    :param kind: short label like ``"image.generate"`` — workers dispatch on this
    :param payload: opaque dict passed to the worker handler
    :param priority: lower = sooner. Defaults to 100.
    :param max_retries: max retry attempts before going to DLQ
    :param timeout_seconds: per-attempt timeout; ``None`` = no timeout
    :param node: target ComfyUI node id (or ``"default"``); used for routing
    """

    kind: str
    payload: dict[str, Any] = field(default_factory=dict)

    # identity & routing
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    correlation_id: str | None = None
    project: str | None = None
    user: str | None = None
    node: str = "default"

    # scheduling
    priority: int = 100
    scheduled_at: float | None = None  # epoch seconds; None = immediate

    # retry policy
    max_retries: int = 3
    retry_count: int = 0
    last_error: str | None = None
    backoff_seconds: float = 2.0  # base for exponential backoff

    # runtime
    timeout_seconds: float | None = None

    # metadata
    state: JobState = JobState.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict, encoding enums as strings."""
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        """Deserialize from a dict (state string → enum)."""
        d = dict(data)
        d["state"] = JobState(d["state"])
        # Backwards compat — fields that may not exist in older rows.
        d.setdefault("payload", {})
        d.setdefault("priority", 100)
        d.setdefault("retry_count", 0)
        d.setdefault("max_retries", 3)
        d.setdefault("backoff_seconds", 2.0)
        d.setdefault("node", "default")
        return cls(**d)

    def next_retry_at(self) -> float:
        """Return the epoch time at which this job should be retried."""
        return time.time() + self.backoff_seconds * (2 ** self.retry_count)
