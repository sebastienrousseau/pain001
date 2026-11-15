# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Contract of the file and Redis job stores and their env selection.

A job store is what lets a job outlive a restart or move between
replicas, so its key layout, its permissions and its tolerance of a
half-written keyspace are observable behaviour. Redis is faked.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import fakeredis
import pytest

from pain001.api.job_store import (
    FileJobStore,
    RedisJobStore,
    job_store_from_env,
)


class PagedRedis:
    """A tiny Redis double whose SCAN returns two keys per page."""

    def __init__(self, values: dict[str, Any]) -> None:
        """Hold ``values`` (``None`` means the key vanished before GET)."""
        self.values = values
        self.scans = 0

    def scan(self, cursor: int = 0, match: str = "*", count: int = 10) -> Any:
        """Return the page at ``cursor`` and the next cursor (0 at the end)."""
        self.scans += 1
        if self.scans > 50:
            raise AssertionError("SCAN never finished")
        keys = sorted(self.values)
        next_cursor = cursor + 2 if cursor + 2 < len(keys) else 0
        return next_cursor, [
            k.encode("utf-8") for k in keys[cursor : cursor + 2]
        ]

    def get(self, key: str) -> Any:
        """Return the stored value, as bytes like a raw client would."""
        value = self.values[key]
        return value if value is None else value.encode("utf-8")


def test_file_store_creates_nested_private_directory(tmp_path: Path) -> None:
    """Missing parents are created; the store directory is owner-only."""
    directory = tmp_path / "a" / "b" / "jobs"
    store = FileJobStore(directory)
    assert directory.is_dir()
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    store.save("job-1", {"status": "pending"})
    assert store.load_all() == {"job-1": {"status": "pending"}}


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permissions")
def test_file_store_ping_refuses_a_read_only_directory(tmp_path: Path) -> None:
    """A directory that exists but cannot be written is unusable."""
    store = FileJobStore(tmp_path / "jobs")
    store.ping()
    store.directory.chmod(0o500)
    try:
        with pytest.raises(OSError, match="Job store directory unusable"):
            store.ping()
    finally:
        store.directory.chmod(0o700)


def test_redis_store_default_namespace() -> None:
    """Without a namespace, keys live under ``pain001:jobs:``."""
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    RedisJobStore(client=client).save("j1", {"a": 1})
    assert client.keys("*") == ["pain001:jobs:j1"]


@pytest.mark.parametrize(
    ("namespace", "key"),
    [("ns:jobs:", "ns:jobs:j1"), ("boX:", "boX:j1"), (":lead", ":lead:j1")],
)
def test_redis_store_strips_only_trailing_colons(
    namespace: str, key: str
) -> None:
    """Trailing colons are dropped; everything else is kept as given."""
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    RedisJobStore(client=client, namespace=namespace).save("j1", {})
    assert client.keys("*") == [key]


def test_redis_store_errors_are_exact(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both constructor refusals say what is missing and how to fix it."""
    with pytest.raises(ValueError) as info:
        RedisJobStore()
    assert (
        str(info.value) == "RedisJobStore requires a url or a client instance"
    )
    monkeypatch.setitem(sys.modules, "redis", None)
    with pytest.raises(ImportError) as missing:
        RedisJobStore(url="redis://localhost:6379/0")
    assert str(missing.value) == (
        "The pain001[redis] extra is required for RedisJobStore; "
        "install pain001[redis] to enable it."
    )


def test_redis_store_from_url_uses_the_built_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A store built from a URL talks to the client that URL produced."""
    import redis

    client = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr(
        redis.Redis, "from_url", classmethod(lambda cls, url, **kw: client)
    )
    store = RedisJobStore(url="redis://example.invalid:6379/0")
    store.save("j1", {"status": "success"})
    assert store.load_all() == {"j1": {"status": "success"}}


def test_redis_load_all_follows_the_cursor_and_skips_bad_keys() -> None:
    """Every SCAN page is read; a vanished or corrupt key skips only itself."""
    client = PagedRedis(
        {
            "pain001:jobs:a": None,
            "pain001:jobs:b": json.dumps({"status": "pending"}),
            "pain001:jobs:c": "{not json",
            "pain001:jobs:d": json.dumps({"status": "success"}),
            "pain001:jobs:e": json.dumps({"status": "failed"}),
        }
    )
    jobs = RedisJobStore(client=client).load_all()
    assert jobs == {
        "b": {"status": "pending"},
        "d": {"status": "success"},
        "e": {"status": "failed"},
    }
    assert client.scans == 3


def test_env_selects_rediss_and_its_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A TLS URL selects Redis; the namespace variable is honoured."""
    monkeypatch.setenv(
        "PAIN001_JOB_STORE_URL", "rediss://example.invalid:6380/0"
    )
    monkeypatch.delenv("PAIN001_JOB_STORE_NAMESPACE", raising=False)
    store = job_store_from_env()
    assert isinstance(store, RedisJobStore)
    assert store._key("j1") == "pain001:jobs:j1"
    monkeypatch.setenv("PAIN001_JOB_STORE_NAMESPACE", "staging:jobs")
    store = job_store_from_env()
    assert isinstance(store, RedisJobStore)
    assert store._key("j1") == "staging:jobs:j1"
