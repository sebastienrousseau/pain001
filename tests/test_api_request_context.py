# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Request ids and inbound trace context on the REST API.

Audit finding D12: logs and traces were not joined. There was no
request-id middleware, an inbound W3C ``traceparent`` was ignored, and
JSON log records carried no trace id. A request with ``traceparent`` now
yields spans that are children of it, and every response echoes an
``X-Request-ID``.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import sys

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from pain001.api.app import app  # noqa: E402
from pain001.api.middleware import install_middleware  # noqa: E402
from pain001.api.request_context import (  # noqa: E402
    RequestContextMiddleware,
    accept_request_id,
    parse_traceparent,
    route_template,
)
from pain001.logging_schema.formatter import JSONFormatter  # noqa: E402
from pain001.observability import otel  # noqa: E402

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
PARENT_ID = "00f067aa0ba902b7"
TRACEPARENT = f"00-{TRACE_ID}-{PARENT_ID}-01"
UNKNOWN_JOB = "/api/v1/status/00000000-0000-4000-8000-000000000000"


@pytest.fixture(autouse=True)
def _no_auth_no_tracing(monkeypatch):
    """Run open, with tracing off unless a test turns it on."""
    monkeypatch.delenv("PAIN001_API_KEY", raising=False)
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    otel.reset_for_tests()
    yield
    otel.reset_for_tests()


@pytest.fixture
def exporter(monkeypatch):
    """Turn tracing on with an in-memory exporter; yield the exporter."""
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setattr(otel, "_tracer", provider.get_tracer("test"))
    monkeypatch.setattr(otel, "_init_attempted", True)
    yield memory
    provider.shutdown()


def _logging_app() -> tuple[FastAPI, io.StringIO]:
    """Build an app whose one route logs through the JSON formatter."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    log = logging.getLogger("pain001.test.request_context")
    log.handlers = [handler]
    log.setLevel(logging.INFO)
    log.propagate = False
    fresh = FastAPI()

    @fresh.get("/log")
    def write_log() -> dict[str, str]:
        """Log one plain-text line."""
        log.info("inside the request")
        return {"ok": "yes"}

    fresh.add_middleware(RequestContextMiddleware)
    return fresh, stream


# ---------------------------------------------------------------------------
# X-Request-ID
# ---------------------------------------------------------------------------
def test_response_carries_a_generated_request_id() -> None:
    """With no inbound id, the server makes one and returns it."""
    response = TestClient(app).get("/api/v1/health")
    assert re.fullmatch(r"req-[0-9a-f]{8}", response.headers["x-request-id"])


def test_well_formed_inbound_request_id_is_echoed() -> None:
    """A caller's id comes back unchanged."""
    response = TestClient(app).get(
        "/api/v1/health", headers={"X-Request-ID": "edge-7f3a.2:9_X"}
    )
    assert response.headers["x-request-id"] == "edge-7f3a.2:9_X"


@pytest.mark.parametrize("bad", ["has space", "x" * 129, "-leading", "a/b"])
def test_malformed_inbound_request_id_is_replaced(bad: str) -> None:
    """An id that could forge log lines or bloat them is not trusted."""
    response = TestClient(app).get(
        "/api/v1/health", headers={"X-Request-ID": bad}
    )
    assert response.headers["x-request-id"] != bad
    assert response.headers["x-request-id"].startswith("req-")


def test_refused_requests_carry_the_request_id(monkeypatch) -> None:
    """The id is outermost: a 429 from the limiter carries it too."""
    monkeypatch.setenv("PAIN001_RATE_LIMIT", "1/minute")
    monkeypatch.delenv("PAIN001_RATE_LIMIT_BACKEND", raising=False)
    monkeypatch.delenv("PAIN001_TRUSTED_PROXIES", raising=False)
    fresh = FastAPI()
    install_middleware(fresh)
    client = TestClient(fresh)
    client.get("/missing")
    refused = client.get("/missing", headers={"X-Request-ID": "retry-1"})
    assert refused.status_code == 429
    assert refused.headers["x-request-id"] == "retry-1"


# ---------------------------------------------------------------------------
# traceparent: the audit's acceptance test
# ---------------------------------------------------------------------------
def test_traceparent_makes_request_spans_its_children(exporter) -> None:
    """A request with ``traceparent`` yields child spans and an id echo."""
    response = TestClient(app).get(
        UNKNOWN_JOB,
        headers={"traceparent": TRACEPARENT, "X-Request-ID": "caller-1"},
    )
    assert response.status_code == 404
    assert response.headers["x-request-id"] == "caller-1"
    spans = {span.name: span for span in exporter.get_finished_spans()}
    server = spans["GET /api/v1/status/{job_id}"]
    handler = spans["pain001.api.status"]
    assert format(server.context.trace_id, "032x") == TRACE_ID
    assert format(server.parent.span_id, "016x") == PARENT_ID
    assert server.parent.is_remote
    assert handler.context.trace_id == server.context.trace_id
    assert handler.parent.span_id == server.context.span_id
    assert server.attributes["http.response.status_code"] == 404
    assert server.attributes["http.route"] == "/api/v1/status/{job_id}"
    assert server.attributes["pain001.request_id"] == "caller-1"


def test_server_span_without_traceparent_starts_a_trace(exporter) -> None:
    """No inbound context: the server span is a root."""
    TestClient(app).get("/api/v1/health")
    (server,) = [
        s for s in exporter.get_finished_spans() if s.name.startswith("GET")
    ]
    assert server.parent is None
    assert server.name == "GET /api/v1/health"


