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

import os
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send


@runtime_checkable
class RateLimiterBackend(Protocol):
    """A pluggable rate-limit decision backend."""

    def is_allowed(self, key: str) -> bool:
        """Record a hit and return ``True`` when within the cap.

        Args:
            key: Per-client bucket key (e.g. client IP).

        Returns:
            ``True`` when the hit fits within the current window's cap;
            ``False`` when the window is full and the request should be
            rejected with HTTP 429.
        """


class InProcessFixedWindowBackend:
    """Single-process fixed-window backend (the default).

    Args:
        max_requests: Maximum requests per window.
        window_seconds: Length of the window.
        clock: Monotonic time source (injectable for tests).
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, key: str) -> bool:
        """Record a hit and return whether the request stays within the cap."""
        now = self._clock()
        window_start = now - self.window_seconds
        hits = self._hits[key]
        while hits and hits[0] <= window_start:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True


class RedisFixedWindowBackend:
    """Redis-backed fixed-window backend for multi-replica deployments.

    Uses ``INCR`` + ``EXPIRE`` on a per-bucket key namespaced as
    ``<namespace>:<window-floor>:<client-key>`` so two API replicas
    sharing one Redis enforce the cap consistently. Bucket keys carry
    a TTL equal to the window length, so stale buckets don't
    accumulate.

    Args:
        max_requests: Maximum requests per window.
        window_seconds: Length of the window.
        url: Redis connection URL (``redis://host:port/db``).
        namespace: Optional key prefix; defaults to ``pain001:ratelimit``.
        clock: Time source (injectable for tests; returns seconds since
            epoch, not monotonic, so window floors line up across hosts).
        client: Optional pre-built ``redis.Redis`` instance; takes
            precedence over ``url`` (useful for tests with ``fakeredis``).

    Raises:
        ImportError: If the ``redis`` package is not installed.
        ValueError: If neither a ``url`` nor a ``client`` is supplied.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        url: str | None = None,
        namespace: str = "pain001:ratelimit",
        clock: Callable[[], float] | None = None,
        client: Any = None,
    ) -> None:
        try:
            import redis  # noqa: PLC0415 - lazy so the extra is optional
        except ImportError as exc:  # pragma: no cover - import-guard
            raise ImportError(
                "The pain001[redis] extra is required for "
                "RedisFixedWindowBackend; install pain001[redis] to "
                "enable it."
            ) from exc
        if client is not None:
            self._client = client
        else:
            if not url:
                raise ValueError(
                    "RedisFixedWindowBackend requires a url or a client"
                )
            self._client = redis.Redis.from_url(url, decode_responses=True)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock or time.time
        self._namespace = namespace.rstrip(":")
        self._ttl_seconds = max(1, int(window_seconds))

    def _bucket_key(self, key: str) -> str:
        """Return a window-floored bucket key for ``key``."""
        floor = int(self._clock() // self.window_seconds)
        return f"{self._namespace}:{floor}:{key}"

    def is_allowed(self, key: str) -> bool:
        """Record a hit and return whether the request stays within the cap."""
        bucket = self._bucket_key(key)
        pipeline = self._client.pipeline()
        pipeline.incr(bucket)
        pipeline.expire(bucket, self._ttl_seconds)
        count, _ = pipeline.execute()
        return int(count) <= self.max_requests


def backend_from_env(
    max_requests: int,
    window_seconds: float,
    clock: Callable[[], float] | None = None,
) -> RateLimiterBackend:
    """Select a backend from environment configuration.

    Selection order:

    * ``PAIN001_RATE_LIMIT_BACKEND=redis`` (default URL from
      ``PAIN001_RATE_LIMIT_REDIS_URL`` or ``PAIN001_JOB_STORE_URL``).
    * Anything else (or unset) -> the in-process default.

    Args:
        max_requests: Per-window cap.
        window_seconds: Window length.
        clock: Optional time source (passed through).

    Returns:
        A configured backend.

    Raises:
        ValueError: If ``PAIN001_RATE_LIMIT_BACKEND`` is set to an
            unrecognised value.
    """
    backend = os.environ.get("PAIN001_RATE_LIMIT_BACKEND", "").strip().lower()
    if not backend or backend == "memory":
        return InProcessFixedWindowBackend(
            max_requests, window_seconds, clock=clock
        )
    if backend == "redis":
        url = os.environ.get(
            "PAIN001_RATE_LIMIT_REDIS_URL",
            os.environ.get("PAIN001_JOB_STORE_URL", ""),
        ).strip()
        if not url:
            raise ValueError(
                "PAIN001_RATE_LIMIT_BACKEND=redis but neither "
                "PAIN001_RATE_LIMIT_REDIS_URL nor "
                "PAIN001_JOB_STORE_URL is set"
            )
        return RedisFixedWindowBackend(
            max_requests, window_seconds, url=url, clock=clock
        )
    raise ValueError(
        f"Unsupported PAIN001_RATE_LIMIT_BACKEND={backend!r}; "
        f"expected 'memory' or 'redis'"
    )


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

    Accepts a pluggable ``backend`` (see :class:`RateLimiterBackend`).
    For backward compatibility, callers may pass ``max_requests`` +
    ``window_seconds`` directly; the middleware then builds an
    :class:`InProcessFixedWindowBackend` itself. Either form works.

    Args:
        app: The wrapped ASGI application.
        max_requests: Maximum requests allowed per window (ignored if
            ``backend`` is supplied).
        window_seconds: Length of the window in seconds (also used for
            the ``Retry-After`` header).
        clock: Monotonic time source (injectable for tests; only used
            when constructing a fallback in-process backend).
        backend: Pluggable backend; pass an instance to use Redis or a
            custom limiter.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] | None = None,
        backend: RateLimiterBackend | None = None,
    ) -> None:
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._backend: RateLimiterBackend = (
            backend
            if backend is not None
            else InProcessFixedWindowBackend(
                max_requests, window_seconds, clock=clock
            )
        )

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
        return self._backend.is_allowed(key)

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
