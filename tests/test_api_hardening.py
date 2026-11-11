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

"""REST hardening from the 0.0.86 audit (P3, S5, P10, D13, S9, D11).

Each test pins one finding: the dashboard keeps the event loop free,
oversized bodies and runaway job queues are refused, the job store
persists outside the manager lock and forgets what it evicts,
``/metrics`` honours the API key, ``/ready`` reports dependencies,
error bodies mask account data, and the OpenAPI licence is the
project's dual licence.
"""

from __future__ import annotations

import asyncio
import re
import stat
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from pain001.api.app import app
from pain001.api.job_manager import JobManager, JobStatus
from pain001.api.job_store import FileJobStore
from pain001.constants import TEMPLATES_DIR
from pain001.validation.schema_validator import SchemaValidator

client = TestClient(app)

TEMPLATE_CSV = (TEMPLATES_DIR / "pain.001.001.03" / "template.csv").read_text(
    encoding="utf-8"
)
#: A synthetic, mod-97-valid IBAN from the bundled sample, written in
#: lower case so the schema pattern rejects it and the error carries
#: the account number.
SAMPLE_IBAN = "DE07512108001245126162"
LOWER_IBAN = SAMPLE_IBAN.lower()
ACCOUNT_DIGITS = re.compile(r"\d{8,}")


