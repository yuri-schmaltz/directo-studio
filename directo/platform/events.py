"""Event bus and webhook delivery.

Directo's modules emit events as the user does work:

- ``job.enqueued``, ``job.started``, ``job.completed``, ``job.failed``
- ``image.added``, ``image.rated``
- ``canvas.saved``, ``canvas.panel_added``
- ``project.created``, ``decision.recorded``
- ``node.healthy``, ``node.unhealthy``
- ``cost.recorded``

The :class:`EventBus` is a simple in-process pub/sub. The
:class:`Webhook` system persists webhook subscriptions and
delivers events over HTTP to external systems (Slack, n8n, Zapier,
custom backends).

The bus is async (asyncio). The webhooks are sync (background thread)
because delivery is fire-and-forget.

All events are recorded in a persistent log so you can replay or audit.
"""

from __future__ import annotations

import asyncio
import enum
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from directo.observability import get_logger

log = get_logger("directo.platform.events")


class EventKind(str, enum.Enum):
    # Job lifecycle
    JOB_ENQUEUED = "job.enqueued"
    JOB_STARTED = "job.started"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_RETRIED = "job.retried"
    JOB_CANCELLED = "job.cancelled"
    # Image
    IMAGE_ADDED = "image.added"
    IMAGE_RATED = "image.rated"
    IMAGE_RESTORED = "image.restored"
    # Gallery
    DEDUP_HIT = "dedup.hit"
    # Canvas
    CANVAS_SAVED = "canvas.saved"
    PANEL_ADDED = "panel.added"
    # Project
    PROJECT_CREATED = "project.created"
    DECISION_RECORDED = "decision.recorded"
    # Node
    NODE_HEALTHY = "node.healthy"
    NODE_UNHEALTHY = "node.unhealthy"
    # Cost
    COST_RECORDED = "cost.recorded"
    # Custom
    CUSTOM = "custom"


