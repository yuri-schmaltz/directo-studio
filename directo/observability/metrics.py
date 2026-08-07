"""Prometheus-compatible metrics collector.

Thin wrapper around ``prometheus_client`` that pre-registers the metrics
the Directo app actually uses. Safe to import multiple times — duplicate
registration is handled gracefully.

Key metrics:
- ``directo_jobs_total`` (counter) — total jobs by state and kind
- ``directo_job_duration_seconds`` (histogram) — job execution time
- ``directo_queue_depth`` (gauge) — current queue size
- ``directo_gpu_utilization`` (gauge) — last observed GPU util
- ``directo_model_load_seconds`` (histogram) — model load latency
- ``directo_api_requests_total`` (counter) — by endpoint and status
"""

from __future__ import annotations

import threading
from typing import Self

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


class MetricsCollector:
    """Thread-safe metrics facade.

    All Directo modules should use this single instance to keep metric
    names consistent. The instance can be configured to use a custom
    registry (useful for tests).
    """

    _instances: dict[int, MetricsCollector] = {}
    _lock = threading.Lock()

    def __new__(cls, registry: CollectorRegistry | None = None) -> Self:
        # Singleton-per-registry pattern.
        reg_id = id(registry) if registry is not None else -1
        with cls._lock:
            if reg_id in cls._instances:
                return cls._instances[reg_id]
            instance = super().__new__(cls)
            instance._init(registry)
            cls._instances[reg_id] = instance
            return instance

    def _init(self, registry: CollectorRegistry | None) -> None:
        self._registry = registry or CollectorRegistry()

        # Jobs
        self.jobs_total = Counter(
            "directo_jobs_total",
            "Total number of jobs processed.",
            labelnames=("kind", "state"),  # state: pending|running|completed|failed|dlq
            registry=self._registry,
        )
        self.job_duration = Histogram(
            "directo_job_duration_seconds",
            "Job execution duration in seconds.",
            labelnames=("kind", "node"),
            buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1800, 3600),
            registry=self._registry,
        )

        # Queue
        self.queue_depth = Gauge(
            "directo_queue_depth",
            "Current number of jobs in the queue.",
            labelnames=("state",),
            registry=self._registry,
        )

        # GPU
        self.gpu_utilization = Gauge(
            "directo_gpu_utilization",
            "Last observed GPU utilization in percent.",
            labelnames=("device",),
            registry=self._registry,
        )
        self.gpu_memory_used = Gauge(
            "directo_gpu_memory_used_bytes",
            "Last observed GPU memory used in bytes.",
            labelnames=("device",),
            registry=self._registry,
        )

        # Models
        self.model_load_seconds = Histogram(
            "directo_model_load_seconds",
            "Time taken to load a model into VRAM.",
            labelnames=("model", "device"),
            buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300),
            registry=self._registry,
        )

        # API
        self.api_requests_total = Counter(
            "directo_api_requests_total",
            "Total API requests served.",
            labelnames=("endpoint", "status"),
            registry=self._registry,
        )

        # Gallery
        self.gallery_images_total = Gauge(
            "directo_gallery_images_total",
            "Number of images in the gallery.",
            registry=self._registry,
        )
        self.gallery_dedup_hits = Counter(
            "directo_gallery_dedup_hits_total",
            "Number of times duplicate detection flagged an image.",
            registry=self._registry,
        )

    # ----------------- Convenience methods -----------------

    def record_job_completed(self, kind: str, duration: float, node: str = "default") -> None:
        self.jobs_total.labels(kind=kind, state="completed").inc()
        self.job_duration.labels(kind=kind, node=node).observe(duration)

    def record_job_failed(self, kind: str) -> None:
        self.jobs_total.labels(kind=kind, state="failed").inc()

    def set_queue_depth(self, state: str, depth: int) -> None:
        self.queue_depth.labels(state=state).set(depth)

    def observe_gpu(self, device: str, util_pct: float, mem_used_bytes: int) -> None:
        self.gpu_utilization.labels(device=device).set(util_pct)
        self.gpu_memory_used.labels(device=device).set(mem_used_bytes)

    def observe_model_load(self, model: str, device: str, seconds: float) -> None:
        self.model_load_seconds.labels(model=model, device=device).observe(seconds)

    def render(self) -> tuple[bytes, str]:
        """Render the registry as Prometheus text format.

        Returned as ``(body, content_type)`` — drop into a FastAPI endpoint
        via ``Response(content=body, media_type=content_type)``.
        """
        return generate_latest(self._registry), CONTENT_TYPE_LATEST

    def get_registry(self) -> CollectorRegistry:
        return self._registry
