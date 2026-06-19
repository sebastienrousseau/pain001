# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Tests for the Redis-backed distributed rate limiter (issue #172).

The Redis backend honours the same ``PAIN001_RATE_LIMIT`` spec as the
in-process default and enforces the cap across multiple API replicas
sharing one Redis. ``fakeredis`` is used so the tests run in-process.
"""

from __future__ import annotations

import sys

import fakeredis
import pytest

from pain001.api.ratelimit import (
    InProcessFixedWindowBackend,
    RateLimiterBackend,
    RedisFixedWindowBackend,
    backend_from_env,
    parse_rate_limit,
)


# A controllable clock fixture so we can advance the window
# deterministically across tests.
class FakeClock:
    """Injectable time source returning monotonically rising seconds."""

    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def fake_redis_client():
    return fakeredis.FakeStrictRedis(decode_responses=True)


# ---------------------------------------------------------------------------
# Criterion 1: parse semantics match the in-process limiter
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "spec, expected",
    [
        ("5/second", (5, 1.0)),
        ("100/minute", (100, 60.0)),
        ("10/hour", (10, 3600.0)),
        ("1/day", (1, 86400.0)),
    ],
)
def test_parse_rate_limit_shared_with_redis(spec, expected):
    """The Redis backend honours the exact same spec parser."""
    parsed = parse_rate_limit(spec)
    assert parsed == expected


# ---------------------------------------------------------------------------
# Criterion 2: 429 + Retry-After on overflow
# ---------------------------------------------------------------------------
def test_redis_backend_allows_under_cap_and_blocks_overflow(
    fake_redis_client, fake_clock
):
    """Requests under the cap pass; the one over the cap is rejected."""
    backend = RedisFixedWindowBackend(
        max_requests=3,
        window_seconds=60.0,
        client=fake_redis_client,
        clock=fake_clock,
    )
    for _ in range(3):
        assert backend.is_allowed("client-1") is True
    # 4th in the same window must be rejected.
    assert backend.is_allowed("client-1") is False


# ---------------------------------------------------------------------------
# Criterion 3: window resets after it elapses
# ---------------------------------------------------------------------------
def test_redis_backend_window_resets_when_clock_advances(
    fake_redis_client, fake_clock
):
    """Advancing the clock past the window frees the bucket."""
    backend = RedisFixedWindowBackend(
        max_requests=2,
        window_seconds=10.0,
        client=fake_redis_client,
        clock=fake_clock,
    )
    assert backend.is_allowed("client-1") is True
    assert backend.is_allowed("client-1") is True
    assert backend.is_allowed("client-1") is False
    # Move past the window boundary.
    fake_clock.advance(10.0)
    assert backend.is_allowed("client-1") is True


# ---------------------------------------------------------------------------
# Criterion 4: cross-replica enforcement
# ---------------------------------------------------------------------------
def test_two_replicas_share_one_cap(fake_redis_client, fake_clock):
    """Two limiter instances against one Redis enforce a single cap."""
    replica_a = RedisFixedWindowBackend(
        max_requests=3,
        window_seconds=60.0,
        client=fake_redis_client,
        clock=fake_clock,
    )
    replica_b = RedisFixedWindowBackend(
        max_requests=3,
        window_seconds=60.0,
        client=fake_redis_client,
        clock=fake_clock,
    )
    # 2 hits via A + 1 via B = 3 total, all allowed.
    assert replica_a.is_allowed("shared-client") is True
    assert replica_b.is_allowed("shared-client") is True
    assert replica_a.is_allowed("shared-client") is True
    # The combined 4th hit is rejected (whichever replica receives it).
    assert replica_b.is_allowed("shared-client") is False


# ---------------------------------------------------------------------------
# Criterion 5: env-driven backend selection
# ---------------------------------------------------------------------------
def test_backend_from_env_defaults_to_in_process(monkeypatch):
    """Unset / 'memory' -> InProcessFixedWindowBackend."""
    monkeypatch.delenv("PAIN001_RATE_LIMIT_BACKEND", raising=False)
    backend = backend_from_env(max_requests=10, window_seconds=60.0)
    assert isinstance(backend, InProcessFixedWindowBackend)


def test_backend_from_env_selects_redis(monkeypatch):
    """``PAIN001_RATE_LIMIT_BACKEND=redis`` returns the Redis backend."""
    monkeypatch.setenv("PAIN001_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv(
        "PAIN001_RATE_LIMIT_REDIS_URL", "redis://localhost:6379/0"
    )
    backend = backend_from_env(max_requests=10, window_seconds=60.0)
    assert isinstance(backend, RedisFixedWindowBackend)


def test_backend_from_env_falls_back_to_job_store_url(monkeypatch):
    """Without REDIS_URL, the job-store URL is reused so one env is enough."""
    monkeypatch.setenv("PAIN001_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.delenv("PAIN001_RATE_LIMIT_REDIS_URL", raising=False)
    monkeypatch.setenv(
        "PAIN001_JOB_STORE_URL", "redis://localhost:6379/0"
    )
    backend = backend_from_env(max_requests=10, window_seconds=60.0)
    assert isinstance(backend, RedisFixedWindowBackend)


def test_backend_from_env_rejects_unknown_value(monkeypatch):
    """An unrecognised backend value raises ``ValueError``."""
    monkeypatch.setenv("PAIN001_RATE_LIMIT_BACKEND", "memcached")
    with pytest.raises(ValueError, match="Unsupported"):
        backend_from_env(max_requests=10, window_seconds=60.0)


def test_backend_from_env_redis_requires_url(monkeypatch):
    """``backend=redis`` without a URL raises ``ValueError``."""
    monkeypatch.setenv("PAIN001_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.delenv("PAIN001_RATE_LIMIT_REDIS_URL", raising=False)
    monkeypatch.delenv("PAIN001_JOB_STORE_URL", raising=False)
    with pytest.raises(ValueError, match="REDIS_URL"):
        backend_from_env(max_requests=10, window_seconds=60.0)


# ---------------------------------------------------------------------------
# Criterion 6: bucket keys namespaced + TTL set
# ---------------------------------------------------------------------------
def test_redis_buckets_are_namespaced_and_expire(
    fake_redis_client, fake_clock
):
    """Bucket keys live under the namespace and carry a TTL."""
    backend = RedisFixedWindowBackend(
        max_requests=1,
        window_seconds=30.0,
        client=fake_redis_client,
        clock=fake_clock,
        namespace="env-x:ratelimit",
    )
    backend.is_allowed("client-1")
    keys = fake_redis_client.keys("env-x:ratelimit:*")
    assert keys, "bucket key was not written"
    # TTL is set: positive integer, capped at the window length.
    ttl = fake_redis_client.ttl(keys[0])
    assert 0 < ttl <= 30


# ---------------------------------------------------------------------------
# Protocol / import-guard checks
# ---------------------------------------------------------------------------
def test_redis_backend_satisfies_protocol(fake_redis_client):
    """``RedisFixedWindowBackend`` is a structural ``RateLimiterBackend``."""
    backend = RedisFixedWindowBackend(
        max_requests=1, window_seconds=1.0, client=fake_redis_client
    )
    assert isinstance(backend, RateLimiterBackend)


def test_redis_backend_requires_redis_package(monkeypatch):
    """Without the redis extra, RedisFixedWindowBackend raises ImportError."""
    monkeypatch.setitem(sys.modules, "redis", None)
    with pytest.raises(ImportError, match="pain001\\[redis\\]"):
        RedisFixedWindowBackend(
            max_requests=1,
            window_seconds=1.0,
            url="redis://localhost:6379/0",
        )


def test_redis_backend_url_or_client_required():
    """Constructor rejects calls without either ``url`` or ``client``."""
    with pytest.raises(ValueError, match="url or a client"):
        RedisFixedWindowBackend(max_requests=1, window_seconds=1.0)
