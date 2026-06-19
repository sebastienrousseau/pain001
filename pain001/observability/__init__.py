# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Observability surface for pain001: metric events + OpenTelemetry tracing.

Two complementary mechanisms:

* :func:`emit_metric_event` and the ``register_metrics_callback`` /
  ``clear_metrics_callbacks`` / ``has_metrics_callbacks`` helpers
  implement the in-process metric-event fan-out the generator core
  has used since v0.0.40. Callbacks see :class:`MetricEvent`
  instances enriched with any active OpenTelemetry trace context.
* :func:`traced`, :func:`init_otel`, :func:`set_span_attributes`,
  :func:`is_enabled`, and :func:`reset_for_tests` (re-exported from
  :mod:`pain001.observability.otel`) implement opt-in OpenTelemetry
  distributed tracing. Off by default; flipped on with
  ``OTEL_ENABLED=true`` and ``pip install "pain001[otel]"``.

The two surfaces compose: when OTel is enabled, every
``emit_metric_event`` call attaches the active span's
``(trace_id, span_id, is_remote)`` to the event so the downstream
metrics backend can correlate metrics back to traces.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pain001.observability.otel import (
    OTEL_ENABLED_ENV,
    PAIN001_SERVICE_NAME,
    init_otel,
    is_enabled,
    reset_for_tests,
    set_span_attributes,
    traced,
)


@dataclass(frozen=True)
class MetricEvent:
    """Structured event emitted from processing steps."""

    name: str
    timestamp: float
    attributes: dict[str, Any] = field(default_factory=dict)
    trace_context: dict[str, Any] = field(default_factory=dict)


MetricsCallback = Callable[[MetricEvent], None]
_CALLBACKS: list[MetricsCallback] = []


def register_metrics_callback(fn: MetricsCallback) -> None:
    """Register a callback for structured metric events."""
    if fn not in _CALLBACKS:
        _CALLBACKS.append(fn)


def clear_metrics_callbacks() -> None:
    """Remove all registered metric callbacks."""
    _CALLBACKS.clear()


def has_metrics_callbacks() -> bool:
    """Return True when metrics emission is enabled."""
    return bool(_CALLBACKS)


def emit_metric_event(name: str, **attributes: Any) -> None:
    """Emit a structured metric event to registered callbacks."""
    if not _CALLBACKS:
        return
    event = MetricEvent(
        name=name,
        timestamp=time.time(),
        attributes=attributes,
        trace_context=_current_trace_context(),
    )
    for callback in list(_CALLBACKS):
        callback(event)


def _current_trace_context() -> dict[str, Any]:
    """Return the active OpenTelemetry trace context, or {} if unavailable."""
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]
    except ImportError:
        return {}

    span = trace.get_current_span()
    if span is None:  # pragma: no cover
        return {}  # pragma: no cover
    context = span.get_span_context()
    if context is None or not context.is_valid:
        return {}
    return {
        "trace_id": format(context.trace_id, "032x"),
        "span_id": format(context.span_id, "016x"),
        "is_remote": context.is_remote,
    }


__all__ = [
    # Metric-event API (v0.0.40+).
    "MetricEvent",
    "clear_metrics_callbacks",
    "emit_metric_event",
    "has_metrics_callbacks",
    "register_metrics_callback",
    # OpenTelemetry tracing API (v0.0.54+).
    "OTEL_ENABLED_ENV",
    "PAIN001_SERVICE_NAME",
    "init_otel",
    "is_enabled",
    "reset_for_tests",
    "set_span_attributes",
    "traced",
]
