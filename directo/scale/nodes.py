"""ComfyUI node registry and orchestrator.

A ComfyUI **node** in this context is a remote ComfyUI server (typically
one per GPU box). Directo discovers, health-checks, and routes jobs to
the right node based on:

- **VRAM budget** (handled by :mod:`directo.scale.vram`).
- **Tags** (e.g. ``flux``, ``sdxl``, ``video``).
- **Current load** (queue depth, last job duration).
- **Affinity** (route the same model to the same node to keep it warm).

This module is the runtime side. The **queue** integration lives in
:mod:`directo.queue` — every ComfyUI job is a regular :class:`Job`
with ``node=<node_id>`` and the Worker filters by node.

Health checks are non-blocking (async). Failures are recorded but never
crash the orchestrator.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from directo.observability import get_logger

log = get_logger("directo.scale.nodes")


@dataclass
class NodeHealth:
    """Snapshot of a node's health at a point in time."""

    node_id: str
    reachable: bool
    latency_ms: float | None = None
    queue_depth: int = 0
    queue_running: int = 0
    vram_total_mb: int | None = None
    vram_free_mb: int | None = None
    error: str | None = None
    last_check: float = field(default_factory=time.time)


@dataclass
class ComfyUINode:
    """A single ComfyUI server in the orchestrator's fleet.

    :param node_id: unique name within the orchestrator
    :param url: base URL, e.g. ``http://10.0.0.5:8188``
    :param tags: free-form tags used for routing (e.g. ``["flux", "video"]``)
    """

    node_id: str
    url: str
    tags: list[str] = field(default_factory=list)
    health: NodeHealth | None = None
    enabled: bool = True
    consecutive_failures: int = 0

    async def ping(self, timeout: float = 5.0) -> NodeHealth:
        """Probe the node and update ``self.health``.

        The ComfyUI ``/system_stats`` endpoint reports VRAM; we use it
        to populate the snapshot. ``/queue`` reports queue depth.
        """
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # ComfyUI exposes multiple endpoints; try the lightweight ones first.
                stats_url = f"{self.url.rstrip('/')}/system_stats"
                resp = await client.get(stats_url)
                latency = (time.perf_counter() - start) * 1000
                if resp.status_code != 200:
                    raise RuntimeError(f"status {resp.status_code}")
                stats = resp.json()

                queue_url = f"{self.url.rstrip('/')}/queue"
                qresp = await client.get(queue_url)
                qdata = qresp.json() if qresp.status_code == 200 else {"queue_running": [], "queue_pending": []}

                # Try to extract VRAM. ComfyUI's system_stats has varying shapes
                # across versions; we look for the most common field paths.
                vram_total, vram_free = _extract_vram(stats)

                self.health = NodeHealth(
                    node_id=self.node_id,
                    reachable=True,
                    latency_ms=latency,
                    queue_depth=len(qdata.get("queue_pending", [])),
                    queue_running=len(qdata.get("queue_running", [])),
                    vram_total_mb=vram_total,
                    vram_free_mb=vram_free,
                )
                self.consecutive_failures = 0
                log.bind(node=self.node_id).info(
                    f"node healthy: latency={latency:.0f}ms queue={self.health.queue_depth}"
                )
        except Exception as exc:  # noqa: BLE001
            self.consecutive_failures += 1
            self.health = NodeHealth(
                node_id=self.node_id, reachable=False, error=str(exc)
            )
            log.bind(node=self.node_id).warning(f"node unreachable: {exc}")
        return self.health

    def can_handle(self, requirements: dict[str, Any]) -> tuple[bool, str | None]:
        """Decide if this node can run a job with the given requirements.

        ``requirements`` is a dict like::

            {"tags": ["flux"], "vram_mb": 12000}

        Returns ``(ok, reason)``. ``reason`` is ``None`` if ``ok`` else
        a human-readable explanation.
        """
        if not self.enabled:
            return False, "node disabled"
        if self.health is None:
            return True, None  # no info; let it through
        if not self.health.reachable:
            return False, f"node unreachable ({self.health.error})"
        # Tag check (all required tags must be present)
        required_tags = set(requirements.get("tags", []))
        if required_tags and not required_tags.issubset(set(self.tags)):
            return False, f"missing tags: {required_tags - set(self.tags)}"
        # VRAM check
        req_vram = requirements.get("vram_mb")
        if req_vram and self.health.vram_free_mb is not None:
            if self.health.vram_free_mb < req_vram:
                return False, f"insufficient VRAM: need {req_vram}MB, have {self.health.vram_free_mb}MB"
        return True, None