@dataclass
class Event:
    kind: EventKind
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}")
    source: str = "directo"
    correlation_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Build an Event from a dict (inverse of to_dict)."""
        return cls(
            kind=EventKind(data.get("kind", "custom")),
            payload=data.get("payload", {}),
            timestamp=float(data.get("timestamp", 0.0)),
            source=str(data.get("source", "unknown")),
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d


# Async listener type
AsyncListener = Callable[[Event], Awaitable[None]]


# =====================================================================
# Event bus
# =====================================================================


class EventBus:
    """In-process pub/sub for Directo events.

    Two API styles:

    - Sync (fire-and-forget): ``bus.publish(EventKind.JOB_COMPLETED, {...})``
    - Async (awaitable): ``await bus.publish_async(event)``

    The sync path schedules the async listeners; the async path awaits
    them. Both are non-blocking from the caller's perspective unless
    the caller awaits.
    """

    def __init__(self, *, log_to_db: bool = True, db_path: str | Path = "directo_events.db") -> None:
        self._listeners: dict[EventKind, list[AsyncListener]] = {}
        self._global_listeners: list[AsyncListener] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._log_to_db = log_to_db
        if log_to_db:
            self._lock = threading.RLock()
            self._db_path = str(db_path)
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)
            self._conn.row_factory = sqlite3.Row
            self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id              TEXT PRIMARY KEY,
                    kind            TEXT NOT NULL,
                    source          TEXT NOT NULL DEFAULT 'directo',
                    payload_json    TEXT NOT NULL DEFAULT '{}',
                    correlation_id  TEXT,
                    timestamp       REAL NOT NULL DEFAULT (unixepoch('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_events_kind_ts ON events (kind, timestamp DESC);
                """
            )

    # ----------------- Subscriptions -----------------

    def subscribe(self, kind: EventKind, listener: AsyncListener) -> None:
        self._listeners.setdefault(kind, []).append(listener)
        log.info(f"listener subscribed to {kind.value}")

    def subscribe_all(self, listener: AsyncListener) -> None:
        self._global_listeners.append(listener)
        log.info("listener subscribed to ALL events")

    def unsubscribe(self, kind: EventKind, listener: AsyncListener) -> bool:
        if kind in self._listeners:
            try:
                self._listeners[kind].remove(listener)
                return True
            except ValueError:
                pass
        return False

    # ----------------- Publishing -----------------

    def publish(
        self,
        kind: EventKind,
        payload: dict[str, Any] | None = None,
        *,
        correlation_id: str | None = None,
        source: str = "directo",
    ) -> Event:
        """Publish an event synchronously. Listeners are scheduled to run async."""
        event = Event(
            kind=kind, payload=payload or {}, correlation_id=correlation_id, source=source
        )
        self._log_event(event)
        # Schedule listeners
        self._schedule_listeners(event)
        return event

    async def publish_async(
        self,
        kind: EventKind,
        payload: dict[str, Any] | None = None,
        *,
        correlation_id: str | None = None,
        source: str = "directo",
    ) -> Event:
        event = Event(
            kind=kind, payload=payload or {}, correlation_id=correlation_id, source=source
        )
        self._log_event(event)
        await self._invoke_listeners(event)
        return event

    def _schedule_listeners(self, event: Event) -> None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._invoke_listeners(event))
                return
        except RuntimeError:
            pass
        # No running loop — run in a new one
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._invoke_listeners(event))
            loop.close()
        except Exception as exc:  # noqa: BLE001
            log.warning(f"listener dispatch failed: {exc}")

    async def _invoke_listeners(self, event: Event) -> None:
        listeners = list(self._listeners.get(event.kind, [])) + list(self._global_listeners)
        for listener in listeners:
            try:
                await listener(event)
            except Exception as exc:  # noqa: BLE001
                log.warning(f"listener for {event.kind.value} raised: {exc}")

    def _log_event(self, event: Event) -> None:
        if not self._log_to_db:
            return
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO events (id, kind, source, payload_json, correlation_id, timestamp) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (event.id, event.kind.value, event.source,
                     json.dumps(event.payload, default=str),
                     event.correlation_id, event.timestamp),
                )
        except Exception as exc:  # noqa: BLE001
            log.warning(f"event log failed: {exc}")

    def history(self, kind: EventKind | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if not self._log_to_db:
            return []
        with self._lock:
            if kind:
                rows = self._conn.execute(
                    "SELECT * FROM events WHERE kind = ? ORDER BY timestamp DESC LIMIT ?",
                    (kind.value, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
                ).fetchall()
        return [{**dict(r), "payload": json.loads(r["payload_json"])} for r in rows]

    def close(self) -> None:
        if self._log_to_db:
            with self._lock:
                self._conn.close()


# =====================================================================
# Webhooks
# =====================================================================


@dataclass
class Webhook:
    id: str
    url: str
    secret: str = ""          # for HMAC signing
    kinds: set[EventKind] = field(default_factory=set)  # empty = all
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    headers: dict[str, str] = field(default_factory=dict)
    last_delivery: float | None = None
    last_status: int | None = None
    last_error: str | None = None


class WebhookManager:
    """Manages webhook subscriptions and delivers events over HTTP."""

    def __init__(
        self,
        bus: EventBus,
        db_path: str | Path = "directo_webhooks.db",
        *,
        timeout: float = 10.0,
    ) -> None:
        self._bus = bus
        self._db_path = str(db_path)
        self._timeout = timeout
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._migrate()
        # Wire the bus to deliver to webhooks
        self._bus.subscribe_all(self._deliver)

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS webhooks (
                    id              TEXT PRIMARY KEY,
                    url             TEXT NOT NULL,
                    secret          TEXT NOT NULL DEFAULT '',
                    kinds_json      TEXT NOT NULL DEFAULT '[]',
                    enabled         INTEGER NOT NULL DEFAULT 1,
                    created_at      REAL NOT NULL DEFAULT (unixepoch('now')),
                    headers_json    TEXT NOT NULL DEFAULT '{}',
                    last_delivery   REAL,
                    last_status     INTEGER,
                    last_error      TEXT
                );
                CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    webhook_id      TEXT NOT NULL,
                    event_id        TEXT NOT NULL,
                    event_kind      TEXT NOT NULL,
                    url             TEXT NOT NULL,
                    status          INTEGER,
                    error           TEXT,
                    duration_ms     REAL,
                    timestamp       REAL NOT NULL DEFAULT (unixepoch('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_deliveries_webhook
                    ON webhook_deliveries (webhook_id, timestamp DESC);
                """
            )

    def register(
        self, url: str, *, kinds: list[EventKind] | None = None,
        secret: str = "", headers: dict[str, str] | None = None,
    ) -> str:
        webhook_id = f"wh-{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO webhooks (id, url, secret, kinds_json, headers_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (webhook_id, url, secret,
                 json.dumps([k.value for k in (kinds or [])]),
                 json.dumps(headers or {})),
            )
        log.info(f"webhook registered: {url} (kinds={kinds or 'all'})")
        return webhook_id

    def list_webhooks(self) -> list[Webhook]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM webhooks").fetchall()
        return [self._row_to_webhook(r) for r in rows]

    def enable(self, webhook_id: str) -> None:
        """Re-enable a previously disabled webhook."""
        with self._lock:
            self._conn.execute(
                "UPDATE webhooks SET enabled = 1 WHERE id = ?", (webhook_id,)
            )

    def disable(self, webhook_id: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE webhooks SET enabled = 0 WHERE id = ?", (webhook_id,))

    def delete(self, webhook_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM webhooks WHERE id = ?", (webhook_id,))
            return cur.rowcount > 0

    # ----------------- Delivery -----------------

    async def _deliver(self, event: Event) -> None:
        webhooks = [w for w in self.list_webhooks()
                    if w.enabled and (not w.kinds or event.kind in w.kinds)]
        for webhook in webhooks:
            await self._deliver_one(webhook, event)

    async def _deliver_one(self, webhook: Webhook, event: Event) -> None:
        import hashlib
        import hmac
        start = time.perf_counter()
        body = json.dumps({
            "id": event.id,
            "kind": event.kind.value,
            "timestamp": event.timestamp,
            "payload": event.payload,
            "source": event.source,
            "correlation_id": event.correlation_id,
        })
        headers = {"Content-Type": "application/json"}
        headers.update(webhook.headers)
        if webhook.secret:
            sig = hmac.new(
                webhook.secret.encode(), body.encode(), hashlib.sha256
            ).hexdigest()
            headers["X-Directo-Signature"] = f"sha256={sig}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(webhook.url, content=body, headers=headers)
            self._record_delivery(webhook, event, resp.status_code, None,
                                  (time.perf_counter() - start) * 1000)
            with self._lock:
                self._conn.execute(
                    "UPDATE webhooks SET last_delivery = ?, last_status = ?, last_error = NULL "
                    "WHERE id = ?",
                    (time.time(), resp.status_code, webhook.id),
                )
        except Exception as exc:  # noqa: BLE001
            self._record_delivery(webhook, event, None, str(exc),
                                  (time.perf_counter() - start) * 1000)
            with self._lock:
                self._conn.execute(
                    "UPDATE webhooks SET last_delivery = ?, last_status = NULL, last_error = ? "
                    "WHERE id = ?",
                    (time.time(), str(exc), webhook.id),
                )

    def _record_delivery(self, webhook: Webhook, event: Event,
                          status: int | None, error: str | None, duration_ms: float) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO webhook_deliveries (webhook_id, event_id, event_kind, url, status, error, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (webhook.id, event.id, event.kind.value, webhook.url, status, error, duration_ms),
            )

    def _row_to_webhook(self, row: sqlite3.Row) -> Webhook:
        kinds_raw = json.loads(row["kinds_json"]) if row["kinds_json"] else []
        return Webhook(
            id=row["id"], url=row["url"], secret=row["secret"],
            kinds={EventKind(k) for k in kinds_raw},
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
            headers=json.loads(row["headers_json"]) if row["headers_json"] else {},
            last_delivery=row["last_delivery"],
            last_status=row["last_status"],
            last_error=row["last_error"],
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
