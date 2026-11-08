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

"""The REST pipelines run off the event loop, a bounded number at a time.

Every scenario drives the app and its ``/health`` probe on one event
loop, the way a single uvicorn worker does. The CPU-bound step is
replaced by a function that blocks on a :class:`threading.Event`, so
whether ``/health`` answers while it is blocked depends only on where
the pipeline runs, never on timing.
"""

from __future__ import annotations

import asyncio
import importlib
import threading
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from pain001.api.app import app
from pain001.validation.schema_validator import SchemaValidator

_CSV = "pain001/templates/pain.001.001.03/template.csv"
_BODY = {
    "data_source": "csv",
    "file_path": _CSV,
    "message_type": "pain.001.001.03",
    "validate_only": True,
}
# Upper bound for a wait that only expires when the code under test is
# wrong (the blocked step then runs on the event loop and holds it).
_WAIT = 5.0


class _Gate:
    """A stand-in for ``validate_batch`` that blocks until released."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.finished = threading.Event()
        self._lock = threading.Condition()
        self.running = 0
        self.started = 0
        self.peak = 0

    def __call__(self, _validator: Any, data: list[dict[str, Any]]) -> Any:
        with self._lock:
            self.started += 1
            self.running += 1
            self.peak = max(self.peak, self.running)
            self._lock.notify_all()
        self.release.wait(_WAIT)
        with self._lock:
            self.running -= 1
        self.finished.set()
        return len(data), len(data), []

    def wait_started(self, count: int) -> bool:
        """Block until ``count`` pipelines have entered the gate.

        Args:
            count: Number of pipelines to wait for.

        Returns:
            True once they have, False on timeout.
        """
        with self._lock:
            return self._lock.wait_for(lambda: self.started >= count, _WAIT)


def _patch_batch(monkeypatch: pytest.MonkeyPatch, gate: _Gate) -> None:
    """Route ``SchemaValidator.validate_batch`` through ``gate``.

    Args:
        monkeypatch: The test's monkeypatch fixture.
        gate: The blocking stand-in.
    """

    def blocked(validator: Any, data: list[dict[str, Any]]) -> Any:
        return gate(validator, data)

    monkeypatch.setattr(SchemaValidator, "validate_batch", blocked)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


async def _settle(client: httpx.AsyncClient, job_ids: list[str]) -> list[str]:
    """Poll the jobs until none is pending or processing.

    Args:
        client: Client bound to the app.
        job_ids: Jobs to wait for.

    Returns:
        The final status of each job.
    """
    statuses: list[str] = []
    for _ in range(500):
        statuses = [
            (await client.get(f"/api/v1/status/{job_id}")).json()["status"]
            for job_id in job_ids
        ]
        if not {"pending", "processing"} & set(statuses):
            break
        await asyncio.sleep(0.01)
    return statuses


async def _post_validate(client: httpx.AsyncClient) -> Callable[[], Any]:
    task = asyncio.create_task(client.post("/api/v1/validate", json=_BODY))

    async def done() -> int:
        return (await task).status_code

    return done


async def _post_generate(client: httpx.AsyncClient) -> Callable[[], Any]:
    task = asyncio.create_task(client.post("/api/v1/generate", json=_BODY))

    async def done() -> int:
        return (await task).status_code

    return done


async def _post_async(client: httpx.AsyncClient) -> Callable[[], Any]:
    response = await client.post("/api/v1/generate/async", json=_BODY)
    job_id = response.json()["job_id"]

    async def done() -> str:
        return (await _settle(client, [job_id]))[0]

    return done


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        (_post_validate, 200),
        (_post_generate, 200),
        (_post_async, "success"),
    ],
    ids=["validate", "generate", "generate-async"],
)
def test_health_answers_while_a_pipeline_runs(monkeypatch, start, expected):
    """``/health`` is served while a validation or generation is blocked."""
    gate = _Gate()
    _patch_batch(monkeypatch, gate)

    async def scenario() -> tuple[int, bool, Any]:
        async with _client() as client:
            done = await start(client)
            assert await asyncio.to_thread(gate.wait_started, 1)
            health = await client.get("/api/v1/health")
            still_blocked = not gate.finished.is_set()
            gate.release.set()
            return health.status_code, still_blocked, await done()

    health_status, still_blocked, outcome = asyncio.run(scenario())
    assert health_status == 200
    assert still_blocked, "/health waited for the pipeline to finish"
    assert outcome == expected


def test_excess_jobs_queue_behind_the_limit(monkeypatch):
    """With a limit of two, two of four jobs run and two wait as pending."""
    pipeline = importlib.import_module("pain001.api._pipeline")
    monkeypatch.setenv(pipeline.CONCURRENCY_ENV, "2")
    pipeline.reset_executor()
    gate = _Gate()
    _patch_batch(monkeypatch, gate)

    async def scenario() -> tuple[list[str], list[str]]:
        async with _client() as client:
            job_ids = []
            for _ in range(4):
                response = await client.post(
                    "/api/v1/generate/async", json=_BODY
                )
                job_ids.append(response.json()["job_id"])
            assert await asyncio.to_thread(gate.wait_started, 2)
            assert (await client.get("/api/v1/health")).status_code == 200
            waiting = [
                (await client.get(f"/api/v1/status/{job_id}")).json()["status"]
                for job_id in job_ids
            ]
            gate.release.set()
            return waiting, await _settle(client, job_ids)

    try:
        waiting, final = asyncio.run(scenario())
    finally:
        pipeline.reset_executor()
    assert sorted(waiting) == [
        "pending",
        "pending",
        "processing",
        "processing",
    ]
    assert final == ["success"] * 4
    assert gate.peak == 2


@pytest.mark.parametrize(
    ("value", "cpus", "expected"),
    [(None, 6, 6), ("", 6, 6), ("  ", None, 1), ("3", 6, 3)],
)
def test_pipeline_limit(monkeypatch, value, cpus, expected):
    """The limit is the env value, else the CPU count, else one."""
    pipeline = importlib.import_module("pain001.api._pipeline")
    if value is None:
        monkeypatch.delenv(pipeline.CONCURRENCY_ENV, raising=False)
    else:
        monkeypatch.setenv(pipeline.CONCURRENCY_ENV, value)
    monkeypatch.setattr(pipeline.os, "cpu_count", lambda: cpus)
    assert pipeline.pipeline_limit() == expected


@pytest.mark.parametrize("value", ["0", "-1", "two", "1.5"])
def test_pipeline_limit_rejects_non_positive_integers(monkeypatch, value):
    """Anything but a positive integer is a configuration error."""
    pipeline = importlib.import_module("pain001.api._pipeline")
    monkeypatch.setenv(pipeline.CONCURRENCY_ENV, value)
    with pytest.raises(ValueError, match=pipeline.CONCURRENCY_ENV):
        pipeline.pipeline_limit()


def test_bad_limit_stops_the_server_at_startup(monkeypatch):
    """The lifespan reads the limit, so a bad value fails start-up."""
    from fastapi.testclient import TestClient

    pipeline = importlib.import_module("pain001.api._pipeline")
    monkeypatch.setenv(pipeline.CONCURRENCY_ENV, "0")
    with pytest.raises(ValueError, match=pipeline.CONCURRENCY_ENV):
        with TestClient(app):
            pass


def test_reset_executor_is_idempotent():
    """Resetting twice (no pool the second time) is harmless."""
    pipeline = importlib.import_module("pain001.api._pipeline")
    pipeline.reset_executor()
    pipeline.reset_executor()
    assert pipeline._executor is None
