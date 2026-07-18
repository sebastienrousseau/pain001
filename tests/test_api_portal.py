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

"""Tests for the REST API portal: versioning, rate limiting, persistence."""

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.responses import PlainTextResponse  # noqa: E402

from pain001.api.app import _install_rate_limiting, app  # noqa: E402
from pain001.api.job_manager import JobManager, JobStatus  # noqa: E402
from pain001.api.job_store import (  # noqa: E402
    FileJobStore,
    job_store_from_env,
)
from pain001.api.ratelimit import (  # noqa: E402
    RateLimitMiddleware,
    parse_rate_limit,
)

client = TestClient(app)


class TestMessageTypeParity:
    """The API's MessageType enum must cover every supported message type."""

    def test_enum_matches_constants(self) -> None:
        """No message type the library supports is missing from the API."""
        from pain001.api.models import MessageType
        from pain001.constants import valid_xml_types

        assert {m.value for m in MessageType} == set(valid_xml_types)

    def test_api_can_target_pain008_and_v12(self) -> None:
        """The two formerly-missing types are now accepted by the API."""
        from pain001.api.models import MessageType

        assert MessageType("pain.008.001.02")
        assert MessageType("pain.001.001.12")

    def test_every_type_has_a_usable_field_schema(self) -> None:
        """SchemaValidator constructs for every supported message type."""
        from pain001.constants import valid_xml_types
        from pain001.validation.schema_validator import SchemaValidator

        for message_type in valid_xml_types:
            assert SchemaValidator(message_type) is not None


class TestVersioning:
    """`/api/v1` is canonical; `/api` remains a hidden legacy alias."""

    def test_v1_health(self) -> None:
        """The versioned health route responds 200."""
        assert client.get("/api/v1/health").status_code == 200

    def test_legacy_health_alias(self) -> None:
        """The unversioned health route still responds 200."""
        assert client.get("/api/health").status_code == 200

    def test_schema_only_documents_v1(self) -> None:
        """Only the versioned paths appear in the OpenAPI document."""
        paths = client.get("/openapi.json").json()["paths"]
        assert "/api/v1/health" in paths
        assert "/api/health" not in paths

    def test_openapi_has_tag_metadata(self) -> None:
        """Tag descriptions are present for grouped docs/SDKs."""
        spec = client.get("/openapi.json").json()
        names = {t["name"] for t in spec.get("tags", [])}
        assert {"Health", "Validation", "Generation"} <= names

    def test_scalar_reference_served(self) -> None:
        """The interactive reference page renders Scalar."""
        resp = client.get("/api/reference")
        assert resp.status_code == 200
        assert "api-reference" in resp.text


class TestParseRateLimit:
    """`parse_rate_limit` spec parsing."""

    @pytest.mark.parametrize(
        "spec,expected",
        [
            ("100/minute", (100, 60.0)),
            ("5/second", (5, 1.0)),
            ("2/hour", (2, 3600.0)),
            ("10/day", (10, 86400.0)),
            ("7/minutes", (7, 60.0)),
            ("3", (3, 60.0)),
        ],
    )
    def test_valid_specs(self, spec, expected) -> None:
        """Valid specs parse to (count, window_seconds)."""
        assert parse_rate_limit(spec) == expected

    @pytest.mark.parametrize("spec", ["", "abc/minute", "0/minute", "5/year"])
    def test_invalid_specs(self, spec) -> None:
        """Malformed specs raise ValueError."""
        with pytest.raises(ValueError):
            parse_rate_limit(spec)


class TestRateLimitMiddleware:
    """The in-process fixed-window limiter."""

    def _app(self, max_requests, clock) -> FastAPI:
        """Build a tiny app guarded by the limiter.

        Args:
            max_requests: Requests allowed per window.
            clock: Injected monotonic clock.

        Returns:
            A configured FastAPI app.
        """
        tiny = FastAPI()

        @tiny.get("/ping")
        async def ping() -> PlainTextResponse:
            return PlainTextResponse("pong")

        tiny.add_middleware(
            RateLimitMiddleware,
            max_requests=max_requests,
            window_seconds=10.0,
            clock=clock,
        )
        return tiny

    def test_allows_within_limit(self) -> None:
        """Requests under the cap pass through."""
        c = TestClient(self._app(2, clock=lambda: 100.0))
        assert c.get("/ping").status_code == 200
        assert c.get("/ping").status_code == 200

    def test_blocks_over_limit(self) -> None:
        """The request exceeding the cap gets 429 with Retry-After."""
        c = TestClient(self._app(1, clock=lambda: 100.0))
        assert c.get("/ping").status_code == 200
        blocked = c.get("/ping")
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers

    def test_window_expiry_resets(self) -> None:
        """Hits older than the window are evicted, freeing capacity."""
        now = {"t": 100.0}
        c = TestClient(self._app(1, clock=lambda: now["t"]))
        assert c.get("/ping").status_code == 200
        assert c.get("/ping").status_code == 429
        now["t"] = 200.0  # advance past the 10s window
        assert c.get("/ping").status_code == 200

    def test_non_http_scope_passes_through(self) -> None:
        """A non-HTTP scope is forwarded untouched."""
        seen = {}

        async def downstream(scope, receive, send) -> None:
            seen["type"] = scope["type"]

        mw = RateLimitMiddleware(
            downstream, max_requests=1, window_seconds=1.0
        )
        import asyncio

        asyncio.run(mw({"type": "lifespan"}, None, None))
        assert seen["type"] == "lifespan"


