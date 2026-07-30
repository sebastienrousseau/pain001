# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

import sys
import types

from pain001.observability import (
    clear_metrics_callbacks,
    emit_metric_event,
    has_metrics_callbacks,
    register_metrics_callback,
)


def test_metrics_callback_receives_structured_event() -> None:
    captured = []

    def callback(event) -> None:
        captured.append(event)

    clear_metrics_callbacks()
    register_metrics_callback(callback)
    emit_metric_event("file_loaded", record_count=3, file_size_bytes=100)
    clear_metrics_callbacks()

    assert len(captured) == 1
    assert captured[0].name == "file_loaded"
    assert captured[0].attributes["record_count"] == 3


def test_register_metrics_callback_deduplicates() -> None:
    captured = []

    def callback(event) -> None:
        captured.append(event)

    clear_metrics_callbacks()
    assert has_metrics_callbacks() is False
    register_metrics_callback(callback)
    register_metrics_callback(callback)
    assert has_metrics_callbacks() is True
    emit_metric_event("dedupe_check")
    clear_metrics_callbacks()

    assert len(captured) == 1


def test_emit_metric_event_without_callbacks_is_noop() -> None:
    clear_metrics_callbacks()
    emit_metric_event("ignored")


def test_trace_context_attached_from_opentelemetry(monkeypatch) -> None:
    span_context = types.SimpleNamespace(
        trace_id=1, span_id=2, is_remote=False, is_valid=True
    )
    span = types.SimpleNamespace(get_span_context=lambda: span_context)
    fake_otel = types.ModuleType("opentelemetry")
    fake_otel.trace = types.SimpleNamespace(get_current_span=lambda: span)
    monkeypatch.setitem(sys.modules, "opentelemetry", fake_otel)

    captured = []
    clear_metrics_callbacks()
    register_metrics_callback(captured.append)
    emit_metric_event("traced")
    clear_metrics_callbacks()

    assert captured[0].trace_context["trace_id"] == format(1, "032x")
    assert captured[0].trace_context["span_id"] == format(2, "016x")


def test_trace_context_empty_for_invalid_span(monkeypatch) -> None:
    span_context = types.SimpleNamespace(
        trace_id=1, span_id=2, is_remote=False, is_valid=False
    )
    span = types.SimpleNamespace(get_span_context=lambda: span_context)
    fake_otel = types.ModuleType("opentelemetry")
    fake_otel.trace = types.SimpleNamespace(get_current_span=lambda: span)
    monkeypatch.setitem(sys.modules, "opentelemetry", fake_otel)

    captured = []
    clear_metrics_callbacks()
    register_metrics_callback(captured.append)
    emit_metric_event("untraced")
    clear_metrics_callbacks()

    assert captured[0].trace_context == {}
