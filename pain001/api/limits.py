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

"""A request-body ceiling for every REST route.

Without one, a client can send a body of any size and the server buffers
and JSON-decodes all of it before a single field is checked. The
:class:`BodyLimitMiddleware` answers ``413`` before parsing: at once when
``Content-Length`` declares too much, and as soon as the bytes received
pass the limit when the body is streamed without a length.

The limit is ``PAIN001_MAX_BODY_BYTES`` (default 21 MiB: the largest
document any route takes, 10 MiB, twice over for JSON escaping, plus
1 MiB for the rest of the request). An upload's ``content`` over the
dashboard cap is also answered ``413``, not ``422``, so the status a
client sees for a large file does not depend on how it was refused.
"""

from __future__ import annotations

import os
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from pain001.api.models import MAX_UPLOAD_BYTES

MAX_BODY_ENV = "PAIN001_MAX_BODY_BYTES"
"""Environment variable naming the largest request body, in bytes."""

DEFAULT_MAX_BODY_BYTES = 2 * MAX_UPLOAD_BYTES + 1024 * 1024
"""21 MiB: a 10 MiB document JSON-escaped at worst twice over, plus 1 MiB."""

_TOO_LARGE = 413


def max_body_bytes() -> int:
    """Return the request-body ceiling.

    Returns:
        ``PAIN001_MAX_BODY_BYTES``, or :data:`DEFAULT_MAX_BODY_BYTES`
        when it is unset or empty.

    Raises:
        ValueError: If the variable is set to anything but a positive
            integer.
    """
    raw = os.environ.get(MAX_BODY_ENV, "").strip()
    if not raw:
        return DEFAULT_MAX_BODY_BYTES
    if not raw.isdigit() or int(raw) < 1:
        raise ValueError(
            f"{MAX_BODY_ENV} must be a positive integer, got {raw!r}"
        )
    return int(raw)


def _too_large(limit: int) -> str:
    """Return the ``413`` detail for a body over ``limit`` bytes.

    Args:
        limit: The ceiling in bytes.

    Returns:
        The message, naming the limit and the variable that sets it.
    """
    return f"Request body exceeds {limit} bytes ({MAX_BODY_ENV})."


def _declared_length(scope: Scope) -> int | None:
    """Return the request's ``Content-Length``, if it sent a usable one.

    Args:
        scope: The ASGI connection scope.

    Returns:
        The declared length, or ``None`` when absent or not a number.
    """
    for name, value in scope.get("headers", []):
        if name == b"content-length" and value.isdigit():
            return int(value)
    return None


class BodyLimitMiddleware:
    """ASGI middleware refusing request bodies over :func:`max_body_bytes`.

    Args:
        app: The wrapped ASGI application.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Check the declared length, then count the body as it arrives.

        Once a streamed body passes the limit, the wrapped ``receive``
        raises a ``413`` :class:`HTTPException`; FastAPI turns it into the
        response while it reads the body.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = max_body_bytes()
        declared = _declared_length(scope)
        if declared is not None and declared > limit:
            response = JSONResponse(
                {"detail": _too_large(limit)}, status_code=_TOO_LARGE
            )
            await response(scope, receive, send)
            return
        received = 0

        async def counted() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(_TOO_LARGE, _too_large(limit))
            return message

        await self.app(scope, counted, send)


async def _upload_too_large(request: Request, exc: Exception) -> Response:
    """Answer ``413`` for an upload over the cap, else the usual ``422``.

    Args:
        request: The request that failed validation.
        exc: The :class:`RequestValidationError` FastAPI raised.

    Returns:
        A ``413`` when the only problem is a ``content`` string over
        :data:`MAX_UPLOAD_BYTES`; FastAPI's own ``422`` otherwise.
    """
    validation = cast(RequestValidationError, exc)
    errors: list[dict[str, Any]] = list(validation.errors())
    if errors and all(
        error.get("type") == "string_too_long"
        and tuple(error.get("loc", ())) == ("body", "content")
        for error in errors
    ):
        return JSONResponse(
            {
                "detail": f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}"
                " MiB; use the CLI or the path-based API for batches this "
                "size."
            },
            status_code=_TOO_LARGE,
        )
    return await request_validation_exception_handler(request, validation)


def install_body_limit(application: FastAPI) -> None:
    """Attach the body ceiling and the oversized-upload handler.

    Args:
        application: The FastAPI application to protect.
    """
    application.add_middleware(BodyLimitMiddleware)
    application.add_exception_handler(
        RequestValidationError, _upload_too_large
    )
