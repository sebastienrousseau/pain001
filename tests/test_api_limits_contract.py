# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Contract of the request-body ceiling and the oversized-upload answer.

The limit is an exact byte count: a body of exactly the limit passes,
one byte more is ``413``, whether the size is declared up front or
only discovered while the body streams in.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from pain001.api.limits import (
    BodyLimitMiddleware,
    _declared_length,
    _upload_too_large,
    install_body_limit,
    max_body_bytes,
)
from pain001.api.models import UiFilePayload


def _limited_app() -> FastAPI:
    """Build a fresh app with the body limit and one echoing route."""
    fresh = FastAPI()

    @fresh.post("/echo")
    async def echo(request: Request) -> dict[str, int]:
        """Return how many body bytes the route received."""
        return {"size": len(await request.body())}

    @fresh.post("/upload")
    async def upload(payload: UiFilePayload) -> dict[str, str]:
        """Accept a dashboard upload."""
        return {"filename": payload.filename}

    install_body_limit(fresh)
    return fresh


def _chunks(*sizes: int) -> Iterator[bytes]:
    """Yield chunks of the given sizes (a body with no Content-Length)."""
    for size in sizes:
        yield b"x" * size


def test_one_byte_is_a_valid_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """``1`` is the smallest accepted limit."""
    monkeypatch.setenv("PAIN001_MAX_BODY_BYTES", "1")
    assert max_body_bytes() == 1


def test_declared_length_reads_only_content_length() -> None:
    """Only the Content-Length header counts, and only when numeric."""
    headers = [(b"x-count", b"12"), (b"content-length", b"5")]
    assert _declared_length({"headers": headers}) == 5
    assert _declared_length({"headers": [(b"x-count", b"12")]}) is None
    assert _declared_length({}) is None


def test_declared_length_at_and_over_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A declared body of exactly the limit passes; one byte more is 413."""
    monkeypatch.setenv("PAIN001_MAX_BODY_BYTES", "10")
    client = TestClient(_limited_app())
    assert client.post("/echo", content=b"x" * 10).json() == {"size": 10}
    response = client.post("/echo", content=b"x" * 11)
    assert response.status_code == 413
    assert response.json() == {
        "detail": "Request body exceeds 10 bytes (PAIN001_MAX_BODY_BYTES)."
    }


def test_declared_overflow_never_reaches_the_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An over-long Content-Length is refused before the app runs."""
    monkeypatch.setenv("PAIN001_MAX_BODY_BYTES", "10")
    called: list[str] = []
    sent: list[dict[str, Any]] = []

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        called.append("app")

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {"type": "http", "headers": [(b"content-length", b"11")]}
    asyncio.run(BodyLimitMiddleware(inner)(scope, receive, send))
    assert called == []
    assert sent[0]["status"] == 413


def _stream(*sizes: int) -> int:
    """Send a length-less body in chunks of ``sizes``; return bytes read."""
    messages = [
        {"type": "http.request", "body": b"x" * size, "more_body": True}
        for size in sizes
    ]
    messages[-1]["more_body"] = False
    read: list[int] = []

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        while True:
            message = await receive()
            read.append(len(message["body"]))
            if not message["more_body"]:
                return

    async def receive() -> dict[str, Any]:
        return messages.pop(0)

    scope = {"type": "http", "headers": []}
    asyncio.run(BodyLimitMiddleware(inner)(scope, receive, None))
    return sum(read)


def test_streamed_chunks_add_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chunks are summed; the chunk that passes the limit raises 413."""
    from starlette.exceptions import HTTPException

    monkeypatch.setenv("PAIN001_MAX_BODY_BYTES", "10")
    assert _stream(10) == 10
    assert _stream(4, 6) == 10
    with pytest.raises(HTTPException) as info:
        _stream(6, 6)
    assert info.value.status_code == 413
    assert info.value.detail == (
        "Request body exceeds 10 bytes (PAIN001_MAX_BODY_BYTES)."
    )


def test_streamed_overflow_is_a_413_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Through FastAPI, a streamed body over the limit is a 413 answer."""
    monkeypatch.setenv("PAIN001_MAX_BODY_BYTES", "10")
    client = TestClient(_limited_app())
    assert client.post("/echo", content=_chunks(10)).json() == {"size": 10}
    response = client.post("/echo", content=_chunks(6, 6))
    assert response.status_code == 413
    assert response.json() == {
        "detail": "Request body exceeds 10 bytes (PAIN001_MAX_BODY_BYTES)."
    }


def test_oversized_upload_message_is_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An upload over 10 MiB is 413 with the documented advice."""
    from pain001.api.models import MAX_UPLOAD_BYTES

    monkeypatch.delenv("PAIN001_MAX_BODY_BYTES", raising=False)
    client = TestClient(_limited_app())
    response = client.post(
        "/upload",
        json={"filename": "a.csv", "content": "x" * (MAX_UPLOAD_BYTES + 1)},
    )
    assert response.status_code == 413
    assert response.json() == {
        "detail": "File exceeds 10 MiB; use the CLI or the path-based API "
        "for batches this size."
    }


def test_validation_error_without_location_stays_422() -> None:
    """An error that names no location is FastAPI's usual 422."""
    exc = RequestValidationError([{"type": "string_too_long", "msg": "long"}])
    scope = {"type": "http", "method": "POST", "path": "/", "headers": []}
    response = asyncio.run(_upload_too_large(Request(scope), exc))
    assert response.status_code == 422