def _extract_vram(stats: dict[str, Any]) -> tuple[int | None, int | None]:
    """Try common field paths for VRAM in ComfyUI's system_stats response."""
    # Newer ComfyUI: "devices" array
    devices = stats.get("devices")
    if isinstance(devices, list) and devices:
        d = devices[0]
        total = d.get("vram_total") or d.get("total_vram")
        free = d.get("vram_free") or d.get("free_vram")
        return int(total) if total else None, int(free) if free else None
    # Older format: direct fields
    total = stats.get("vram_total")
    free = stats.get("vram_free")
    if total or free:
        return int(total) if total else None, int(free) if free else None
    return None, None


class NodeRegistry:
    """In-memory registry of all known ComfyUI nodes.

    The orchestrator (typically a single Directo process) maintains one
    registry. Workers query the registry via :meth:`pick` to choose
    where to route each job.

    For persistence (across restarts), use :meth:`to_json` /
    :meth:`from_json` to serialize.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, ComfyUINode] = {}
        self._lock = asyncio.Lock()

    def add(self, node: ComfyUINode) -> None:
        self._nodes[node.node_id] = node
        log.bind(node=node.node_id).info(f"node registered: {node.url} tags={node.tags}")

    def remove(self, node_id: str) -> bool:
        return self._nodes.pop(node_id, None) is not None

    def get(self, node_id: str) -> ComfyUINode | None:
        return self._nodes.get(node_id)

    def all(self) -> list[ComfyUINode]:
        return list(self._nodes.values())

    def to_json(self) -> list[dict[str, Any]]:
        return [
            {"node_id": n.node_id, "url": n.url, "tags": n.tags, "enabled": n.enabled}
            for n in self._nodes.values()
        ]

    @classmethod
    def from_json(cls, data: list[dict[str, Any]]) -> "NodeRegistry":
        reg = cls()
        for d in data:
            reg.add(ComfyUINode(
                node_id=d["node_id"], url=d["url"],
                tags=list(d.get("tags", [])), enabled=d.get("enabled", True),
            ))
        return reg

    # ----------------- Routing -----------------

    def pick(
        self,
        requirements: dict[str, Any] | None = None,
        *,
        prefer_node: str | None = None,
    ) -> ComfyUINode | None:
        """Choose the best node for a job.

        Selection logic:
        1. If ``prefer_node`` is given and healthy, use it (warm affinity).
        2. Otherwise, filter to nodes that pass :meth:`can_handle`.
        3. Among those, pick the one with the lowest (queue_depth + 1) *
           (1 + latency_penalty). Falls back to round-robin on ties.

        Returns ``None`` if no node can handle the job.
        """
        requirements = requirements or {}
        # 1. warm affinity
        if prefer_node and prefer_node in self._nodes:
            n = self._nodes[prefer_node]
            ok, _ = n.can_handle(requirements)
            if ok:
                return n

        # 2. filter
        candidates: list[ComfyUINode] = []
        for n in self._nodes.values():
            ok, _ = n.can_handle(requirements)
            if ok:
                candidates.append(n)

        if not candidates:
            return None

        # 3. score
        def score(n: ComfyUINode) -> float:
            h = n.health
            if h is None:
                return 0.0  # unprobed = assume best
            latency = (h.latency_ms or 50) / 100.0  # 50ms baseline
            depth = (h.queue_depth + h.queue_running) + 1
            return depth * (1.0 + latency / 10.0)

        return min(candidates, key=score)

    # ----------------- Health -----------------

    async def check_all(self, timeout: float = 5.0) -> list[NodeHealth]:
        """Probe every node concurrently and return the snapshots."""
        results = await asyncio.gather(
            *[n.ping(timeout=timeout) for n in self._nodes.values()],
            return_exceptions=True,
        )
        out: list[NodeHealth] = []
        for n, r in zip(self._nodes.values(), results):
            if isinstance(r, Exception):
                out.append(NodeHealth(node_id=n.node_id, reachable=False, error=str(r)))
            else:
                out.append(r)  # type: ignore[arg-type]
        return out

    def disable(self, node_id: str) -> None:
        if n := self._nodes.get(node_id):
            n.enabled = False
            log.bind(node=node_id).warning("node disabled")

    def enable(self, node_id: str) -> None:
        if n := self._nodes.get(node_id):
            n.enabled = True
            log.bind(node=node_id).info("node enabled")
