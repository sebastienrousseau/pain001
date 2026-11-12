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

"""Job management for async XML generation."""

import os
import threading
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pain001.api.job_store import JobStore, job_store_from_env
from pain001.exceptions import PaymentValidationError


class JobStatus(StrEnum):
    """Job status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = frozenset(
    {JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED}
)

MAX_ACTIVE_JOBS_ENV = "PAIN001_MAX_ACTIVE_JOBS"
"""Environment variable capping pending plus processing async jobs."""

DEFAULT_MAX_ACTIVE_JOBS = 100
"""Active jobs the API accepts when ``PAIN001_MAX_ACTIVE_JOBS`` is unset."""


class JobCapacityError(RuntimeError):
    """Raised when a new job would exceed the active-job cap."""


class JobCancelledError(RuntimeError):
    """Raised in a worker whose job was cancelled, to stop it early."""


def max_active_jobs() -> int:
    """Return how many jobs may be pending or processing at once.

    Returns:
        ``PAIN001_MAX_ACTIVE_JOBS``, or :data:`DEFAULT_MAX_ACTIVE_JOBS`
        when it is unset or empty.

    Raises:
        ValueError: If the variable is set to anything but a positive
            integer.
    """
    raw = os.environ.get(MAX_ACTIVE_JOBS_ENV, "").strip()
    if not raw:
        return DEFAULT_MAX_ACTIVE_JOBS
    if not raw.isdigit() or int(raw) < 1:
        raise ValueError(
            f"{MAX_ACTIVE_JOBS_ENV} must be a positive integer, got {raw!r}"
        )
    return int(raw)


class JobResult:  # pylint: disable=too-few-public-methods
    """Represents a job result.

    Args:
        job_id: Unique job identifier.
        status: Current job status.
        result: Job result data.
        error: Error message if failed.
    """

    def __init__(
        self,
        job_id: str,
        status: JobStatus,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ):
        self.job_id = job_id
        self.status = status
        self.result = result
        self.error = error
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        self.progress_percent = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialise the job to a plain dictionary.

        Returns:
            A JSON-serialisable snapshot of the job's state.
        """
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress_percent": self.progress_percent,
        }

    @classmethod
    def from_dict(cls, snapshot: dict[str, Any]) -> "JobResult":
        """Reconstruct a job from a persisted snapshot.

        Args:
            snapshot: A dictionary previously produced by :meth:`to_dict`.

        Returns:
            The rehydrated :class:`JobResult`.
        """
        job = cls(
            job_id=snapshot["job_id"],
            status=JobStatus(snapshot["status"]),
            result=snapshot.get("result"),
            error=snapshot.get("error"),
        )
        job.created_at = datetime.fromisoformat(snapshot["created_at"])
        job.updated_at = datetime.fromisoformat(snapshot["updated_at"])
        job.progress_percent = snapshot.get("progress_percent", 0)
        return job


def output_name(message_type: str) -> str:
    """Return a fresh output filename for one generation.

    Every generation gets its own file (GHSA-vv3x-jpvc-w468). A shared
    ``<message_type>.xml`` let a later job overwrite an earlier one and
    served the later caller's payments to the earlier job's download.

    Args:
        message_type: The sanitised message type, e.g. ``pain.001.001.03``.

    Returns:
        ``<message_type>-<32 hex characters>.xml``.
    """
    return f"{message_type}-{uuid.uuid4().hex}.xml"


