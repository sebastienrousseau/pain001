# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Contract of the rate limiter: window edges, buckets and the 429.

The window boundary is inclusive on the old side (a hit exactly one
window ago no longer counts), each client has its own bucket, and the
refusal body and ``Retry-After`` header are what a client reads. Redis
is faked; clocks are injected.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import fakeredis
import pytest
from fastapi import FastAPI

from pain001.api.ratelimit import (
    InProcessFixedWindowBackend,
    RateLimitMiddleware,
    RedisFixedWindowBackend,
    backend_from_env,
    install_rate_limiting,
    parse_rate_limit,
)


class Clock:
    """A settable time source."""

    def __init__(self, now: float = 0.0) -> None:
        """Start at ``now``."""
        self.now = now

    def __call__(self) -> float:
        """Return the current time."""
        return self.now


def _redis(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Make every ``redis.Redis.from_url`` return one shared fake client."""
    import redis

    client = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr(
        redis.Redis, "from_url", classmethod(lambda cls, url, **kw: client)
    )
    return client


def test_hit_exactly_one_window_ago_no_longer_counts() -> None:
    """At ``t + window`` the hit from ``t`` has expired."""
    clock = Clock()
    backend = InProcessFixedWindowBackend(1, 10.0, clock=clock)
    clock.now = 5.0
    assert backend.is_allowed("a")
    clock.now = 14.9
    assert not backend.is_allowed("a")
    clock.now = 15.0  # no sweep due now: only the expiry rule frees "a"
    assert backend.is_allowed("a")


def test_sweep_runs_once_per_window_from_construction() -> None:
    """Idle clients are forgotten at window boundaries, not every call."""
    clock = Clock()
    backend = InProcessFixedWindowBackend(5, 10.0, clock=clock)
    clock.now = 5.0
    backend.is_allowed("early")
    clock.now = 10.0  # first sweep: "early" (5.0) is still in the window
    backend.is_allowed("b")
    clock.now = 16.0  # no sweep until 20.0, so "early" is kept
    backend.is_allowed("c")
    assert sorted(backend._hits) == ["b", "c", "early"]
    clock.now = 20.0  # sweep: hits at or before 10.0 are gone
    backend.is_allowed("d")
    assert sorted(backend._hits) == ["c", "d"]


def test_sweep_drops_a_client_whose_last_hit_is_the_window_start() -> None:
    """A last hit exactly at the window start is idle and swept."""
    clock = Clock()
    backend = InProcessFixedWindowBackend(5, 10.0, clock=clock)
    backend.is_allowed("old")
    clock.now = 10.0
    backend.is_allowed("new")
    assert list(backend._hits) == ["new"]


def test_redis_buckets_are_per_client_with_default_namespace() -> None:
    """Each client has its own bucket under ``pain001:ratelimit``."""
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    backend = RedisFixedWindowBackend(
        1, 60.0, client=client, clock=Clock(125.0)
    )
    assert backend.is_allowed("a")
    assert backend.is_allowed("b")
    assert not backend.is_allowed("a")
    assert sorted(client.keys("*")) == [
        "pain001:ratelimit:2:a",
        "pain001:ratelimit:2:b",
    ]


@pytest.mark.parametrize(
    ("namespace", "prefix"),
    [("rl:", "rl:"), ("boX:", "boX:"), (":rl", ":rl:")],
)
def test_redis_namespace_loses_only_trailing_colons(
    namespace: str, prefix: str
) -> None:
    """Trailing colons are dropped from the namespace, nothing else."""
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    RedisFixedWindowBackend(
        1, 60.0, namespace=namespace, client=client, clock=Clock(0.0)
    ).is_allowed("k")
    assert client.keys("*") == [f"{prefix}0:k"]


def test_redis_sub_second_window_expires_after_one_second() -> None:
    """A window under a second still gets the minimum one-second TTL."""
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    RedisFixedWindowBackend(
        1, 0.5, client=client, clock=Clock(0.0)
    ).is_allowed("k")
    assert client.ttl("pain001:ratelimit:0:k") == 1


def test_redis_backend_errors_are_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both constructor refusals say what is missing and how to fix it."""
    with pytest.raises(ValueError) as info:
        RedisFixedWindowBackend(1, 1.0)
    assert (
        str(info.value) == "RedisFixedWindowBackend requires a url or a client"
    )
    monkeypatch.setitem(sys.modules, "redis", None)
    with pytest.raises(ImportError) as missing:
        RedisFixedWindowBackend(1, 1.0, url="redis://localhost:6379/0")
    assert str(missing.value) == (
        "The pain001[redis] extra is required for RedisFixedWindowBackend; "
        "install pain001[redis] to enable it."
    )


def test_redis_backend_from_url_uses_the_built_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A backend built from a URL counts in the client the URL produced."""
    client = _redis(monkeypatch)
    backend = RedisFixedWindowBackend(
        1, 60.0, url="redis://example.invalid:6379/0", clock=Clock(0.0)
    )
    assert backend.is_allowed("k")
    assert not backend.is_allowed("k")
    assert client.get("pain001:ratelimit:0:k") == "2"


def test_env_memory_backend_uses_the_given_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``memory`` selects the in-process backend, driven by ``clock``."""
    monkeypatch.setenv("PAIN001_RATE_LIMIT_BACKEND", "memory")
    clock = Clock(0.0)
    backend = backend_from_env(1, 60.0, clock=clock)
    assert isinstance(backend, InProcessFixedWindowBackend)
    assert backend.is_allowed("k")
    assert not backend.is_allowed("k")
    clock.now = 61.0
    assert backend.is_allowed("k")


def test_env_redis_backend_gets_cap_and_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Redis backend from the env enforces the cap on the clock given."""
    client = _redis(monkeypatch)
    monkeypatch.setenv("PAIN001_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("PAIN001_RATE_LIMIT_REDIS_URL", "redis://x.invalid/0")
    backend = backend_from_env(2, 60.0, clock=Clock(150.0))
    assert [backend.is_allowed("k") for _ in range(3)] == [True, True, False]
    assert client.keys("*") == ["pain001:ratelimit:2:k"]


def test_env_redis_without_url_names_both_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal names the two variables that would supply a URL."""
    monkeypatch.setenv("PAIN001_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.delenv("PAIN001_RATE_LIMIT_REDIS_URL", raising=False)
    monkeypatch.delenv("PAIN001_JOB_STORE_URL", raising=False)
    with pytest.raises(ValueError) as info:
        backend_from_env(1, 1.0)
    assert str(info.value) == (
        "PAIN001_RATE_LIMIT_BACKEND=redis but neither "
        "PAIN001_RATE_LIMIT_REDIS_URL nor PAIN001_JOB_STORE_URL is set"
    )


class Recorder:
    """An ASGI app that reads one message and answers 204."""

    def __init__(self) -> None:
        """Start with nothing seen."""
        self.seen: list[str] = []

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        """Record the scope type and the first received message type."""
        self.seen.append(scope["type"])
        self.seen.append((await receive())["type"])
        if scope["type"] != "http":
            await send({"type": f"{scope['type']}.startup.complete"})
            return
        await send({"type": "http.response.start", "status": 204})
        await send({"type": "http.response.body", "body": b""})


def _call(
    middleware: RateLimitMiddleware, scope_type: str = "http"
) -> list[dict[str, Any]]:
    """Run one request (or other scope) through ``middleware``."""
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": f"{scope_type}.request", "body": b""}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {
        "type": scope_type,
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": ("10.0.0.1", 1234),
    }
    asyncio.run(middleware(scope, receive, send))
    return sent


def test_allowed_and_other_scopes_reach_the_app_intact() -> None:
    """The app gets the real receive and send channels."""
    app = Recorder()
    middleware = RateLimitMiddleware(app, max_requests=5, window_seconds=60.0)
    assert middleware.max_requests == 5
    sent = _call(middleware)
    assert sent[0]["status"] == 204
    assert _call(middleware, "lifespan") == [
        {"type": "lifespan.startup.complete"}
    ]
    assert app.seen == ["http", "http.request", "lifespan", "lifespan.request"]


def test_refusal_is_429_with_body_and_retry_after() -> None:
    """Over the cap: 429, the documented detail and Retry-After."""
    middleware = RateLimitMiddleware(
        Recorder(), max_requests=1, window_seconds=90.0, clock=Clock(0.0)
    )
    _call(middleware)
    start, body = _call(middleware)
    assert start["status"] == 429
    assert (b"retry-after", b"90") in start["headers"]
    assert (
        body["body"] == b'{"detail":"Rate limit exceeded. Try again later."}'
    )


def test_supplied_backend_decides() -> None:
    """A backend passed in is the one consulted, not a built-in one."""

    class Deny:
        """A backend that refuses everything."""

        def is_allowed(self, key: str) -> bool:
            """Refuse."""
            return False

    middleware = RateLimitMiddleware(
        Recorder(), max_requests=100, window_seconds=60.0, backend=Deny()
    )
    assert _call(middleware)[0]["status"] == 429


def test_install_passes_the_parsed_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The installed middleware gets the cap the spec names."""
    monkeypatch.setenv("PAIN001_RATE_LIMIT", "7/second")
    monkeypatch.delenv("PAIN001_RATE_LIMIT_BACKEND", raising=False)
    fresh = FastAPI()
    install_rate_limiting(fresh)
    kwargs = fresh.user_middleware[0].kwargs
    assert kwargs["max_requests"] == 7
    assert kwargs["window_seconds"] == 1.0


def test_parse_errors_quote_the_spec() -> None:
    """Both kinds of malformed spec are reported with the spec itself."""
    for spec in ("lots/minute", "5/fortnight"):
        with pytest.raises(ValueError) as info:
            parse_rate_limit(spec)
        assert str(info.value) == f"Invalid rate limit: {spec!r}"