class TestInstallRateLimiting:
    """`_install_rate_limiting` env wiring."""

    def test_noop_without_env(self, monkeypatch) -> None:
        """No middleware is added when the env var is unset."""
        monkeypatch.delenv("PAIN001_RATE_LIMIT", raising=False)
        fresh = FastAPI()
        before = len(fresh.user_middleware)
        _install_rate_limiting(fresh)
        assert len(fresh.user_middleware) == before

    def test_installs_with_env(self, monkeypatch) -> None:
        """The middleware is added when the env var is set."""
        monkeypatch.setenv("PAIN001_RATE_LIMIT", "100/minute")
        fresh = FastAPI()
        _install_rate_limiting(fresh)
        assert any(m.cls is RateLimitMiddleware for m in fresh.user_middleware)


class TestFileJobStore:
    """The durable file-backed job store."""

    def test_save_load_roundtrip(self, tmp_path) -> None:
        """A saved snapshot is read back by load_all."""
        store = FileJobStore(tmp_path / "jobs")
        store.save("abc", {"job_id": "abc", "status": "pending"})
        loaded = store.load_all()
        assert loaded["abc"]["status"] == "pending"

    def test_delete(self, tmp_path) -> None:
        """A deleted snapshot disappears from load_all."""
        store = FileJobStore(tmp_path)
        store.save("x", {"job_id": "x"})
        store.delete("x")
        assert "x" not in store.load_all()
        # Deleting a missing job is a no-op.
        store.delete("missing")

    @pytest.mark.parametrize(
        "bad_id",
        [
            "../../etc/passwd",
            "../secret",
            "a/b",
            "a\\b",
            ".hidden",
            "",
            "foo/../bar",
            "with space",
            "sub/../../escape",
        ],
    )
    def test_path_rejects_traversal_and_separators(
        self, tmp_path, bad_id
    ) -> None:
        """Unsafe job ids are rejected before a path is ever built."""
        store = FileJobStore(tmp_path)
        with pytest.raises(ValueError, match="Unsafe job id"):
            store.save(bad_id, {"job_id": bad_id})
        with pytest.raises(ValueError, match="Unsafe job id"):
            store.delete(bad_id)

    @pytest.mark.parametrize(
        "good_id",
        [
            "abc",
            "abc-123",
            "job_42",
            "550e8400-e29b-41d4-a716-446655440000",
            "A",
        ],
    )
    def test_path_accepts_valid_ids_and_stays_contained(
        self, tmp_path, good_id
    ) -> None:
        """Valid ids round-trip and their file stays inside the store dir."""
        store = FileJobStore(tmp_path)
        resolved = store._path(good_id)
        base = Path(tmp_path).resolve()
        assert resolved.parent == base
        assert resolved.name == f"{good_id}.json"
        store.save(good_id, {"job_id": good_id, "status": "pending"})
        assert store.load_all()[good_id]["status"] == "pending"

    def test_from_env_unset(self, monkeypatch) -> None:
        """No store is built when the env var is unset."""
        monkeypatch.delenv("PAIN001_JOB_STORE_DIR", raising=False)
        assert job_store_from_env() is None

    def test_from_env_set(self, monkeypatch, tmp_path) -> None:
        """A FileJobStore is built when the env var points at a dir."""
        monkeypatch.setenv("PAIN001_JOB_STORE_DIR", str(tmp_path))
        store = job_store_from_env()
        assert isinstance(store, FileJobStore)


class TestJobManagerPersistence:
    """JobManager write-through and rehydration via a store."""

    def test_jobs_survive_restart(self, tmp_path) -> None:
        """A job created under one manager is reloaded by the next."""
        store = FileJobStore(tmp_path)
        manager = JobManager(store=store)
        job_id = manager.create_job()
        manager.update_status(job_id, JobStatus.PROCESSING, progress=50)

        revived = JobManager(store=FileJobStore(tmp_path))
        assert job_id in revived.jobs
        assert revived.jobs[job_id].status == JobStatus.PROCESSING

    def test_cancel_is_persisted(self, tmp_path) -> None:
        """Cancellation is written through to the store."""
        store = FileJobStore(tmp_path)
        manager = JobManager(store=store)
        job_id = manager.create_job()
        assert manager.cancel_job(job_id) is True

        revived = JobManager(store=FileJobStore(tmp_path))
        assert revived.jobs[job_id].status == JobStatus.CANCELLED

    def test_in_memory_when_no_store(self) -> None:
        """Without a store, no persistence occurs and jobs work in memory."""
        manager = JobManager()
        job_id = manager.create_job()
        assert manager.get_job(job_id) is not None
