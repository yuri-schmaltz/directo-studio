"""Observability module: structured logging, metrics, and tracing.

Provides three primitives that work together:

- :func:`configure_logging` — loguru-based structured JSON logging with
  correlation IDs that propagate through async tasks.
- :class:`MetricsCollector` — Prometheus-compatible metrics (counter,
  histogram, gauge) for queue depth, generation latency, etc.
- :class:`Tracer` — minimal OpenTelemetry-style tracer for span recording
  (works without opentelemetry installed; full OTEL if the package is
  available).
"""

from directo.observability.logging import (
    bind_context,
    clear_context,
    configure_logging,
    correlation_id_var,
    get_logger,
)
from directo.observability.metrics import MetricsCollector
from directo.observability.tracing import Tracer, trace

__all__ = [
    "MetricsCollector",
    "Tracer",
    "bind_context",
    "clear_context",
    "configure_logging",
    "correlation_id_var",
    "get_logger",
    "trace",
]
