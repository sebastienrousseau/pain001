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

"""Keep a keyless REST API to requests addressed to loopback.

Without ``PAIN001_API_KEY`` every endpoint is open, so the server
should answer only clients that address it as the local machine
(ADR 0009). While no key is set, :class:`HostGuardMiddleware` answers
``400`` to a ``Host`` that is not loopback (``localhost`` or a loopback
IP address, any port) and ``403`` to an ``Origin`` that is not, before
routing.

``PAIN001_ALLOWED_HOSTS`` names further hosts, comma separated (``*``
accepts any). With a key set the check is off: the bearer token is
what authenticates, and a browser never adds it by itself.
"""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from pain001.security.api_access import ALLOWED_HOSTS_ENV, API_KEY_ENV

_ANY = "*"

_BAD_HOST = 400
_BAD_ORIGIN = 403

_ADVICE = (
    "this server has no PAIN001_API_KEY, so it answers only requests "
    "addressed to localhost, 127.0.0.1 or [::1]; set PAIN001_API_KEY, "
    "or name the host in PAIN001_ALLOWED_HOSTS"
)


def hostname(netloc: str) -> str | None:
    """The lower-case host in ``netloc``, without port or brackets.

    Args:
        netloc: A ``Host`` header value, or the authority of a URL.

    Returns:
        The host, or None when there is none or it does not parse.
    """
    try:
        return urlsplit(f"//{netloc}").hostname or None
    except ValueError:
        return None


def _extra_hosts() -> frozenset[str]:
    """The hosts ``PAIN001_ALLOWED_HOSTS`` adds, in ``hostname`` form."""
    names = os.environ.get(ALLOWED_HOSTS_ENV, "").split(",")
    return frozenset(
        _ANY if name.strip() == _ANY else hostname(name.strip()) or ""
        for name in names
    ) - {""}


def allowed_host(host: str | None, extra: frozenset[str]) -> bool:
    """Tell whether a keyless server may answer a request for ``host``.

    Args:
        host: The host the request names, as :func:`hostname` returns it.
        extra: The further hosts the operator allows.

    Returns:
        True for ``localhost``, a loopback IP address, or one of ``extra``.
    """
    if host is None:
        return False
    if host == "localhost" or host in extra or _ANY in extra:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _refusal(headers: Headers) -> tuple[int, str] | None:
    """The status and reason for refusing a keyless request, if any."""
    extra = _extra_hosts()
    if not allowed_host(hostname(headers.get("host", "")), extra):
        return _BAD_HOST, f"Host not allowed: {_ADVICE}."
    origin = headers.get("origin")
    if origin is not None and not allowed_host(
        hostname(origin.partition("://")[2]), extra
    ):
        return _BAD_ORIGIN, f"Origin not allowed: {_ADVICE}."
    return None


class HostGuardMiddleware:
    """Refuse non-loopback ``Host`` and ``Origin`` while no key is set."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Answer a refused request at once; pass the rest through.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """
        refusal = None
        if scope["type"] == "http" and not os.environ.get(API_KEY_ENV):
            refusal = _refusal(Headers(scope=scope))
        if refusal is None:
            await self.app(scope, receive, send)
            return
        status, detail = refusal
        response = JSONResponse({"detail": detail}, status_code=status)
        await response(scope, receive, send)


__all__ = ["HostGuardMiddleware", "allowed_host", "hostname"]
