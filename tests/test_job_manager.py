# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The in-memory job manager's eviction and terminal-status rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pain001.api.job_manager import TERMINAL_STATUSES, JobManager


def _finish(manager: JobManager, job_id: str, when: datetime) -> None:
    manager.update_status(job_id, "success", 100)
    manager.jobs[job_id].updated_at = when


def test_create_job_evicts_old_completed_jobs_at_capacity() -> None:
    """At max_jobs the oldest completed jobs are removed, running ones kept."""
    manager = JobManager(max_jobs=3)
    ids = [manager.create_job() for _ in range(3)]
    base = datetime(2026, 9, 12, tzinfo=timezone.utc)
    _finish(manager, ids[0], base)
    _finish(manager, ids[1], base + timedelta(minutes=1))
    # the third job is still running and must survive any cleanup
    manager.cleanup_old_jobs(keep_count=1)
    assert ids[0] not in manager.jobs and ids[1] in manager.jobs
    assert ids[2] in manager.jobs
    # creating at capacity triggers the cleanup with the default keep count
    manager.max_jobs = 2
    new = manager.create_job()
    assert new in manager.jobs


def test_cleanup_keeps_everything_under_the_keep_count() -> None:
    """Fewer completed jobs than keep_count means nothing is removed."""
    manager = JobManager()
    job_id = manager.create_job()
    _finish(manager, job_id, datetime.now(timezone.utc))
    manager.cleanup_old_jobs(keep_count=100)
    assert job_id in manager.jobs


def test_terminal_status_is_not_overwritten() -> None:
    """A late update cannot resurrect a finished or cancelled job."""
    manager = JobManager()
    job_id = manager.create_job()
    assert "cancelled" in TERMINAL_STATUSES or "failed" in TERMINAL_STATUSES
    manager.update_status(job_id, "failed", 50, error="boom")
    manager.update_status(job_id, "running", 75)
    job = manager.get_job(job_id)
    assert job is not None and job.status == "failed" and job.error == "boom"
    manager.update_status("no-such-job", "running", 1)  # silently ignored
