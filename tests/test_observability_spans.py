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

"""The spans a traced run actually emits (issue #182, closing the gap).

The first cut of the OpenTelemetry surface traced ``process_files``
alone. The issue asks for a generate run to show at least
``pain001.generate``, ``pain001.validate`` and ``pain001.write``, for
``validate_scheme`` and the REST handlers to be spans too, and for the
SDK to be bootstrapped when the server starts. These tests pin each of
those against an in-memory exporter.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from pain001.constants import TEMPLATES_DIR
from pain001.observability import otel

_TPL = TEMPLATES_DIR / "pain.001.001.03"


@pytest.fixture
def exporter(monkeypatch: pytest.MonkeyPatch):
    """Route every span the decorators open into an in-memory exporter."""
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    monkeypatch.setenv("OTEL_ENABLED", "true")
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    tracer = provider.get_tracer("pain001-test")
    monkeypatch.setattr(otel, "init_otel", lambda *a, **kw: tracer)
    return memory


def _names(memory) -> list[str]:
    """Span names in finish order."""
    return [span.name for span in memory.get_finished_spans()]


def _span(memory, name: str):
    """The first finished span called ``name``."""
    return next(s for s in memory.get_finished_spans() if s.name == name)


# ---------------------------------------------------------------------------
# Decorator: async support and static attributes
# ---------------------------------------------------------------------------
def test_traced_wraps_coroutines_and_keeps_them_coroutines(exporter) -> None:
    """A traced ``async def`` is still a coroutine function and spans."""

    @otel.traced("pain001.test-async")
    async def handler(value: int) -> int:
        await asyncio.sleep(0)
        return value * 2

    assert asyncio.iscoroutinefunction(handler)
    assert asyncio.run(handler(21)) == 42
    assert _names(exporter) == ["pain001.test-async"]


def test_traced_coroutine_is_a_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With tracing off the async wrapper just awaits the function."""
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    otel.reset_for_tests()

    @otel.traced("pain001.test-async")
    async def handler() -> str:
        return "ok"

    assert asyncio.run(handler()) == "ok"


def test_traced_static_attributes_land_on_the_span(exporter) -> None:
    """``attributes=`` is stamped on every span the decorator opens."""

    @otel.traced("pain001.test-attrs", attributes={"http.route": "/x"})
    def handler() -> None:
        return None

    handler()
    assert _span(exporter, "pain001.test-attrs").attributes["http.route"] == (
        "/x"
    )


# ---------------------------------------------------------------------------
# Acceptance criterion: generate -> validate -> write
# ---------------------------------------------------------------------------
def test_generate_run_emits_generate_validate_and_write_spans(
    exporter, tmp_path: Path
) -> None:
    """One ``process_files`` call shows the three spans the issue names."""
    from pain001.core.core import process_files

    out = tmp_path / "out.xml"
    process_files(
        "pain.001.001.03",
        str(_TPL / "template.xml"),
        str(_TPL / "pain.001.001.03.xsd"),
        str(_TPL / "template.csv"),
        output_path=str(out),
    )
    assert out.exists()

    names = set(_names(exporter))
    assert {
        "pain001.generate",
        "pain001.render",
        "pain001.validate",
        "pain001.write",
    } <= names

    generate = _span(exporter, "pain001.generate")
    assert generate.attributes["pain001.message_type"] == "pain.001.001.03"
    assert generate.attributes["pain001.row_count"] > 0
    # The write span (render + XSD validate + file write) nests under
    # the batch span, and the XSD validation nests under the render.
    write = _span(exporter, "pain001.write")
    assert write.parent.span_id == generate.context.span_id
    validate = _span(exporter, "pain001.validate")
    render = _span(exporter, "pain001.render")
    assert validate.parent.span_id == render.context.span_id
    assert (
        render.attributes["pain001.row_count"]
        == (generate.attributes["pain001.row_count"])
    )


def test_streaming_run_has_its_own_span(exporter, tmp_path: Path) -> None:
    """``process_files_streaming`` is traced separately from the eager path."""
    from pain001.core.core import process_files_streaming

    written = process_files_streaming(
        "pain.001.001.03",
        str(_TPL / "template.xml"),
        str(_TPL / "pain.001.001.03.xsd"),
        str(_TPL / "template.csv"),
        chunk_size=1,
        output_dir=str(tmp_path),
    )
    assert written
    names = _names(exporter)
    assert "pain001.generate.streaming" in names
    # Each chunk renders and XSD-validates under the streaming span.
    assert names.count("pain001.render") == len(written)
    assert names.count("pain001.validate") >= len(written)


