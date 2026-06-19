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


class RedisJobStore:
    """A :class:`JobStore` that persists each job under a Redis hash key.

    Multiple API replicas behind a load balancer share one Redis, so a
    job submitted on replica A can be polled on replica B and survives
    rolling restarts on either side. Job snapshots are serialised to
    JSON and stored at ``<namespace>:<job_id>``; ``load_all`` enumerates
    every key under the namespace via ``SCAN`` (cursor-paginated, so it
    is safe on a large keyspace).

    Args:
        url: Redis connection URL (``redis://host:port/db``).
        namespace: Optional key prefix; defaults to ``pain001:jobs``.
            Use a per-environment value to isolate dev / staging / prod
            in the same instance.
        client: Optional pre-built ``redis.Redis`` instance; takes
            precedence over ``url`` (useful for tests with ``fakeredis``).

    Raises:
        ImportError: If the ``redis`` package is not installed.
    """

    def __init__(
        self,
        url: str | None = None,
        namespace: str = "pain001:jobs",
        client: Any = None,
    ) -> None:
        try:
            import redis  # noqa: PLC0415 - lazy so the extra is optional
        except ImportError as exc:  # pragma: no cover - import-guard
            raise ImportError(
                "The pain001[redis] extra is required for "
                "RedisJobStore; install pain001[redis] to enable it."
            ) from exc
        if client is not None:
            self._client = client
        else:
            if not url:
                raise ValueError(
                    "RedisJobStore requires a url or a client instance"
                )
            self._client = redis.Redis.from_url(url, decode_responses=True)
        self._namespace = namespace.rstrip(":")

    def _key(self, job_id: str) -> str:
        """Return the namespaced Redis key for a job id."""
        return f"{self._namespace}:{job_id}"

    def save(self, job_id: str, snapshot: dict[str, Any]) -> None:
        """Persist a single job snapshot.

        Args:
            job_id: Unique job identifier.
            snapshot: Serialisable job state.
        """
        self._client.set(self._key(job_id), json.dumps(snapshot))

    def load_all(self) -> dict[str, dict[str, Any]]:
        """Load every persisted job snapshot.

        Returns:
            A mapping of job id to its snapshot.
        """
        jobs: dict[str, dict[str, Any]] = {}
        cursor = 0
        prefix = f"{self._namespace}:"
        while True:
            cursor, keys = self._client.scan(
                cursor=cursor, match=f"{prefix}*", count=100
            )
            for key in keys:
                key_str = (
                    key.decode("utf-8") if isinstance(key, bytes) else key
                )
                raw = self._client.get(key_str)
                if raw is None:
                    continue
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                try:
                    jobs[key_str[len(prefix) :]] = json.loads(raw)
                except json.JSONDecodeError:  # pragma: no cover - defensive
                    continue
            if cursor == 0:
                break
        return jobs

    def delete(self, job_id: str) -> None:
        """Remove a persisted job snapshot.

        Args:
            job_id: Unique job identifier.
        """
        self._client.delete(self._key(job_id))


def job_store_from_env() -> JobStore | None:
    """Build a job store from environment configuration.

    Selection order:

    * ``PAIN001_JOB_STORE_URL=redis://...`` -> :class:`RedisJobStore`
      (multi-replica durable, requires the ``pain001[redis]`` extra).
    * ``PAIN001_JOB_STORE_DIR=/path`` -> :class:`FileJobStore`
      (single-replica durable, no extra dependency).
    * Neither set -> ``None`` (the :class:`JobManager` stays in-memory).

    Returns:
        A configured store, or ``None`` when persistence is not enabled.

    Raises:
        ValueError: If ``PAIN001_JOB_STORE_URL`` has an unrecognised
            scheme.
    """
    url = os.environ.get("PAIN001_JOB_STORE_URL", "").strip()
    if url:
        if url.startswith(("redis://", "rediss://")):
            namespace = os.environ.get(
                "PAIN001_JOB_STORE_NAMESPACE", "pain001:jobs"
            )
            return RedisJobStore(url=url, namespace=namespace)
        raise ValueError(
            f"Unsupported PAIN001_JOB_STORE_URL scheme: {url!r}; "
            f"expected redis:// or rediss://"
        )
    directory = os.environ.get("PAIN001_JOB_STORE_DIR")
    if not directory:
        return None
    return FileJobStore(directory)
