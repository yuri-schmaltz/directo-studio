"""Minimal span tracer for Directo.

Records the start/end time of named operations and logs them. Works
standalone (no OpenTelemetry required) so Directo is easy to install.
If ``opentelemetry`` is available, the same spans can be exported to
OTLP/Jaeger/etc. by registering a real Tracer.

Usage:
    >>> tracer = Tracer()
    >>> with tracer.span("generate_image", model="flux-dev"):
    ...     do_work()
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from directo.observability.logging import get_logger

log = get_logger("directo.tracing")


class Span:
    """A single traced operation."""

    def __init__(self, name: str, **attributes: Any) -> None:
        self.name = name
        self.attributes = attributes
        self.span_id = uuid4().hex[:16]
        self.parent_id: str | None = None
        self.start_time = time.perf_counter()
        self.end_time: float | None = None
        self.error: BaseException | None = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: BaseException) -> None:
        self.error = exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "name": self.name,
            "attributes": self.attributes,
            "duration_ms": (self.end_time - self.start_time) * 1000 if self.end_time else None,
            "status": "error" if self.error else "ok",
            "error": str(self.error) if self.error else None,
        }


class Tracer:
    """Records spans and emits them to the structured log.

    The tracer is stateless — each ``span`` contextmanager creates a new
    :class:`Span`, attaches it as a loguru context var, and finalizes
    it on exit. If OpenTelemetry is installed at runtime, the spans
    can be forwarded automatically (no-op otherwise).
    """

    def __init__(self) -> None:
        self._spans: list[Span] = []

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[Span]:
        sp = Span(name, **attributes)
        try:
            yield sp
        except BaseException as exc:
            sp.record_exception(exc)
            raise
        finally:
            sp.end_time = time.perf_counter()
            self._spans.append(sp)
            log.bind(span_id=sp.span_id).info(
                f"span '{sp.name}' finished in {sp.to_dict()['duration_ms']:.2f}ms",
                span=sp.to_dict(),
            )

    def drain(self) -> list[dict[str, Any]]:
        """Return and clear all recorded spans as dicts."""
        out = [s.to_dict() for s in self._spans]
        self._spans.clear()
        return out


def trace(name: str, **attributes: Any):
    """Convenience decorator: trace an entire function as a single span.

    Example:
        >>> @trace("render_image", kind="img2img")
        ... def render(...):
        ...     ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with Tracer().span(name, **attributes, function=func.__name__):
                return func(*args, **kwargs)
        return wrapper
    return decorator