def test_validate_scheme_span_carries_the_scheme_spec(exporter) -> None:
    """``validate_scheme`` is a span stamped with the profiles it ran."""
    from pain001.validation import validate_scheme

    rows = [
        {
            "payment_currency": "EUR",
            "debtor_account_IBAN": "DE89370400440532013000",
            "creditor_account_IBAN": "FR1420041010050500013M02606",
            "payment_amount": "100.00",
            "requested_execution_date": "2026-09-12",
        }
    ] * 2
    validate_scheme(rows, "sepa-sct,anti-duplicate")
    span = _span(exporter, "pain001.validate.scheme")
    assert span.attributes["pain001.scheme"] == "sepa-sct,anti-duplicate"
    assert span.attributes["pain001.row_count"] == 2


# ---------------------------------------------------------------------------
# REST handlers
# ---------------------------------------------------------------------------
def test_rest_validate_handler_is_a_span_with_its_route(exporter) -> None:
    """``POST /api/v1/validate`` opens ``pain001.api.validate``."""
    from pain001.api.app import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/validate",
        json={
            "data_source": "csv",
            "file_path": "pain001/templates/pain.001.001.03/template.csv",
            "message_type": "pain.001.001.03",
            "scheme": "sepa-sct",
        },
    )
    assert response.status_code == 200
    handler = _span(exporter, "pain001.api.validate")
    assert handler.attributes["http.route"] == "/api/v1/validate"
    # The scheme check ran inside the handler's span.
    scheme = _span(exporter, "pain001.validate.scheme")
    assert scheme.parent.span_id == handler.context.span_id


def test_rest_generate_handler_nests_the_write_span(
    exporter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``POST /api/v1/generate`` opens ``pain001.api.generate`` over the write."""
    from pain001.api.app import app

    monkeypatch.chdir(Path.cwd())
    client = TestClient(app)
    response = client.post(
        "/api/v1/generate",
        json={
            "data_source": "csv",
            "file_path": "pain001/templates/pain.001.001.03/template.csv",
            "message_type": "pain.001.001.03",
            "output_dir": str(tmp_path),
        },
    )
    assert response.status_code == 200, response.text
    handler = _span(exporter, "pain001.api.generate")
    assert handler.attributes["http.route"] == "/api/v1/generate"
    assert _span(exporter, "pain001.write").parent.span_id == (
        handler.context.span_id
    )


def test_dashboard_handlers_are_spans(exporter) -> None:
    """The dashboard endpoints are traced like the path-based ones."""
    from pain001.api.app import app

    client = TestClient(app)
    csv_text = (_TPL / "template.csv").read_text(encoding="utf-8")
    body = {"filename": "p.csv", "content": csv_text}
    assert client.post("/api/v1/ui/validate", json=body).status_code == 200
    assert client.post("/api/v1/ui/generate", json=body).status_code == 200
    names = set(_names(exporter))
    assert {"pain001.api.ui.validate", "pain001.api.ui.generate"} <= names
    assert (
        _span(exporter, "pain001.api.ui.generate").attributes["http.route"]
        == "/api/v1/ui/generate"
    )


def test_job_status_and_download_handlers_are_spans(exporter) -> None:
    """Polling and download carry their parameterised routes."""
    from pain001.api.app import app

    client = TestClient(app)
    assert client.get("/api/v1/status/no-such-job").status_code == 404
    assert client.get("/api/v1/download/no-such-job").status_code == 404
    assert _span(exporter, "pain001.api.status").attributes["http.route"] == (
        "/api/v1/status/{job_id}"
    )
    assert (
        _span(exporter, "pain001.api.download").attributes["http.route"]
        == "/api/v1/download/{job_id}"
    )


# ---------------------------------------------------------------------------
# Bootstrap: once per process, at startup
# ---------------------------------------------------------------------------
def test_app_lifespan_bootstraps_the_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Starting the FastAPI app calls ``init_otel`` exactly once."""
    import importlib

    app_module = importlib.import_module("pain001.api.app")
    calls: list[str] = []
    monkeypatch.setattr(app_module, "init_otel", lambda: calls.append("init"))
    with TestClient(app_module.app) as client:
        assert client.get("/api/v1/health").status_code == 200
    assert calls == ["init"]


def test_serve_command_bootstraps_the_sdk() -> None:
    """``pain001 serve`` initialises tracing before handing off to uvicorn."""
    from pain001.cli.cli import cli

    with (
        patch("uvicorn.run") as run,
        patch("pain001.cli.cli.init_otel") as init,
    ):
        result = CliRunner().invoke(cli, ["serve", "--port", "9101"])
    assert result.exit_code == 0, result.output
    init.assert_called_once_with()
    run.assert_called_once()
