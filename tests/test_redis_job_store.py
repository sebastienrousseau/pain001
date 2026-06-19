# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Tests for the Redis-backed job store (issue #171).

The store implements the existing :class:`JobStore` Protocol so it
is a drop-in replacement for :class:`FileJobStore`. Tests use
``fakeredis`` so they run in-process with no external service.
"""

from __future__ import annotations

import sys
import time

import fakeredis
import pytest

from pain001.api.job_manager import JobManager, JobStatus
from pain001.api.job_store import (
    FileJobStore,
    JobStore,
    RedisJobStore,
    job_store_from_env,
)


@pytest.fixture
def fake_redis_client():
    """A fresh fakeredis client per test (no cross-test state)."""
    return fakeredis.FakeStrictRedis(decode_responses=True)


# ---------------------------------------------------------------------------
# Criterion 1: implements the JobStore protocol
# ---------------------------------------------------------------------------
def test_redis_store_implements_jobstore_protocol(fake_redis_client):
    """``RedisJobStore`` satisfies the ``JobStore`` runtime Protocol."""
    store = RedisJobStore(client=fake_redis_client)
    assert isinstance(store, JobStore)
    assert callable(store.save)
    assert callable(store.load_all)
    assert callable(store.delete)


# ---------------------------------------------------------------------------
# Criterion 2: round-trip via JobManager
# ---------------------------------------------------------------------------
def test_round_trip_via_job_manager_rehydrates_state(fake_redis_client):
    """A job written by one JobManager is visible to a fresh manager."""
    store = RedisJobStore(client=fake_redis_client)
    manager_a = JobManager(store=store)
    job_id = manager_a.create_job()
    manager_a.update_status(
        job_id, JobStatus.SUCCESS, result={"file_path": "/tmp/out.xml"}
    )

    manager_b = JobManager(store=RedisJobStore(client=fake_redis_client))
    rehydrated = manager_b.get_job(job_id)
    assert rehydrated is not None
    assert rehydrated.status == JobStatus.SUCCESS
    assert rehydrated.result == {"file_path": "/tmp/out.xml"}


# ---------------------------------------------------------------------------
# Criterion 3: update_status + cancel write through
# ---------------------------------------------------------------------------
def test_update_status_writes_through_to_redis(fake_redis_client):
    """``update_status`` persists to Redis and a fresh manager sees it."""
    manager_a = JobManager(store=RedisJobStore(client=fake_redis_client))
    job_id = manager_a.create_job()
    manager_a.update_status(job_id, JobStatus.PROCESSING)

    manager_b = JobManager(store=RedisJobStore(client=fake_redis_client))
    observed = manager_b.get_job(job_id)
    assert observed.status == JobStatus.PROCESSING

    # Terminal statuses remain final.
    manager_a.update_status(job_id, JobStatus.SUCCESS)
    manager_c = JobManager(store=RedisJobStore(client=fake_redis_client))
    assert manager_c.get_job(job_id).status == JobStatus.SUCCESS


def test_cancel_job_writes_through_to_redis(fake_redis_client):
    """``cancel_job`` persists the cancelled state."""
    manager_a = JobManager(store=RedisJobStore(client=fake_redis_client))
    job_id = manager_a.create_job()
    assert manager_a.cancel_job(job_id) is True

    manager_b = JobManager(store=RedisJobStore(client=fake_redis_client))
    assert manager_b.get_job(job_id).status == JobStatus.CANCELLED


# ---------------------------------------------------------------------------
# Criterion 4: env-driven backend selection
# ---------------------------------------------------------------------------
def test_job_store_from_env_selects_redis_for_redis_url(monkeypatch):
    """``PAIN001_JOB_STORE_URL=redis://...`` selects the Redis backend."""
    monkeypatch.setenv("PAIN001_JOB_STORE_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("PAIN001_JOB_STORE_DIR", raising=False)
    store = job_store_from_env()
    assert isinstance(store, RedisJobStore)


def test_job_store_from_env_falls_back_to_file(monkeypatch, tmp_path):
    """No URL set + JOB_STORE_DIR set -> FileJobStore."""
    monkeypatch.delenv("PAIN001_JOB_STORE_URL", raising=False)
    monkeypatch.setenv("PAIN001_JOB_STORE_DIR", str(tmp_path))
    store = job_store_from_env()
    assert isinstance(store, FileJobStore)


def test_job_store_from_env_returns_none_when_unset(monkeypatch):
    """No URL + no DIR -> ``None`` (in-memory manager)."""
    monkeypatch.delenv("PAIN001_JOB_STORE_URL", raising=False)
    monkeypatch.delenv("PAIN001_JOB_STORE_DIR", raising=False)
    assert job_store_from_env() is None


def test_job_store_from_env_rejects_unknown_scheme(monkeypatch):
    """An unsupported scheme raises a documented ``ValueError``."""
    monkeypatch.setenv(
        "PAIN001_JOB_STORE_URL", "memcached://localhost:11211"
    )
    with pytest.raises(ValueError, match="Unsupported"):
        job_store_from_env()


# ---------------------------------------------------------------------------
# Criterion 5: concurrency safety
# ---------------------------------------------------------------------------
def test_two_managers_on_same_job_id_keep_terminal_state(fake_redis_client):
    """Concurrent managers cannot resurrect a cancelled job.

    Driving two managers against the same Redis: cancellation by A
    is observable by B, and a subsequent ``update_status`` from B on
    the same id leaves the cancelled status in place.
    """
    manager_a = JobManager(store=RedisJobStore(client=fake_redis_client))
    job_id = manager_a.create_job()
    manager_a.cancel_job(job_id)

    manager_b = JobManager(store=RedisJobStore(client=fake_redis_client))
    observed = manager_b.get_job(job_id)
    assert observed.status == JobStatus.CANCELLED

    # Trying to advance the cancelled job from B should not resurrect it.
    manager_b.update_status(job_id, JobStatus.PROCESSING)
    manager_c = JobManager(store=RedisJobStore(client=fake_redis_client))
    assert (
        manager_c.get_job(job_id).status == JobStatus.CANCELLED
    ), "cancelled jobs must stay terminal across managers"


# ---------------------------------------------------------------------------
# Criterion 6: clear ImportError when the extra is not installed
# ---------------------------------------------------------------------------
def test_redis_store_requires_redis_package(monkeypatch):
    """Importing RedisJobStore with redis missing raises a clear ImportError.

    Simulate the ``pain001[redis]`` extra being absent by purging the
    ``redis`` module and a fake import that raises ``ImportError``.
    The error message names the extra to install.
    """
    monkeypatch.setitem(sys.modules, "redis", None)
    with pytest.raises(ImportError, match="pain001\\[redis\\]"):
        RedisJobStore(url="redis://localhost:6379/0")


def test_redis_namespace_isolation(fake_redis_client):
    """Two stores with different namespaces don't see each other's jobs."""
    store_a = RedisJobStore(
        client=fake_redis_client, namespace="env-a:jobs"
    )
    store_b = RedisJobStore(
        client=fake_redis_client, namespace="env-b:jobs"
    )
    store_a.save("job-1", {"id": "job-1", "status": "running"})
    store_b.save("job-2", {"id": "job-2", "status": "running"})
    a_jobs = store_a.load_all()
    b_jobs = store_b.load_all()
    assert set(a_jobs) == {"job-1"}
    assert set(b_jobs) == {"job-2"}


def test_redis_save_and_delete_round_trip(fake_redis_client):
    """Direct save/load/delete round-trip without a JobManager."""
    store = RedisJobStore(client=fake_redis_client)
    snapshot = {
        "job_id": "abc-123",
        "status": "running",
        "message_type": "pain.001.001.03",
        "created_at": time.time(),
    }
    store.save("abc-123", snapshot)
    assert store.load_all() == {"abc-123": snapshot}
    store.delete("abc-123")
    assert store.load_all() == {}


def test_redis_url_or_client_required():
    """Constructor rejects calls without either ``url`` or ``client``."""
    with pytest.raises(ValueError, match="url or a client"):
        RedisJobStore()