def _payload(**overrides: object) -> dict[str, object]:
    """Return a dashboard payload for the bundled sample CSV."""
    body: dict[str, object] = {
        "filename": "payments.csv",
        "content": TEMPLATE_CSV,
        "message_type": "pain.001.001.03",
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# P3: the dashboard endpoints run their pipeline off the event loop
# ---------------------------------------------------------------------------
def _health_while_blocked(
    path: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[bool, httpx.Response, httpx.Response]:
    """Hold the dashboard pipeline inside validation and ask ``/health``.

    The patched validator waits for an event that is set only once
    ``/health`` has answered. On the event loop it would hold the loop
    until its timeout, so ``released`` tells the two apart without
    depending on timings.

    Args:
        path: The dashboard endpoint to call.
        monkeypatch: Pytest fixture used to patch the validator.

    Returns:
        ``(released, health, upload)``: whether the pipeline was released
        by ``/health`` answering, and both responses.
    """
    release = threading.Event()
    entered = threading.Event()
    outcome: dict[str, bool] = {}
    original = SchemaValidator.validate_batch

    def blocking(self: SchemaValidator, rows: list[dict[str, Any]]) -> Any:
        entered.set()
        outcome["released"] = release.wait(timeout=5)
        return original(self, rows)

    monkeypatch.setattr(SchemaValidator, "validate_batch", blocking)

    async def scenario() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as http:
            upload = asyncio.create_task(http.post(path, json=_payload()))
            for _ in range(500):
                if entered.is_set():
                    break
                await asyncio.sleep(0.01)
            health = await http.get("/api/v1/health")
            release.set()
            return health, await upload

    health, upload = asyncio.run(scenario())
    return outcome.get("released", False), health, upload


@pytest.mark.parametrize(
    "path", ["/api/v1/ui/validate", "/api/v1/ui/generate"]
)
def test_dashboard_pipeline_does_not_block_health(
    path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``/health`` answers while a dashboard upload is mid-validation."""
    released, health, upload = _health_while_blocked(path, monkeypatch)
    assert released, "/health waited for the dashboard pipeline"
    assert health.status_code == 200
    assert upload.status_code == 200


# ---------------------------------------------------------------------------
# S5: request bodies and the job queue are bounded
# ---------------------------------------------------------------------------
def test_body_over_limit_is_refused_from_content_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A declared body over the limit is refused before it is parsed."""
    monkeypatch.setenv("PAIN001_MAX_BODY_BYTES", "1024")
    response = client.post(
        "/api/v1/ui/validate", json=_payload(content="x" * 4096)
    )
    assert response.status_code == 413
    assert "1024" in response.json()["detail"]


def test_streamed_body_over_limit_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A chunked body with no Content-Length is counted as it arrives."""
    monkeypatch.setenv("PAIN001_MAX_BODY_BYTES", "1024")

    def chunks() -> Any:
        yield b'{"filename": "p.csv", "content": "'
        for _ in range(8):
            yield b"x" * 512
        yield b'"}'

    response = client.post(
        "/api/v1/ui/validate",
        content=chunks(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_upload_content_declares_its_cap() -> None:
    """The dashboard payload's ``content`` carries the upload cap."""
    from pain001.api.models import MAX_UPLOAD_BYTES

    schema = app.openapi()["components"]["schemas"]["UiFilePayload"]
    assert schema["properties"]["content"]["maxLength"] == MAX_UPLOAD_BYTES


def test_job_manager_refuses_jobs_beyond_the_active_cap() -> None:
    """Pending and running jobs are capped; finished ones free a slot."""
    from pain001.api.job_manager import JobCapacityError

    manager = JobManager(max_active=2)
    first = manager.create_job()
    manager.create_job()
    with pytest.raises(JobCapacityError):
        manager.create_job()
    manager.update_status(first, JobStatus.SUCCESS, 100)
    assert manager.create_job() in manager.jobs


def test_async_generate_answers_503_at_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``/generate/async`` answers 503 with Retry-After when full."""
    from pain001.api.job_manager import job_manager

    monkeypatch.setattr(job_manager, "max_active", 0)
    response = client.post(
        "/api/v1/generate/async",
        json={
            "data_source": "csv",
            "file_path": "tests/data/template.csv",
            "message_type": "pain.001.001.03",
        },
    )
    assert response.status_code == 503
    assert response.headers["Retry-After"]


# ---------------------------------------------------------------------------
# P10: persistence outside the lock, deletes, load cap, file mode
# ---------------------------------------------------------------------------
class _RecordingStore:
    """An in-memory store that records whether the manager lock is held."""

    def __init__(self, manager_ref: dict[str, JobManager]) -> None:
        self.saved: dict[str, dict[str, Any]] = {}
        self.deleted: list[str] = []
        self.lock_free: list[bool] = []
        self._ref = manager_ref

    def save(self, job_id: str, snapshot: dict[str, Any]) -> None:
        manager = self._ref.get("manager")
        if manager is not None:
            seen: list[bool] = []

            def probe() -> None:
                got = manager._lock.acquire(timeout=1)
                if got:
                    manager._lock.release()
                seen.append(got)

            worker = threading.Thread(target=probe)
            worker.start()
            worker.join()
            self.lock_free.append(seen[0])
        self.saved[job_id] = snapshot

    def load_all(self) -> dict[str, dict[str, Any]]:
        return dict(self.saved)

    def delete(self, job_id: str) -> None:
        self.deleted.append(job_id)
        self.saved.pop(job_id, None)


def test_jobs_are_persisted_outside_the_manager_lock() -> None:
    """A slow store never holds the lock ``/status`` needs."""
    ref: dict[str, JobManager] = {}
    store = _RecordingStore(ref)
    manager = JobManager(store=store)
    ref["manager"] = manager
    job_id = manager.create_job()
    manager.update_status(job_id, JobStatus.PROCESSING, 50)
    manager.cancel_job(job_id)
    assert store.lock_free == [True, True, True]


def test_cleanup_deletes_evicted_jobs_from_the_store() -> None:
    """Evicted jobs leave the store as well as memory."""
    store = _RecordingStore({})
    manager = JobManager(store=store)
    ids = [manager.create_job() for _ in range(3)]
    base = datetime(2026, 9, 12, tzinfo=UTC)
    for offset, job_id in enumerate(ids):
        manager.update_status(job_id, JobStatus.SUCCESS, 100)
        manager.jobs[job_id].updated_at = base + timedelta(minutes=offset)
    manager.cleanup_old_jobs(keep_count=1)
    assert sorted(store.deleted) == sorted(ids[:2])
    assert set(store.saved) == {ids[2]}


def test_load_all_keeps_only_the_newest_max_jobs() -> None:
    """A store larger than ``max_jobs`` loads the newest and drops the rest."""
    store = _RecordingStore({})
    seed = JobManager(store=store)
    ids = [seed.create_job() for _ in range(4)]
    base = datetime(2026, 9, 12, tzinfo=UTC)
    for offset, job_id in enumerate(ids):
        seed.jobs[job_id].updated_at = base + timedelta(minutes=offset)
        store.saved[job_id] = seed.jobs[job_id].to_dict()
    manager = JobManager(max_jobs=2, store=store)
    assert set(manager.jobs) == set(ids[2:])
    assert sorted(store.deleted) == sorted(ids[:2])


def test_job_files_are_private(tmp_path: Path) -> None:
    """Job snapshots are written owner-read/write only."""
    store = FileJobStore(tmp_path / "jobs")
    store.save("job-1", {"job_id": "job-1"})
    mode = stat.S_IMODE((tmp_path / "jobs" / "job-1.json").stat().st_mode)
    assert mode == 0o600


# ---------------------------------------------------------------------------
# D13: /metrics honours the key; payment volume is opt-in; /ready
# ---------------------------------------------------------------------------
def test_metrics_requires_the_api_key_when_one_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ``PAIN001_API_KEY`` set, ``/metrics`` needs it too."""
    monkeypatch.setenv("PAIN001_API_KEY", "k3y")
    assert client.get("/metrics").status_code == 401
    ok = client.get("/metrics", headers={"Authorization": "Bearer k3y"})
    assert ok.status_code == 200


def test_metrics_token_takes_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``PAIN001_METRICS_TOKEN`` gives the scraper its own credential."""
    monkeypatch.setenv("PAIN001_API_KEY", "k3y")
    monkeypatch.setenv("PAIN001_METRICS_TOKEN", "scrape")
    assert (
        client.get(
            "/metrics", headers={"Authorization": "Bearer k3y"}
        ).status_code
        == 401
    )
    ok = client.get("/metrics", headers={"Authorization": "Bearer scrape"})
    assert ok.status_code == 200


def test_payment_volume_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Payment volume by currency is neither recorded nor shown by default."""
    from pain001.api.metrics import registry, render_prometheus

    registry.reset()
    monkeypatch.delenv("PAIN001_METRICS_PAYMENT_VOLUME", raising=False)
    registry.record_data_volumes([{"payment_amount": "10", "currency": "EUR"}])
    assert "pain001_payment_volume_cents_total" not in render_prometheus("x")
    monkeypatch.setenv("PAIN001_METRICS_PAYMENT_VOLUME", "1")
    registry.record_data_volumes([{"payment_amount": "10", "currency": "EUR"}])
    body = render_prometheus("x")
    assert 'pain001_payment_volume_cents_total{currency="EUR"} 1000.0' in body
    registry.reset()


def test_ready_reports_ok() -> None:
    """``/ready`` answers 200 when templates, XSDs and the store load."""
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["templates"] == "ok"


# ---------------------------------------------------------------------------
# S9: error bodies mask account data
# ---------------------------------------------------------------------------
def test_dashboard_errors_mask_account_numbers() -> None:
    """A rejected IBAN is reported masked, in ``value`` and ``message``."""
    # Every row: one debtor IBAN per file, or the one-batch check refuses
    # the upload before the schema reports it.
    bad = TEMPLATE_CSV.replace(SAMPLE_IBAN, LOWER_IBAN)
    response = client.post("/api/v1/ui/validate", json=_payload(content=bad))
    assert response.status_code == 200
    errors = response.json()["errors"]
    assert errors and errors[0]["field"] == "$.debtor_account_IBAN"
    assert "value" in errors[0]
    assert not ACCOUNT_DIGITS.search(response.text), response.text


# ---------------------------------------------------------------------------
# D11: the OpenAPI licence is the project's dual licence
# ---------------------------------------------------------------------------
def test_openapi_licence_is_dual() -> None:
    """The OpenAPI document names ``Apache-2.0 OR MIT``."""
    licence = app.openapi()["info"]["license"]
    assert licence["name"] == "Apache-2.0 OR MIT"
    assert licence["identifier"] == "Apache-2.0 OR MIT"


# ---------------------------------------------------------------------------
# P11 / P12: bounded in-process state
# ---------------------------------------------------------------------------
def test_rate_limiter_forgets_idle_clients() -> None:
    """Clients idle for a full window no longer hold a bucket."""
    from pain001.api.ratelimit import InProcessFixedWindowBackend

    now = [0.0]
    backend = InProcessFixedWindowBackend(5, 10.0, clock=lambda: now[0])
    for host in range(50):
        backend.is_allowed(f"10.0.0.{host}")
    now[0] = 25.0
    backend.is_allowed("10.0.0.200")
    assert list(backend._hits) == ["10.0.0.200"]


def test_summary_samples_are_a_bounded_deque() -> None:
    """Summaries keep the newest 10,000 samples without list.pop(0)."""
    from collections import deque

    from pain001.api.metrics import MetricsRegistry

    reg = MetricsRegistry()
    for value in range(10_005):
        reg.observe("lat", float(value))
    samples = reg._summaries[("lat", ())]
    assert isinstance(samples, deque)
    assert len(samples) == 10_000 and samples[0] == 5.0


# ---------------------------------------------------------------------------
# Edges of the above: configuration, fallbacks and failure paths
# ---------------------------------------------------------------------------
def test_max_body_bytes_reads_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset means the default; anything but a positive integer is refused."""
    from pain001.api.limits import DEFAULT_MAX_BODY_BYTES, max_body_bytes

    monkeypatch.delenv("PAIN001_MAX_BODY_BYTES", raising=False)
    assert max_body_bytes() == DEFAULT_MAX_BODY_BYTES
    monkeypatch.setenv("PAIN001_MAX_BODY_BYTES", "2048")
    assert max_body_bytes() == 2048
    for bad in ("0", "-1", "lots"):
        monkeypatch.setenv("PAIN001_MAX_BODY_BYTES", bad)
        with pytest.raises(ValueError, match="PAIN001_MAX_BODY_BYTES"):
            max_body_bytes()


def test_body_within_limit_and_odd_length_header_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A body under the limit reaches the route; a junk length is ignored."""
    from pain001.api.limits import _declared_length

    monkeypatch.setenv("PAIN001_MAX_BODY_BYTES", "65536")
    response = client.post("/api/v1/ui/validate", json=_payload())
    assert response.status_code == 200
    assert _declared_length({"headers": [(b"content-length", b"x")]}) is None


def test_body_limit_passes_non_http_scopes() -> None:
    """Lifespan and websocket scopes go straight through."""
    from pain001.api.limits import BodyLimitMiddleware

    seen: list[str] = []

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        seen.append(scope["type"])

    asyncio.run(BodyLimitMiddleware(inner)({"type": "lifespan"}, None, None))
    assert seen == ["lifespan"]


def test_upload_over_the_cap_is_413_not_422() -> None:
    """``content`` longer than the cap is refused as too large."""
    from pain001.api.models import MAX_UPLOAD_BYTES

    response = client.post(
        "/api/v1/ui/validate",
        json=_payload(content="x" * (MAX_UPLOAD_BYTES + 1)),
    )
    assert response.status_code == 413
    assert "CLI" in response.json()["detail"]


def test_other_validation_errors_stay_422() -> None:
    """A payload missing a field is still FastAPI's usual 422."""
    response = client.post("/api/v1/ui/validate", json={"content": "x"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "filename"]


def test_max_active_jobs_reads_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset means the default; anything but a positive integer is refused."""
    from pain001.api.job_manager import (
        DEFAULT_MAX_ACTIVE_JOBS,
        max_active_jobs,
    )

    monkeypatch.delenv("PAIN001_MAX_ACTIVE_JOBS", raising=False)
    assert max_active_jobs() == DEFAULT_MAX_ACTIVE_JOBS
    monkeypatch.setenv("PAIN001_MAX_ACTIVE_JOBS", "7")
    assert max_active_jobs() == 7
    monkeypatch.setenv("PAIN001_MAX_ACTIVE_JOBS", "0")
    with pytest.raises(ValueError, match="PAIN001_MAX_ACTIVE_JOBS"):
        max_active_jobs()


def test_stale_and_evicted_snapshots_are_not_written() -> None:
    """An older snapshot never replaces a newer one or revives an eviction."""
    store = _RecordingStore({})
    manager = JobManager(store=store)
    job_id = manager.create_job()
    with manager._lock:
        older = manager._snapshot(job_id)
        newer = manager._snapshot(job_id)
    manager._write(job_id, newer)
    manager._write(job_id, older)
    assert newer is not None and store.saved[job_id] == newer[1]
    manager.update_status(job_id, JobStatus.SUCCESS, 100)
    with manager._lock:
        late = manager._snapshot(job_id)
    manager.cleanup_old_jobs(keep_count=0)
    manager._write(job_id, late)
    assert job_id not in store.saved


def test_create_job_at_capacity_deletes_what_it_evicts() -> None:
    """Hitting ``max_jobs`` evicts finished jobs from the store too."""
    store = _RecordingStore({})
    manager = JobManager(max_jobs=101, store=store)
    ids = [manager.create_job() for _ in range(101)]
    for job_id in ids:
        manager.update_status(job_id, JobStatus.SUCCESS, 100)
    manager.create_job()
    assert len(store.deleted) == 1


def test_file_store_ping(tmp_path: Path) -> None:
    """The file store answers while its directory exists."""
    store = FileJobStore(tmp_path / "jobs")
    store.ping()
    (tmp_path / "jobs").rmdir()
    with pytest.raises(OSError, match="unusable"):
        store.ping()


def test_redis_store_ping() -> None:
    """The Redis store pings its client."""
    import fakeredis

    from pain001.api.job_store import RedisJobStore

    RedisJobStore(client=fakeredis.FakeStrictRedis()).ping()


def test_metrics_rejects_a_wrong_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A metrics token with no header, or the wrong one, is a 401."""
    monkeypatch.setenv("PAIN001_METRICS_TOKEN", "scrape")
    assert client.get("/metrics").status_code == 401


@pytest.mark.parametrize("value", ["1", "true", "YES"])
def test_payment_volume_switch_values(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The opt-in accepts the usual truthy spellings, nothing else."""
    from pain001.api.metrics import payment_volume_enabled

    monkeypatch.setenv("PAIN001_METRICS_PAYMENT_VOLUME", value)
    assert payment_volume_enabled()
    monkeypatch.setenv("PAIN001_METRICS_PAYMENT_VOLUME", "0")
    assert not payment_volume_enabled()


class _Store:
    """A job store whose ``ping`` succeeds or fails on demand."""

    def __init__(self, healthy: bool) -> None:
        self.healthy = healthy

    def ping(self) -> None:
        if not self.healthy:
            raise ConnectionError("down")


def test_ready_checks_the_job_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """A store that answers is ``ok``; one that does not makes a 503."""
    from pain001.api.job_manager import job_manager

    monkeypatch.setattr(job_manager, "store", _Store(healthy=True))
    assert client.get("/api/v1/ready").json()["checks"]["job_store"] == "ok"
    monkeypatch.setattr(job_manager, "store", _Store(healthy=False))
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"templates": "ok", "job_store": "failed"},
    }
    monkeypatch.setattr(job_manager, "store", object())
    assert client.get("/api/v1/ready").json()["checks"]["job_store"] == "ok"


def test_ready_without_a_store_reports_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no job store configured the check is ``disabled``, not failed."""
    from pain001.api.job_manager import job_manager

    monkeypatch.setattr(job_manager, "store", None)
    body = client.get("/api/ready").json()
    assert body["checks"]["job_store"] == "disabled"


def test_ready_fails_when_a_template_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A missing bundled file makes the replica not ready."""
    from pain001.api import ops

    ops._check_templates.cache_clear()
    monkeypatch.setattr(ops, "TEMPLATES_DIR", tmp_path)
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["templates"] == "failed"
    # A failure is not remembered: the next probe checks again.
    monkeypatch.undo()
    assert client.get("/api/v1/ready").json()["checks"]["templates"] == "ok"


def test_mask_error_rules() -> None:
    """Rows are masked field by field; other fields are shown unchanged."""
    from pain001.api._redact import mask_error

    message, value = mask_error(
        "$", "'x' is a required property", {"debtor_account_IBAN": SAMPLE_IBAN}
    )
    assert SAMPLE_IBAN not in value and "DE07" in value
    assert message == "'x' is a required property"
    assert mask_error("$.payment_amount", "bad 'abc'", "abc") == (
        "bad 'abc'",
        "abc",
    )
    assert mask_error("$.debtor_name", "too short", "") == (
        "too short",
        "[REDACTED]",
    )


def test_rate_limiter_still_expires_old_hits_of_active_clients() -> None:
    """A client seen inside the window keeps its bucket, minus old hits."""
    from pain001.api.ratelimit import InProcessFixedWindowBackend

    now = [0.0]
    backend = InProcessFixedWindowBackend(2, 10.0, clock=lambda: now[0])
    backend.is_allowed("client")
    now[0] = 5.0
    backend.is_allowed("client")
    now[0] = 10.5
    assert backend.is_allowed("client")
    assert list(backend._hits["client"]) == [5.0, 10.5]


def test_body_limit_passes_non_body_messages() -> None:
    """A disconnect message is handed on without being counted."""
    from pain001.api.limits import BodyLimitMiddleware

    received: list[str] = []

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        received.append((await receive())["type"])

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    scope = {"type": "http", "headers": []}
    asyncio.run(BodyLimitMiddleware(inner)(scope, receive, None))
    assert received == ["http.disconnect"]


def test_install_uses_the_backend_the_environment_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``PAIN001_RATE_LIMIT_BACKEND=redis`` reaches the installed limiter."""
    from fastapi import FastAPI

    from pain001.api.ratelimit import (
        RedisFixedWindowBackend,
        install_rate_limiting,
    )

    monkeypatch.setenv("PAIN001_RATE_LIMIT", "5/minute")
    monkeypatch.setenv("PAIN001_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("PAIN001_RATE_LIMIT_REDIS_URL", "redis://127.0.0.1:1/0")
    fresh = FastAPI()
    install_rate_limiting(fresh)
    backend = fresh.user_middleware[0].kwargs.get("backend")
    assert isinstance(backend, RedisFixedWindowBackend)
