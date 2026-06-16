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

"""Job management for async XML generation."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pain001.api.job_store import JobStore, job_store_from_env


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = frozenset(
    {JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED}
)


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
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
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


class JobManager:
    """Manages async job lifecycle.

    Args:
        max_jobs: Maximum number of jobs to keep in memory.
        store: Optional persistence backend. When provided, jobs are
            write-through persisted and rehydrated from it on construction
            so they survive a process restart.
    """

    def __init__(self, max_jobs: int = 1000, store: JobStore | None = None):
        self.jobs: dict[str, JobResult] = {}
        self.max_jobs = max_jobs
        self.store = store
        if store is not None:
            for job_id, snapshot in store.load_all().items():
                self.jobs[job_id] = JobResult.from_dict(snapshot)

    def _persist(self, job_id: str) -> None:
        """Write a job through to the persistence backend, if configured.

        Args:
            job_id: Identifier of the job to persist.
        """
        if self.store is not None and job_id in self.jobs:
            self.store.save(job_id, self.jobs[job_id].to_dict())

    def create_job(self) -> str:
        """Create a new job.

        Returns:
            Job ID.
        """
        if len(self.jobs) >= self.max_jobs:  # pragma: no cover
            self.cleanup_old_jobs()  # pragma: no cover
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = JobResult(
            job_id=job_id,
            status=JobStatus.PENDING,
        )
        self._persist(job_id)
        return job_id

    def get_job(self, job_id: str) -> JobResult | None:
        """Get job by ID.

        Args:
            job_id: Job identifier.

        Returns:
            JobResult or None if not found.
        """
        return self.jobs.get(job_id)

    def update_status(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        job_id: str,
        status: JobStatus,
        progress: int = 0,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Update job status.

        Args:
            job_id: Job identifier.
            status: New status.
            progress: Progress percentage (0-100).
            result: Result data if completed.
            error: Error message if failed.

        Terminal statuses (success/failed/cancelled) are final: a
        late-arriving update (e.g. a worker finishing after the user
        cancelled the job) must not resurrect or overwrite them.
        """
        if job_id in self.jobs:  # pragma: no cover
            job = self.jobs[job_id]
            if job.status in TERMINAL_STATUSES:  # pragma: no cover
                return  # pragma: no cover
            job.status = status
            job.progress_percent = min(100, max(0, progress))
            job.updated_at = datetime.now(timezone.utc)
            if result:
                job.result = result
            if error:
                job.error = error
            self._persist(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.

        Args:
            job_id: Job identifier.

        Returns:
            True if cancelled, False if not found.
        """
        if job_id in self.jobs:
            job = self.jobs[job_id]
            if job.status not in TERMINAL_STATUSES:
                job.status = JobStatus.CANCELLED
                job.updated_at = datetime.now(timezone.utc)
                self._persist(job_id)
                return True
        return False

    def cleanup_old_jobs(self, keep_count: int = 100) -> None:
        """Remove old completed jobs to free memory.

        Args:
            keep_count: Number of recent jobs to keep.
        """
        completed_jobs = [  # pragma: no cover
            (job_id, job)
            for job_id, job in self.jobs.items()
            if job.status in TERMINAL_STATUSES
        ]

        # Sort by updated_at and remove oldest
        if len(completed_jobs) > keep_count:  # pragma: no cover
            completed_jobs.sort(
                key=lambda x: x[1].updated_at
            )  # pragma: no cover
            for job_id, _ in completed_jobs[:-keep_count]:  # pragma: no cover
                del self.jobs[job_id]  # pragma: no cover


# Global job manager instance. Persistence activates only when
# PAIN001_JOB_STORE_DIR is set; otherwise jobs are kept in memory.
job_manager = JobManager(store=job_store_from_env())
