# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""OpenTelemetry tracing surface for pain001 (opt-in, zero-cost when off).

Enterprise teams running pain001 in a microservices mesh need
distributed traces across their generator + REST surface alongside
Datadog / Honeycomb / Tempo / Jaeger. This module provides a single,
env-gated tracing seam that:

* defaults to a complete no-op (zero startup or per-call overhead)
  when ``OTEL_ENABLED`` is unset or when the ``pain001[otel]`` extra
  is not installed;
* exposes one decorator (:func:`traced`) the generator and the REST
  handlers wear unconditionally - the decorator decides at call
  time whether to create a span;
* exposes one bootstrap (:func:`init_otel`) called from the CLI
  ``serve`` subcommand and from the FastAPI app's startup hook so
  the SDK is initialised once per process.

When enabled, the decorator stamps the span with rich attributes the
operator can pivot on:

* ``pain001.message_type`` - ISO 20022 message type being generated.
* ``pain001.row_count`` - number of payment rows in the batch.
* ``pain001.scheme`` - active scheme profile (``sepa-sct`` etc.).
* ``pain001.format`` - input format (``csv``, ``json``, ...).

Configuration via the OpenTelemetry SDK's own env vars
(``OTEL_EXPORTER_OTLP_ENDPOINT``, ``OTEL_SERVICE_NAME``, ...) so the
operator surface stays the one every OTel-aware tool already uses.
``OTEL_ENABLED=true`` is the master switch pain001 owns on top of
that.
"""

from __future__ import annotations

import functools
import logging
import os
import threading
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

OTEL_ENABLED_ENV = "OTEL_ENABLED"
"""Master switch operators flip to opt in to tracing."""

PAIN001_SERVICE_NAME = "pain001"
"""Default ``service.name`` resource attribute (overridable by
``OTEL_SERVICE_NAME``)."""

F = TypeVar("F", bound=Callable[..., Any])

_tracer: Any = None
"""Process-level singleton tracer; ``None`` when OTel is disabled."""

_init_lock = threading.Lock()
"""Guards :func:`init_otel` so concurrent callers initialise once."""

_init_attempted = False
"""Set after the first :func:`init_otel` call so repeats short-circuit."""


def is_enabled() -> bool:
    """Return ``True`` iff the operator has set ``OTEL_ENABLED=true``.

    A separate env-var name from OTel's own toggle so pain001 can be
    instrumented without enabling tracing for every other library in
    the same process.

    Returns:
        ``True`` when the env var is one of ``true`` / ``1`` /
        ``yes`` (case-insensitive); ``False`` otherwise.
    """
    return os.environ.get(OTEL_ENABLED_ENV, "").lower() in {
        "true",
        "1",
        "yes",
    }


def init_otel(service_name: str = PAIN001_SERVICE_NAME) -> Any:
    """Initialise the OTel SDK once per process and return the tracer.

    Idempotent: subsequent calls return the cached tracer without
    re-initialising. Safe to call when ``OTEL_ENABLED`` is unset or
    when the ``pain001[otel]`` extra is missing - both cases return
    ``None`` and tracing stays off.

    Args:
        service_name: ``service.name`` resource attribute. Defaults
            to ``"pain001"``; override when wrapping pain001 inside
            a larger service (``"acme-payments"``).

    Returns:
        The tracer object the rest of the SDK exposes (an
        ``opentelemetry.trace.Tracer``), or ``None`` when tracing
        is disabled or the SDK is not installed.
    """
    global _tracer, _init_attempted
    if _init_attempted:
        return _tracer
    with _init_lock:
        if _init_attempted:  # pragma: no cover - double-checked locking
            return _tracer
        _init_attempted = True
        if not is_enabled():
            return None
        try:
            from opentelemetry import trace  # noqa: PLC0415
            from opentelemetry.sdk.resources import Resource  # noqa: PLC0415
            from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415
            from opentelemetry.sdk.trace.export import (  # noqa: PLC0415
                BatchSpanProcessor,
            )
        except ImportError:
            logger.warning(
                "OTEL_ENABLED is set but the pain001[otel] extra is not "
                "installed; tracing stays off. Install with: "
                "pip install 'pain001[otel]'"
            )
            return None
        resource = Resource.create(
            {
                "service.name": os.environ.get(
                    "OTEL_SERVICE_NAME", service_name
                ),
            }
        )
        provider = TracerProvider(resource=resource)
        # Exporter selection follows the SDK's standard env vars
        # (OTEL_EXPORTER_OTLP_ENDPOINT etc.); when neither is set,
        # spans accumulate in the provider with no exporter and
        # silently drop on flush.
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: PLC0415, E501
                OTLPSpanExporter,
            )

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        except ImportError:  # pragma: no cover - exporter is optional
            logger.info(
                "no OTLP exporter installed; spans will not be shipped. "
                "Install opentelemetry-exporter-otlp for HTTP export."
            )
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)
        return _tracer


def reset_for_tests() -> None:
    """Drop the cached tracer + reset the init flag.

    Test-only seam. Production code never resets; the tracer lives
    for the lifetime of the process.
    """
    global _tracer, _init_attempted
    _tracer = None
    _init_attempted = False


def traced(span_name: str) -> Callable[[F], F]:
    """Decorate a function so each call becomes an OTel span when enabled.

    The decorator is *always* applied; the per-call decision is made
    by checking :func:`is_enabled` (cached after the first call). When
    tracing is off, the wrapper is a single ``if`` plus the original
    call - effectively free.

    The wrapped function may set additional span attributes via the
    ``_otel_span`` kwarg the wrapper injects; tests should not rely
    on that injection.

    Args:
        span_name: Stable, kebab-cased span name
            (``"pain001.generate"``, ``"pain001.validate"``).

    Returns:
        A decorator producing a function that creates a span on
        each call (when enabled) and propagates the original
        function's result + exceptions verbatim.
    """

    def decorator(fn: F) -> F:
        """Wrap ``fn`` so calls open a span (when enabled)."""

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Open a span if enabled, then dispatch to ``fn``."""
            tracer = init_otel()  # cheap after first call
            if tracer is None:
                return fn(*args, **kwargs)
            # The SDK's context manager auto-records the exception
            # and flips status to ERROR when an exception escapes,
            # so we can let the `raise` propagate naturally.
            with tracer.start_as_current_span(span_name):
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def set_span_attributes(**attributes: Any) -> None:
    """Stamp the *current* span with the supplied attributes.

    Helper for tracing-aware call sites that want to enrich the span
    set up by :func:`traced` without restructuring the function.
    Safe to call when tracing is disabled (no-op) and when called
    outside any span (no-op).

    Conventionally pain001 attribute names are kebab-cased and
    prefixed with ``pain001.`` (``pain001.message_type``,
    ``pain001.row_count``).

    Args:
        **attributes: Keyword arguments mapped onto span attributes.
    """
    if not is_enabled():
        return
    try:
        from opentelemetry import trace  # noqa: PLC0415
    except ImportError:  # pragma: no cover - guarded by is_enabled
        return
    span = trace.get_current_span()
    if span is None:  # pragma: no cover - SDK always returns NonRecording
        return
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)
