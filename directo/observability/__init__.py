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
    configure_logging,
    get_logger,
    bind_context,
    clear_context,
    correlation_id_var,
)
from directo.observability.metrics import MetricsCollector
from directo.observability.tracing import Tracer, trace

__all__ = [
    "configure_logging",
    "get_logger",
    "bind_context",
    "clear_context",
    "correlation_id_var",
    "MetricsCollector",
    "Tracer",
    "trace",
]
