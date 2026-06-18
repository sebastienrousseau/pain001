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

"""Pluggable persistence for async generation jobs.

By default the :class:`~pain001.api.job_manager.JobManager` keeps jobs in
memory, which is lost on restart. Setting ``PAIN001_JOB_STORE_DIR`` to a
writable directory activates the :class:`FileJobStore`, which write-through
persists each job as a JSON document and rehydrates them on startup — so a
job submitted before a deploy can still be polled afterwards.
"""

import json
import os
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class JobStore(Protocol):
    """Persistence backend for job snapshots."""

    def save(self, job_id: str, snapshot: dict[str, Any]) -> None:
        """Persist a single job snapshot.

        Args:
            job_id: Unique job identifier.
            snapshot: Serialisable job state.
        """

    def load_all(self) -> dict[str, dict[str, Any]]:
        """Load every persisted job snapshot.

        Returns:
            A mapping of job id to its snapshot.
        """

    def delete(self, job_id: str) -> None:
        """Remove a persisted job snapshot.

        Args:
            job_id: Unique job identifier.
        """


class FileJobStore:
    """A :class:`JobStore` that persists each job as a JSON file.

    Args:
        directory: Directory under which ``<job_id>.json`` files are kept.
            It is created if it does not exist.
    """

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        """Return the on-disk path for a job id.

        Args:
            job_id: Unique job identifier.

        Returns:
            The JSON file path for the job.
        """
        return self.directory / f"{job_id}.json"

    def save(self, job_id: str, snapshot: dict[str, Any]) -> None:
        """Atomically persist a job snapshot as JSON.

        Args:
            job_id: Unique job identifier.
            snapshot: Serialisable job state.
        """
        target = self._path(job_id)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(snapshot), encoding="utf-8")
        os.replace(tmp, target)

    def load_all(self) -> dict[str, dict[str, Any]]:
        """Load all persisted job snapshots, skipping unreadable files.

        Returns:
            A mapping of job id to its snapshot.
        """
        jobs: dict[str, dict[str, Any]] = {}
        for path in sorted(self.directory.glob("*.json")):
            try:
                jobs[path.stem] = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):  # pragma: no cover
                continue  # pragma: no cover
        return jobs

    def delete(self, job_id: str) -> None:
        """Delete a persisted job snapshot if present.

        Args:
            job_id: Unique job identifier.
        """
        self._path(job_id).unlink(missing_ok=True)


def job_store_from_env() -> FileJobStore | None:
    """Build a :class:`FileJobStore` when ``PAIN001_JOB_STORE_DIR`` is set.

    Returns:
        A :class:`FileJobStore` rooted at the configured directory, or
        ``None`` when persistence is not enabled.
    """
    directory = os.environ.get("PAIN001_JOB_STORE_DIR")
    if not directory:
        return None
    return FileJobStore(directory)
