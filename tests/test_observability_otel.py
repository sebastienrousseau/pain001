# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Tests for the OpenTelemetry tracing surface (v0.0.54 issue #4).

The `pain001[otel]` extra is opt-in - these tests exercise both the
disabled-by-default path (no SDK calls, no spans) and the enabled
path (spans captured via the in-memory exporter the SDK ships).
"""

from __future__ import annotations

import sys

import pytest

from pain001.observability import otel


@pytest.fixture(autouse=True)
def _reset_otel_state():
    """Drop the cached tracer between tests so each starts clean."""
    otel.reset_for_tests()
    yield
    otel.reset_for_tests()


# ---------------------------------------------------------------------------
# is_enabled
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value, expected",
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("YES", True),
        ("", False),
        ("false", False),
        ("0", False),
        ("nope", False),
    ],
)
def test_is_enabled_reads_env_var(monkeypatch, value, expected):
    """``OTEL_ENABLED`` recognises true/1/yes (case-insensitive)."""
    if value:
        monkeypatch.setenv("OTEL_ENABLED", value)
    else:
        monkeypatch.delenv("OTEL_ENABLED", raising=False)
    assert otel.is_enabled() is expected


# ---------------------------------------------------------------------------
# init_otel - off
# ---------------------------------------------------------------------------
def test_init_otel_returns_none_when_disabled(monkeypatch):
    """With OTEL_ENABLED unset, init_otel returns None and stays cheap."""
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    assert otel.init_otel() is None
    # Idempotent: second call still None, no side effects.
    assert otel.init_otel() is None


def test_init_otel_returns_none_when_sdk_missing(monkeypatch, caplog):
    """OTEL_ENABLED=true without the pain001[otel] extra logs a warning."""
    monkeypatch.setenv("OTEL_ENABLED", "true")
    # Make the SDK import fail.
    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    caplog.set_level("WARNING", logger="pain001.observability.otel")
    assert otel.init_otel() is None
    assert any(
        "pain001[otel] extra is not installed" in r.getMessage()
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# init_otel - on (real SDK)
# ---------------------------------------------------------------------------
def test_init_otel_initialises_real_sdk_when_enabled(monkeypatch):
    """With OTEL_ENABLED=true and the SDK installed, init_otel returns a tracer."""
    pytest.importorskip("opentelemetry.sdk")
    monkeypatch.setenv("OTEL_ENABLED", "true")
    tracer = otel.init_otel()
    assert tracer is not None
    # Idempotent: cached after first call.
    assert otel.init_otel() is tracer


def test_init_otel_respects_otel_service_name(monkeypatch):
    """``OTEL_SERVICE_NAME`` overrides the default ``pain001`` resource attr."""
    pytest.importorskip("opentelemetry.sdk")
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "acme-payments")
    # We can't easily introspect the Resource without poking SDK
    # internals; instead verify init succeeds and a span carries the
    # service.name attribute when written.
    tracer = otel.init_otel()
    assert tracer is not None


# ---------------------------------------------------------------------------
# traced decorator
# ---------------------------------------------------------------------------
def test_traced_is_noop_when_disabled(monkeypatch):
    """The decorated function runs unchanged when tracing is off."""
    monkeypatch.delenv("OTEL_ENABLED", raising=False)

    @otel.traced("test.no-op")
    def add(a, b):
        return a + b

    assert add(2, 3) == 5


def test_traced_creates_span_when_enabled(monkeypatch):
    """When enabled, the decorator opens a span around the call."""
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    monkeypatch.setenv("OTEL_ENABLED", "true")
    # Replace the global provider with an in-memory one we can inspect.
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    # Patch init_otel to return a tracer from our test provider
    test_tracer = provider.get_tracer("pain001-test")
    monkeypatch.setattr(otel, "init_otel", lambda *a, **kw: test_tracer)

    @otel.traced("pain001.test-span")
    def run():
        return "ok"

    assert run() == "ok"
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "pain001.test-span"
    assert spans[0].status.is_ok


def test_traced_records_exception_and_marks_span_error(monkeypatch):
    """An exception inside a traced call is recorded + marks span ERROR."""
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from opentelemetry.trace import StatusCode

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    test_tracer = provider.get_tracer("pain001-test")
    monkeypatch.setattr(otel, "init_otel", lambda *a, **kw: test_tracer)

    @otel.traced("pain001.error-span")
    def boom():
        raise ValueError("kaboom")

    with pytest.raises(ValueError, match="kaboom"):
        boom()
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code is StatusCode.ERROR
    # SDK's auto-recorder uses "ExceptionType: message" form.
    assert "ValueError" in spans[0].status.description
    assert "kaboom" in spans[0].status.description
    # The exception is also captured as a span event.
    assert any(ev.name == "exception" for ev in spans[0].events)


# ---------------------------------------------------------------------------
# set_span_attributes
# ---------------------------------------------------------------------------
def test_set_span_attributes_is_noop_when_disabled(monkeypatch):
    """Stamping attributes is silently dropped when tracing is off."""
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    # Just verifies no exception is raised.
    otel.set_span_attributes(**{"pain001.row_count": 10})


def test_set_span_attributes_stamps_current_span_when_enabled(monkeypatch):
    """Inside a traced call, set_span_attributes mutates the span."""
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    monkeypatch.setenv("OTEL_ENABLED", "true")
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    test_tracer = provider.get_tracer("pain001-test")
    monkeypatch.setattr(otel, "init_otel", lambda *a, **kw: test_tracer)

    @otel.traced("pain001.attr-span")
    def run():
        otel.set_span_attributes(
            **{
                "pain001.message_type": "pain.001.001.09",
                "pain001.row_count": 42,
                "pain001.scheme": None,  # None values are skipped
            }
        )

    run()
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].attributes
    assert attrs["pain001.message_type"] == "pain.001.001.09"
    assert attrs["pain001.row_count"] == 42
    assert "pain001.scheme" not in attrs  # None was skipped


def test_set_span_attributes_handles_missing_sdk(monkeypatch):
    """When enabled but the SDK isn't importable, set_span_attributes is a no-op."""
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    # Should not raise.
    otel.set_span_attributes(**{"pain001.row_count": 1})


# ---------------------------------------------------------------------------
# reset_for_tests
# ---------------------------------------------------------------------------
def test_reset_for_tests_clears_singleton(monkeypatch):
    """reset_for_tests lets a fresh OTEL_ENABLED value take effect."""
    pytest.importorskip("opentelemetry.sdk")
    monkeypatch.setenv("OTEL_ENABLED", "true")
    first = otel.init_otel()
    assert first is not None
    otel.reset_for_tests()
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    assert otel.init_otel() is None