class JobManager:
    """Manages async job lifecycle.

    Snapshots are written to the store outside the manager's lock, so a
    slow disk or Redis never holds the lock ``/status`` needs; a version
    number per job keeps a late write from replacing a newer one.

    Args:
        max_jobs: Maximum number of jobs to keep in memory; a store
            holding more loads the newest ``max_jobs`` and drops the rest.
        store: Optional persistence backend. When provided, jobs are
            write-through persisted and rehydrated from it on construction
            so they survive a process restart.
        max_active: Most jobs that may be pending or processing at once,
            or ``None`` for no cap. :meth:`create_job` refuses the next.
    """

    def __init__(
        self,
        max_jobs: int = 1000,
        store: JobStore | None = None,
        max_active: int | None = None,
    ):
        self._lock = threading.RLock()
        self._store_lock = threading.Lock()
        self._versions: dict[str, int] = {}
        self._written: dict[str, int] = {}
        self.jobs: dict[str, JobResult] = {}
        self.max_jobs = max_jobs
        self.max_active = max_active
        self.store = store
        if store is not None:
            self._load(store)

    def _load(self, store: JobStore) -> None:
        """Rehydrate the newest ``max_jobs`` jobs and drop the rest.

        Args:
            store: The persistence backend to read.
        """
        loaded = [
            JobResult.from_dict(snapshot)
            for snapshot in store.load_all().values()
        ]
        loaded.sort(key=lambda job: job.updated_at, reverse=True)
        for job in loaded[: self.max_jobs]:
            self.jobs[job.job_id] = job
        for job in loaded[self.max_jobs :]:
            store.delete(job.job_id)

    def _snapshot(self, job_id: str) -> tuple[int, dict[str, Any]] | None:
        """Take a versioned snapshot of a job; call with the lock held.

        Args:
            job_id: Identifier of the job to snapshot.

        Returns:
            ``(version, snapshot)``, or ``None`` when nothing is persisted.
        """
        if self.store is None or job_id not in self.jobs:
            return None
        version = self._versions.get(job_id, 0) + 1
        self._versions[job_id] = version
        return version, self.jobs[job_id].to_dict()

    def _write(
        self, job_id: str, taken: tuple[int, dict[str, Any]] | None
    ) -> None:
        """Write a snapshot to the store, unless a newer one is there.

        Called without the manager lock, so readers never wait on I/O.

        Args:
            job_id: Identifier of the job.
            taken: What :meth:`_snapshot` returned.
        """
        if taken is None or self.store is None:
            return
        version, snapshot = taken
        with self._store_lock:
            # A job evicted since the snapshot stays deleted.
            if job_id not in self._versions or version <= self._written.get(
                job_id, 0
            ):
                return
            self._written[job_id] = version
            self.store.save(job_id, snapshot)

    def _active_count(self) -> int:
        """Count pending and processing jobs; call with the lock held.

        Returns:
            The number of jobs not yet in a terminal status.
        """
        return sum(
            job.status not in TERMINAL_STATUSES for job in self.jobs.values()
        )

    def create_job(self) -> str:
        """Create a new job.

        Returns:
            Job ID.

        Raises:
            JobCapacityError: When ``max_active`` jobs are already
                pending or processing.
        """
        with self._lock:
            if (
                self.max_active is not None
                and self._active_count() >= self.max_active
            ):
                raise JobCapacityError(
                    f"{self.max_active} jobs are already pending or running"
                )
            evicted = (
                self._evict(100) if len(self.jobs) >= self.max_jobs else []
            )
            job_id = str(uuid.uuid4())
            self.jobs[job_id] = JobResult(
                job_id=job_id,
                status=JobStatus.PENDING,
            )
            taken = self._snapshot(job_id)
        self._forget(evicted)
        self._write(job_id, taken)
        return job_id

    def get_job(self, job_id: str) -> JobResult | None:
        """Get job by ID.

        Args:
            job_id: Job identifier.

        Returns:
            JobResult or None if not found.
        """
        with self._lock:
            return self.jobs.get(job_id)

    def update_status(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        job_id: str,
        status: JobStatus,
        progress: int = 0,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> bool:
        """Update job status.

        Args:
            job_id: Job identifier.
            status: New status.
            progress: Progress percentage (0-100).
            result: Result data if completed.
            error: Error message if failed.

        Returns:
            True if the update was applied, False if the job is unknown
            or already final.

        Terminal statuses (success/failed/cancelled) are final: a
        late-arriving update (e.g. a worker finishing after the user
        cancelled the job) must not resurrect or overwrite them.
        """
        with self._lock:
            job = self.jobs.get(job_id)
            if job is None or job.status in TERMINAL_STATUSES:
                return False
            job.status = status
            job.progress_percent = min(100, max(0, progress))
            job.updated_at = datetime.now(UTC)
            if result:
                job.result = result
            if error:
                job.error = error
            taken = self._snapshot(job_id)
        self._write(job_id, taken)
        return True

    def raise_if_cancelled(self, job_id: str) -> None:
        """Stop the calling worker if its job was cancelled.

        Args:
            job_id: Job identifier.

        Raises:
            JobCancelledError: If the job is cancelled.
        """
        with self._lock:
            job = self.jobs.get(job_id)
            cancelled = job is not None and job.status is JobStatus.CANCELLED
        if cancelled:
            raise JobCancelledError(job_id)

    def report_progress(self, job_id: str, percent: int) -> None:
        """Mark a job as processing at ``percent``: a worker's safe point.

        The generation pipeline reports at each stage boundary; for a
        cancelled job :meth:`raise_if_cancelled` raises
        :class:`JobCancelledError` there, so the worker stops instead of
        rendering its file.

        Args:
            job_id: Job identifier.
            percent: Progress percentage.
        """
        self.raise_if_cancelled(job_id)
        self.update_status(job_id, JobStatus.PROCESSING, progress=percent)

    @staticmethod
    def error_for(exc: Exception) -> str:
        """Return the error a job that raised ``exc`` reports.

        A data validation failure says which rows and columns to fix,
        the same detail ``POST /generate`` returns with a 400; anything
        else stays generic so internals never reach the job record.

        Args:
            exc: The exception that ended the job.

        Returns:
            The message to store on the job.
        """
        if isinstance(exc, PaymentValidationError):
            return str(exc)
        return "Processing failed"

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.

        Args:
            job_id: Job identifier.

        Returns:
            True if cancelled, False if not found.
        """
        with self._lock:
            job = self.jobs.get(job_id)
            if job is None or job.status in TERMINAL_STATUSES:
                return False
            job.status = JobStatus.CANCELLED
            job.updated_at = datetime.now(UTC)
            taken = self._snapshot(job_id)
        self._write(job_id, taken)
        return True

    def cleanup_old_jobs(self, keep_count: int = 100) -> None:
        """Remove old completed jobs from memory and from the store.

        Args:
            keep_count: Number of recent jobs to keep.
        """
        with self._lock:
            evicted = self._evict(keep_count)
        self._forget(evicted)

    def _evict(self, keep_count: int) -> list[str]:
        """Drop all but the newest ``keep_count`` finished jobs from memory.

        Call with the lock held.

        Args:
            keep_count: Number of recent finished jobs to keep.

        Returns:
            The identifiers removed, for :meth:`_forget`.
        """
        completed_jobs = [
            (job_id, job)
            for job_id, job in self.jobs.items()
            if job.status in TERMINAL_STATUSES
        ]
        if len(completed_jobs) <= keep_count:
            return []
        # Sort by updated_at and remove oldest
        completed_jobs.sort(key=lambda x: x[1].updated_at)
        # ``[:-keep_count]`` would keep everything when keep_count is 0.
        excess = len(completed_jobs) - keep_count
        evicted = [job_id for job_id, _ in completed_jobs[:excess]]
        for job_id in evicted:
            del self.jobs[job_id]
            self._versions.pop(job_id, None)
        return evicted

    def _forget(self, job_ids: list[str]) -> None:
        """Delete evicted jobs from the store, outside the manager lock.

        Args:
            job_ids: The jobs just removed from memory.
        """
        if self.store is None:
            return
        with self._store_lock:
            for job_id in job_ids:
                self._written.pop(job_id, None)
                self.store.delete(job_id)


# Global job manager instance. Persistence activates only when
# PAIN001_JOB_STORE_DIR is set; otherwise jobs are kept in memory.
job_manager = JobManager(
    store=job_store_from_env(), max_active=max_active_jobs()
)
