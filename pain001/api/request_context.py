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

"""Request ids and inbound trace context for every REST request.

:class:`RequestContextMiddleware` sits outermost, so every answer (a
``413`` or ``429`` included) carries an ``X-Request-ID``: the caller's,
when it is well formed (1 to 128 characters of letters, digits and
``. _ : -``, starting with a letter or digit), otherwise a fresh one. The
id is bound to the request's context, so JSON log lines written while
serving it carry it as ``request_id``.

An inbound W3C ``traceparent`` joins the request to the caller's trace.
With tracing on (``OTEL_ENABLED`` and the ``pain001[otel]`` extra) the
middleware opens a server span whose parent is extracted with the
configured propagators (W3C trace context by default), so the handler
spans are its children; log lines carry its ``trace_id`` and
``span_id``. With tracing off, or OpenTelemetry not installed, the
header is still parsed and logs carry the caller's ``trace_id``.
"""

from __future__ import annotations

import re
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from pain001.logging_schema.context import (
    bind_request_context,
    generate_request_id,
    reset_request_context,
)
from pain001.observability.otel import init_otel

REQUEST_ID_HEADER = "x-request-id"
"""The header a request id is read from and echoed in."""

_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")

_TRACEPARENT = re.compile(
    r"([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}(-.*)?"
)

_SERVER_ERROR = 500


def accept_request_id(value: str | None) -> str:
    """Return the caller's request id when well formed, else a new one.

    A caller's id is copied into every log line, so one with spaces,
    slashes or unbounded length is refused rather than trusted.

    Args:
        value: The inbound ``X-Request-ID``, if any.

    Returns:
        The id this request is served under.
    """
    if value and _REQUEST_ID.fullmatch(value):
        return value
    return generate_request_id()


def parse_traceparent(value: str | None) -> tuple[str, str] | None:
    """Parse a W3C ``traceparent`` header.

    Args:
        value: The header, e.g.
            ``00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01``.

    Returns:
        ``(trace_id, parent_span_id)``, or ``None`` when the header is
        missing or invalid: version ``ff``, a version ``00`` header with
        trailing fields, or an all-zero id.
    """
    match = _TRACEPARENT.fullmatch((value or "").strip())
    if match is None:
        return None
    version, trace_id, parent_id, rest = match.groups()
    invalid = (
        version == "ff"
        or (version == "00" and rest is not None)
        or not trace_id.strip("0")
        or not parent_id.strip("0")
    )
    return None if invalid else (trace_id, parent_id)


def _echo_request_id(send: Send, request_id: str) -> Send:
    """Wrap ``send`` so the response start carries the request id.

    Args:
        send: The ASGI send channel.
        request_id: The id to echo.

    Returns:
        A send channel that sets ``X-Request-ID`` on the response.
    """

    async def send_with_id(message: Message) -> None:
        """Set the header on ``http.response.start``, then send."""
        if message["type"] == "http.response.start":
            message.setdefault("headers", [])
            MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
        await send(message)

    return send_with_id


def route_template(scope: Scope) -> str | None:
    """Return the matched route's template, with any router prefix.

    A route on an included router knows only its own path
    (``/status/{job_id}``); the prefix it was mounted under is recovered
    from the request path, so the span names ``/api/v1/status/{job_id}``
    and the legacy ``/api`` alias stays apart.

    Args:
        scope: The ASGI scope after routing.

    Returns:
        The full template, or ``None`` when no route matched.
    """
    template = str(getattr(scope.get("route"), "path_format", "") or "")
    if not template:
        return None
    rendered = template
    for name, value in scope.get("path_params", {}).items():
        rendered = rendered.replace(f"{{{name}}}", str(value))
    path = str(scope["path"])
    prefix = path[: -len(rendered)] if path.endswith(rendered) else ""
    return prefix + template


async def _serve_traced(
    tracer: Any,
    app: ASGIApp,
    scope: Scope,
    receive: Receive,
    send: Send,
    request_id: str,
) -> None:
    """Serve a request inside a server span parented on ``traceparent``.

    Args:
        tracer: The OpenTelemetry tracer.
        app: The wrapped application.
        scope: The ASGI connection scope.
        receive: The ASGI receive channel.
        send: The ASGI send channel.
        request_id: The id the request is served under.
    """
    from opentelemetry import propagate, trace  # noqa: PLC0415

    headers = Headers(scope=scope)
    method = scope["method"]
    with tracer.start_as_current_span(
        method,
        context=propagate.extract(dict(headers.items())),
        kind=trace.SpanKind.SERVER,
        attributes={
            "http.request.method": method,
            "url.path": scope["path"],
            "pain001.request_id": request_id,
        },
    ) as span:

        async def send_traced(message: Message) -> None:
            """Record the status code on the span, then send."""
            if message["type"] == "http.response.start":
                status = message["status"]
                span.set_attribute("http.response.status_code", status)
                if status >= _SERVER_ERROR:
                    span.set_status(trace.StatusCode.ERROR)
            await send(message)

        await app(scope, receive, send_traced)
        route = route_template(scope)
        if route:
            span.update_name(f"{method} {route}")
            span.set_attribute("http.route", route)


class RequestContextMiddleware:
    """Bind a request id and the inbound trace context to each request.

    Args:
        app: The wrapped ASGI application.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Serve one connection, binding its context for HTTP.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        request_id = accept_request_id(headers.get(REQUEST_ID_HEADER))
        tokens = bind_request_context(
            request_id, parse_traceparent(headers.get("traceparent"))
        )
        send = _echo_request_id(send, request_id)
        try:
            tracer = init_otel()
            if tracer is None:
                await self.app(scope, receive, send)
            else:
                await _serve_traced(
                    tracer, self.app, scope, receive, send, request_id
                )
        finally:
            reset_request_context(tokens)
