"""Structured logging with correlation IDs.

Wraps loguru with:
- JSON output for machine consumption
- A ``correlation_id`` contextvar that propagates through asyncio tasks,
  so every log line in a single request/job can be correlated.
- Sensible defaults: console for dev, file for prod.
- Never logs secrets (basic redaction layer).

Usage:
    >>> from directo.observability import configure_logging, get_logger, bind_context
    >>> configure_logging(level="INFO", json=True)
    >>> log = get_logger(__name__)
    >>> with bind_context(correlation_id="abc-123", job_id=42):
    ...     log.info("generation started", model="flux-dev")
"""

from __future__ import annotations

import json
import re
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator

from loguru import logger

# Correlation ID flows through async tasks automatically via contextvars.
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Additional context (job_id, user_id, etc.) that gets injected into every log.
_context_stack: ContextVar[dict[str, Any]] = ContextVar("directo_context", default={})

# Basic redaction — extend as needed.
_REDACT_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|authorization)\s*[=:]\s*['\"]?[\w\-./+=]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI/Anthropic style
    re.compile(r"xai-[A-Za-z0-9]{20,}"),
]


def _redact(text: str) -> str:
    """Mask obvious secrets in log messages."""
    for pat in _REDACT_PATTERNS:
        text = pat.sub(lambda m: m.group(0).split("=")[0] + "=***REDACTED***" if "=" in m.group(0) else "***REDACTED***", text)
    return text


def _json_sink(message: Any) -> None:
    """Loguru sink that emits a single JSON line per record."""
    record = message.record
    payload = {
        "ts": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "message": _redact(record["message"]),
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
    }
    # Inject any extra fields bound via ``logger.bind(**kwargs)``.
    extras = {k: v for k, v in record["extra"].items() if k not in payload}
    extras = {k: _redact(v) if isinstance(v, str) else v for k, v in extras.items()}
    payload.update(extras)
    # Inject contextvar-based context.
    ctx = _context_stack.get()
    cid = correlation_id_var.get()
    if cid:
        payload.setdefault("correlation_id", cid)
    payload.update(ctx)
    sys.stderr.write(json.dumps(payload, default=str) + "\n")
    sys.stderr.flush()


def configure_logging(
    level: str = "INFO",
    *,
    json_output: bool = True,
    log_file: str | Path | None = None,
    rotation: str = "100 MB",
    retention: str = "14 days",
) -> None:
    """Configure global logging for Directo.

    :param level: log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
    :param json_output: emit JSON to stderr (recommended for production)
    :param log_file: optional path to also write rotated log files
    :param rotation: when to rotate the log file (size or time)
    :param retention: how long to keep rotated log files
    """
    # Remove default handler.
    logger.remove()

    if json_output:
        logger.add(
            _json_sink,
            level=level,
            backtrace=False,
            diagnose=False,
        )
    else:
        # Human-friendly colored output for dev.
        logger.add(
            sys.stderr,
            level=level,
            format=(
                "<green>{time:HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_file),
            level=level,
            rotation=rotation,
            retention=retention,
            compression="gz",
            serialize=True,  # always JSON in files
            enqueue=True,    # async-safe
        )


def get_logger(name: str | None = None):
    """Return a loguru logger optionally bound to a name.

    The returned object supports both ``log.info("msg")`` and
    ``log.bind(correlation_id="x").info("msg")``.
    """
    if name:
        return logger.bind(logger_name=name)
    return logger


@contextmanager
def bind_context(**kwargs: Any) -> Iterator[None]:
    """Bind contextual fields (job_id, user_id, etc.) to all log lines.

    Inside the block, every log call will include the bound fields.
    Use for request/job-scoped context.

    Example:
        >>> with bind_context(job_id=42, project="short_film"):
        ...     log.info("starting render")
    """
    token = _context_stack.set({**_context_stack.get(), **kwargs})
    try:
        yield
    finally:
        _context_stack.reset(token)


def clear_context() -> None:
    """Clear all bound context. Useful at the start of each request."""
    _context_stack.set({})
    correlation_id_var.set(None)
