"""Tests for the observability module."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from directo.observability import (
    MetricsCollector,
    Tracer,
    bind_context,
    configure_logging,
    correlation_id_var,
    get_logger,
)


def test_get_logger_returns_loguru():
    log = get_logger("test.module")
    assert log is not None


def test_configure_logging_json_emits_valid_json(capsys):
    configure_logging(level="INFO", json_output=True)
    log = get_logger("test")
    log.info("hello world", foo="bar")
    captured = capsys.readouterr()
    line = captured.err.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["message"] == "hello world"
    assert payload["foo"] == "bar"
    assert payload["level"] == "INFO"


def test_correlation_id_propagates_through_bind_context(capsys):
    configure_logging(level="INFO", json_output=True)
    correlation_id_var.set("abc-123")
    with bind_context(job_id=42, user="alice"):
        log = get_logger("test")
        log.info("doing thing")
    line = capsys.readouterr().err.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["correlation_id"] == "abc-123"
    assert payload["job_id"] == 42
    assert payload["user"] == "alice"
    correlation_id_var.set(None)


def test_metrics_collector_singleton():
    m1 = MetricsCollector()
    m2 = MetricsCollector()
    assert m1 is m2
    m1.record_job_completed("test.kind", duration=1.23, node="node-a")
    body, content_type = m1.render()
    assert content_type.startswith("text/plain")
    assert b"directo_jobs_total" in body
    assert b'test.kind' in body


def test_metrics_independent_per_registry():
    from prometheus_client import CollectorRegistry
    r1 = CollectorRegistry()
    r2 = CollectorRegistry()
    m1 = MetricsCollector(r1)
    m2 = MetricsCollector(r2)
    assert m1 is not m2
    # Both should be functional independently.


def test_tracer_span_records_duration():
    tracer = Tracer()
    with tracer.span("op", kind="test") as sp:
        x = sum(range(100))
    spans = tracer.drain()
    assert len(spans) == 1
    assert spans[0]["name"] == "op"
    assert spans[0]["attributes"]["kind"] == "test"
    assert spans[0]["duration_ms"] is not None
    assert spans[0]["status"] == "ok"


def test_tracer_records_exception():
    tracer = Tracer()
    with pytest.raises(RuntimeError):
        with tracer.span("op.fail"):
            raise RuntimeError("boom")
    spans = tracer.drain()
    assert spans[0]["status"] == "error"
    assert "boom" in spans[0]["error"]


def test_log_redacts_api_keys(capsys):
    configure_logging(level="INFO", json_output=True)
    log = get_logger("test")
    log.info("calling openai with api_key=sk-abcdefghijklmnopqrstuvwxyz123456")
    line = capsys.readouterr().err.strip().splitlines()[-1]
    assert "REDACTED" in line
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in line
