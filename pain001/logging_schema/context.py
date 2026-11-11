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

"""Per-request ID and trace-context propagation for structured logs."""

import sys
import uuid
from contextvars import ContextVar, Token

# ContextVar rather than a module global or threading.local: the API
# serves concurrent async requests, and each task must see its own
# request id without leaking it to other in-flight requests.
_request_id_context: ContextVar[str | None] = ContextVar(
    "request_id", default=None
)

# The trace id and parent span id of an inbound W3C ``traceparent``, so
# logs join the caller's trace even when OpenTelemetry is not installed.
_inbound_trace_context: ContextVar[tuple[str, str] | None] = ContextVar(
    "inbound_trace", default=None
)

RequestContextTokens = tuple[Token[str | None], Token[tuple[str, str] | None]]
"""What :func:`bind_request_context` returns and
:func:`reset_request_context` takes."""


def generate_request_id() -> str:
    """Generate a unique request ID for request tracing.

    Returns:
        A short UUID-based request ID (format: req-<8-char-hex>).

    Example:
        >>> generate_request_id()
        'req-88f24b21'
    """
    return f"req-{uuid.uuid4().hex[:8]}"


def get_request_id() -> str:
    """Get or create request ID for current context.

    Returns:
        The request ID for the current execution context.
    """
    request_id = _request_id_context.get()
    if request_id is None:
        request_id = generate_request_id()
        _request_id_context.set(request_id)
    return request_id


def set_request_id(request_id: str) -> None:
    """Set request ID for current context (useful for API handlers).

    Args:
        request_id: The request ID to set.
    """
    _request_id_context.set(request_id)


def bind_request_context(
    request_id: str, inbound_trace: tuple[str, str] | None
) -> RequestContextTokens:
    """Bind one request's id and inbound trace context to this context.

    Args:
        request_id: The request id logs carry.
        inbound_trace: ``(trace_id, parent_span_id)`` from the caller's
            ``traceparent``, or ``None``.

    Returns:
        Tokens for :func:`reset_request_context`, so the values never
        outlive the request.
    """
    return (
        _request_id_context.set(request_id),
        _inbound_trace_context.set(inbound_trace),
    )


def reset_request_context(tokens: RequestContextTokens) -> None:
    """Restore what :func:`bind_request_context` replaced.

    Args:
        tokens: The tokens it returned.
    """
    _request_id_context.reset(tokens[0])
    _inbound_trace_context.reset(tokens[1])


def current_trace_ids() -> dict[str, str]:
    """Return the trace and span ids a log record should carry.

    The active OpenTelemetry span wins. Without one, a request that came
    with a ``traceparent`` still yields the caller's trace id, so its logs
    can be found from the caller's trace. OpenTelemetry is read only if
    something already imported it: without the module no span can be
    active, and a log call never pays for the import.

    Returns:
        ``{"trace_id", "span_id"}`` for an active span, ``{"trace_id"}``
        for an inbound trace alone, otherwise ``{}``.
    """
    trace = sys.modules.get("opentelemetry.trace")
    if trace is not None:
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            return {
                "trace_id": format(context.trace_id, "032x"),
                "span_id": format(context.span_id, "016x"),
            }
    inbound = _inbound_trace_context.get()
    return {"trace_id": inbound[0]} if inbound else {}
