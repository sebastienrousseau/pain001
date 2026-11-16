# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Contract of the async job lifecycle: limits, snapshots and eviction.

``JobManager`` is what ``/generate/async``, ``/status`` and ``/jobs``
read and write, and its snapshots are what a restarted replica reloads.
These tests pin the values a caller or a store can observe.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from pain001.api.job_manager import (
    JobCancelledError,
    JobCapacityError,
    JobManager,
    JobResult,
    JobStatus,
    max_active_jobs,
)
from pain001.exceptions import PaymentValidationError


class RecordingStore:
    """An in-memory JobStore that records every save and delete."""

    def __init__(self, preloaded: dict[str, dict[str, Any]] | None = None):
        """Start with ``preloaded`` snapshots, if any."""
        self.data: dict[str, dict[str, Any]] = dict(preloaded or {})
        self.saves: list[tuple[str, dict[str, Any]]] = []

    def save(self, job_id: str, snapshot: dict[str, Any]) -> None:
        """Keep the snapshot and log the write."""
        self.data[job_id] = snapshot
        self.saves.append((job_id, snapshot))

    def load_all(self) -> dict[str, dict[str, Any]]:
        """Return every stored snapshot."""
        return dict(self.data)

    def delete(self, job_id: str) -> None:
        """Forget a snapshot."""
        self.data.pop(job_id, None)


def _finished(manager: JobManager, count: int) -> None:
    """Add ``count`` finished jobs to ``manager``."""
    for _ in range(count):
        job_id = manager.create_job()
        manager.update_status(job_id, JobStatus.SUCCESS)


def test_max_active_jobs_accepts_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """``1`` is the smallest valid cap; ``0`` is refused."""
    monkeypatch.setenv("PAIN001_MAX_ACTIVE_JOBS", "1")
    assert max_active_jobs() == 1
    monkeypatch.setenv("PAIN001_MAX_ACTIVE_JOBS", "0")
    with pytest.raises(ValueError, match="got '0'"):
        max_active_jobs()


def test_new_job_result_defaults() -> None:
    """A new result keeps its error, starts at 0 % and has UTC times."""
    job = JobResult("j1", JobStatus.FAILED, error="boom")
    assert job.error == "boom"
    assert job.progress_percent == 0
    assert job.created_at.tzinfo is UTC
    assert job.updated_at.tzinfo is UTC


def test_snapshot_round_trip_is_lossless() -> None:
    """to_dict names every field; from_dict restores each of them."""
    job = JobResult("j1", JobStatus.FAILED, result={"a": 1}, error="boom")
    job.progress_percent = 40
    job.created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    job.updated_at = datetime(2026, 1, 2, 3, 4, 6, tzinfo=UTC)
    snapshot = job.to_dict()
    assert snapshot == {
        "job_id": "j1",
        "status": "failed",
        "result": {"a": 1},
        "error": "boom",
        "created_at": "2026-01-02T03:04:05+00:00",
        "updated_at": "2026-01-02T03:04:06+00:00",
        "progress_percent": 40,
    }
    restored = JobResult.from_dict(snapshot)
    assert restored.to_dict() == snapshot
    assert restored.created_at == job.created_at


def test_snapshot_without_progress_reads_zero() -> None:
    """An older snapshot with no progress field reloads at 0 %."""
    restored = JobResult.from_dict(
        {
            "job_id": "j1",
            "status": "pending",
            "created_at": "2026-01-02T03:04:05+00:00",
            "updated_at": "2026-01-02T03:04:05+00:00",
        }
    )
    assert restored.progress_percent == 0
    assert restored.error is None


def test_default_capacity_is_a_thousand_jobs() -> None:
    """At 1,000 jobs the next create evicts down to 100 finished ones."""
    manager = JobManager()
    _finished(manager, 999)
    assert len(manager.jobs) == 999
    manager.create_job()
    assert len(manager.jobs) == 1000
    manager.create_job()
    # 100 finished survivors, the pending job above and the new one.
    assert len(manager.jobs) == 102


