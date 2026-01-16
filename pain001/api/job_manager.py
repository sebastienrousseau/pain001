# Copyright (C) 2023-2026 Sebastien Rousseau.
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
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobResult:  # pylint: disable=too-few-public-methods
    """Represents a job result."""

    def __init__(
        self,
        job_id: str,
        status: JobStatus,
        result: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        """Initialize job result.

        Args:
            job_id: Unique job identifier.
            status: Current job status.
            result: Job result data.
            error: Error message if failed.
        """
        self.job_id = job_id
        self.status = status
        self.result = result
        self.error = error
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.progress_percent = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress_percent": self.progress_percent,
        }


class JobManager:
    """Manages async job lifecycle."""

    def __init__(self, max_jobs: int = 1000):
        """Initialize job manager.

        Args:
            max_jobs: Maximum number of jobs to keep in memory.
        """
        self.jobs: dict[str, JobResult] = {}
        self.max_jobs = max_jobs

    def create_job(self) -> str:
        """Create a new job.

        Returns:
            Job ID.
        """
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = JobResult(
            job_id=job_id,
            status=JobStatus.PENDING,
        )
        return job_id

    def get_job(self, job_id: str) -> Optional[JobResult]:
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
        result: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update job status.

        Args:
            job_id: Job identifier.
            status: New status.
            progress: Progress percentage (0-100).
            result: Result data if completed.
            error: Error message if failed.
        """
        if job_id in self.jobs:
            job = self.jobs[job_id]
            job.status = status
            job.progress_percent = min(100, max(0, progress))
            job.updated_at = datetime.utcnow()
            if result:
                job.result = result
            if error:
                job.error = error

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.

        Args:
            job_id: Job identifier.

        Returns:
            True if cancelled, False if not found.
        """
        if job_id in self.jobs:
            job = self.jobs[job_id]
            if job.status not in [
                JobStatus.SUCCESS,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            ]:
                job.status = JobStatus.CANCELLED
                job.updated_at = datetime.utcnow()
                return True
        return False

    def cleanup_old_jobs(self, keep_count: int = 100) -> None:
        """Remove old completed jobs to free memory.

        Args:
            keep_count: Number of recent jobs to keep.
        """
        completed_jobs = [
            (job_id, job)
            for job_id, job in self.jobs.items()
            if job.status
            in [
                JobStatus.SUCCESS,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            ]
        ]

        # Sort by updated_at and remove oldest
        if len(completed_jobs) > keep_count:
            completed_jobs.sort(key=lambda x: x[1].updated_at)
            for job_id, _ in completed_jobs[:-keep_count]:
                del self.jobs[job_id]


# Global job manager instance
job_manager = JobManager()