def test_server_error_marks_the_span(exporter) -> None:
    """A 5xx answer sets the span status to error; no route keeps the name."""
    from opentelemetry.trace import StatusCode

    async def broken(scope, receive, send):
        """Answer 503 without headers and without a route."""
        await send({"type": "http.response.start", "status": 503})
        await send({"type": "http.response.body", "body": b""})

    response = TestClient(RequestContextMiddleware(broken)).get("/x")
    assert response.status_code == 503
    assert response.headers["x-request-id"].startswith("req-")
    (server,) = exporter.get_finished_spans()
    assert server.name == "GET"
    assert server.status.status_code is StatusCode.ERROR


def test_tracing_on_without_the_package_still_serves(monkeypatch) -> None:
    """``OTEL_ENABLED`` without OpenTelemetry installed changes nothing."""
    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    monkeypatch.setenv("OTEL_ENABLED", "true")
    response = TestClient(app).get(
        "/api/v1/health", headers={"traceparent": TRACEPARENT}
    )
    assert response.status_code == 200
    assert response.headers["x-request-id"].startswith("req-")


def test_non_http_scopes_pass_through() -> None:
    """Lifespan and websocket scopes reach the app untouched."""
    seen = []

    async def inner(scope, receive, send):
        """Record the scope."""
        seen.append(scope["type"])

    middleware = RequestContextMiddleware(inner)
    asyncio.run(middleware({"type": "lifespan"}, None, None))
    assert seen == ["lifespan"]


# ---------------------------------------------------------------------------
# JSON logs carry the request id and the trace id
# ---------------------------------------------------------------------------
def test_json_logs_carry_request_and_inbound_trace_id() -> None:
    """With tracing off, logs still join the caller's trace."""
    fresh, stream = _logging_app()
    TestClient(fresh).get(
        "/log", headers={"X-Request-ID": "join-1", "traceparent": TRACEPARENT}
    )
    record = json.loads(stream.getvalue())
    assert record["request_id"] == "join-1"
    assert record["trace_id"] == TRACE_ID
    assert "span_id" not in record


def test_json_logs_carry_the_active_span(exporter) -> None:
    """With tracing on, logs name the request's own span."""
    fresh, stream = _logging_app()
    TestClient(fresh).get("/log", headers={"traceparent": TRACEPARENT})
    record = json.loads(stream.getvalue())
    (server,) = exporter.get_finished_spans()
    assert record["trace_id"] == TRACE_ID
    assert record["span_id"] == format(server.context.span_id, "016x")


def test_json_logs_outside_a_request_have_no_trace_id() -> None:
    """No request and no span: no trace fields."""
    record = logging.LogRecord("x", logging.INFO, "f", 1, "plain", None, None)
    data = json.loads(JSONFormatter().format(record))
    assert "trace_id" not in data
    assert data["message"] == "plain"


def test_json_formatter_wraps_a_bare_json_scalar() -> None:
    """A message that parses as a JSON number is still wrapped."""
    record = logging.LogRecord("x", logging.INFO, "f", 1, "42", None, None)
    data = json.loads(JSONFormatter().format(record))
    assert data["message"] == "42"


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def test_accept_request_id() -> None:
    """Missing ids are generated; good ones are kept."""
    assert accept_request_id("abc") == "abc"
    assert accept_request_id(None).startswith("req-")
    assert accept_request_id("").startswith("req-")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (TRACEPARENT, (TRACE_ID, PARENT_ID)),
        (f" {TRACEPARENT} ", (TRACE_ID, PARENT_ID)),
        (f"01-{TRACE_ID}-{PARENT_ID}-01-future", (TRACE_ID, PARENT_ID)),
        (None, None),
        ("", None),
        ("garbage", None),
        (f"ff-{TRACE_ID}-{PARENT_ID}-01", None),
        (f"00-{TRACE_ID}-{PARENT_ID}-01-extra", None),
        (f"00-{'0' * 32}-{PARENT_ID}-01", None),
        (f"00-{TRACE_ID}-{'0' * 16}-01", None),
        (f"00-{TRACE_ID.upper()}-{PARENT_ID}-01", None),
    ],
)
def test_parse_traceparent(value, expected) -> None:
    """Only a W3C-valid header yields a parent."""
    assert parse_traceparent(value) == expected


class _Route:
    """A stand-in for a matched route."""

    path_format = "/status/{job_id}"


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        ({"path": "/x"}, None),
        (
            {
                "path": "/api/status/7",
                "route": _Route(),
                "path_params": {"job_id": "7"},
            },
            "/api/status/{job_id}",
        ),
        (
            {"path": "/elsewhere", "route": _Route(), "path_params": {}},
            "/status/{job_id}",
        ),
    ],
)
def test_route_template(scope, expected) -> None:
    """The router prefix is recovered from the path when it can be."""
    assert route_template(scope) == expected


def test_trace_ids_without_opentelemetry_loaded(monkeypatch) -> None:
    """Never imported, OpenTelemetry is not consulted; inbound ids are."""
    from pain001.logging_schema import context

    monkeypatch.delitem(sys.modules, "opentelemetry.trace", raising=False)
    tokens = context.bind_request_context("req-1", (TRACE_ID, PARENT_ID))
    try:
        assert context.current_trace_ids() == {"trace_id": TRACE_ID}
    finally:
        context.reset_request_context(tokens)
    assert context.current_trace_ids() == {}