def test_no_eviction_below_capacity() -> None:
    """Under ``max_jobs``, creating a job never evicts finished ones."""
    manager = JobManager(max_jobs=500)
    _finished(manager, 150)
    manager.create_job()
    assert len(manager.jobs) == 151


def test_capacity_error_names_the_cap() -> None:
    """The refusal says how many jobs are already active."""
    manager = JobManager(max_active=2)
    manager.create_job()
    manager.create_job()
    with pytest.raises(JobCapacityError) as info:
        manager.create_job()
    assert str(info.value) == "2 jobs are already pending or running"


def test_update_status_progress_is_clamped_and_defaults_to_zero() -> None:
    """Progress is clamped to 0..100 and reset when not given."""
    manager = JobManager()
    job_id = manager.create_job()
    manager.update_status(job_id, JobStatus.PROCESSING, progress=150)
    assert manager.jobs[job_id].progress_percent == 100
    manager.update_status(job_id, JobStatus.PROCESSING, progress=-5)
    assert manager.jobs[job_id].progress_percent == 0
    manager.report_progress(job_id, 55)
    assert manager.jobs[job_id].progress_percent == 55
    manager.update_status(job_id, JobStatus.PROCESSING)
    assert manager.jobs[job_id].progress_percent == 0


def test_cancelled_worker_error_carries_the_job_id() -> None:
    """The exception that stops a cancelled worker names its job."""
    manager = JobManager()
    job_id = manager.create_job()
    manager.cancel_job(job_id)
    with pytest.raises(JobCancelledError) as info:
        manager.report_progress(job_id, 50)
    assert info.value.args == (job_id,)


def test_error_for_hides_internal_failures() -> None:
    """Validation errors are shown; anything else is a generic message."""
    assert JobManager.error_for(RuntimeError("secret")) == "Processing failed"
    message = JobManager.error_for(PaymentValidationError("row 2 bad"))
    assert "row 2 bad" in message


def test_cleanup_keeps_a_hundred_finished_jobs_by_default() -> None:
    """Without an argument, cleanup keeps the newest 100 finished jobs."""
    manager = JobManager()
    _finished(manager, 101)
    manager.cleanup_old_jobs()
    assert len(manager.jobs) == 100


def test_late_snapshot_never_replaces_a_newer_one() -> None:
    """A snapshot taken earlier but written later is dropped."""
    store = RecordingStore()
    manager = JobManager(store=store)
    job_id = manager.create_job()
    with manager._lock:
        stale = manager._snapshot(job_id)
    manager.update_status(job_id, JobStatus.PROCESSING, progress=50)
    manager._write(job_id, stale)
    assert store.data[job_id]["progress_percent"] == 50
    assert store.data[job_id]["status"] == "processing"


def test_same_snapshot_is_written_once() -> None:
    """Writing one snapshot twice reaches the store once."""
    store = RecordingStore()
    manager = JobManager(store=store)
    job_id = manager.create_job()
    with manager._lock:
        taken = manager._snapshot(job_id)
    manager._write(job_id, taken)
    manager._write(job_id, taken)
    assert [saved for saved, _ in store.saves] == [job_id, job_id]
    manager._write(job_id, None)
    assert len(store.saves) == 2


def test_evicting_reloaded_jobs_deletes_them_from_the_store() -> None:
    """Jobs loaded at start-up, never rewritten, can still be evicted."""
    snapshots = {
        f"old-{i}": JobResult(f"old-{i}", JobStatus.SUCCESS).to_dict()
        for i in range(3)
    }
    store = RecordingStore(snapshots)
    manager = JobManager(store=store)
    assert set(manager.jobs) == set(snapshots)
    manager.cleanup_old_jobs(keep_count=0)
    assert manager.jobs == {}
    assert store.data == {}
