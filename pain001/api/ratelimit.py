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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""In-process, dependency-free rate limiting for the Pain001 REST API.

A small fixed-window limiter keyed by client IP, configured entirely
through the ``PAIN001_RATE_LIMIT`` environment variable (e.g. ``100/minute``
or ``20/second``). When the variable is unset the middleware is a no-op, so
local development is unaffected.

This is deliberately a single-process limiter — sufficient for one API
node and for protecting against accidental floods. Horizontally-scaled
deployments should enforce limits at the gateway or with a shared store
(e.g. Redis); see the API documentation.
"""

import time
from collections import defaultdict, deque
from collections.abc import Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

_WINDOW_SECONDS = {
    "second": 1.0,
    "minute": 60.0,
    "hour": 3600.0,
    "day": 86400.0,
}


def parse_rate_limit(spec: str) -> tuple[int, float]:
    """Parse a ``<count>/<window>`` rate-limit specification.

    Args:
        spec: A specification such as ``100/minute`` or ``5/second``.

    Returns:
        A ``(max_requests, window_seconds)`` tuple.

    Raises:
        ValueError: If the specification is malformed or the window is
            not one of second/minute/hour/day.
    """
    try:
        count_str, _, window = spec.strip().partition("/")
        max_requests = int(count_str)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid rate limit: {spec!r}") from exc
    window = window.strip().lower().rstrip("s") or "minute"
    if max_requests <= 0 or window not in _WINDOW_SECONDS:
        raise ValueError(f"Invalid rate limit: {spec!r}")
    return max_requests, _WINDOW_SECONDS[window]


class RateLimitMiddleware:
    """ASGI middleware enforcing a fixed-window per-client request cap.

    Args:
        app: The wrapped ASGI application.
        max_requests: Maximum requests allowed per window.
        window_seconds: Length of the sliding window, in seconds.
        clock: Monotonic time source (injectable for tests).
    """

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        """Derive the rate-limit bucket key for a request.

        Args:
            request: The incoming request.

        Returns:
            The client host, or ``"unknown"`` when it cannot be resolved.
        """
        client = request.client
        return client.host if client else "unknown"

    def _is_allowed(self, key: str) -> bool:
        """Record a hit and report whether it is within the limit.

        Args:
            key: The client bucket key.

        Returns:
            True if the request is allowed, False if the cap is exceeded.
        """
        now = self._clock()
        window_start = now - self.window_seconds
        hits = self._hits[key]
        while hits and hits[0] <= window_start:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Enforce the limit for HTTP scopes, passing others through.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        key = self._client_key(request)
        if not self._is_allowed(key):
            response: Response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(int(self.window_seconds))},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
