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

"""Tests for the Prometheus metrics registry, middleware, and endpoint."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from pain001.api.app import app  # noqa: E402
from pain001.api.metrics import (  # noqa: E402
    MetricsRegistry,
    registry,
    render_prometheus,
)

client = TestClient(app)


class TestMetricsRegistry:
    """The minimal counter registry."""

    def test_inc_and_render(self) -> None:
        """Counters accumulate and render with sorted labels."""
        reg = MetricsRegistry()
        reg.inc("reqs_total", {"method": "GET", "status": "200"})
        reg.inc("reqs_total", {"method": "GET", "status": "200"})
        reg.inc("reqs_total", {"method": "POST", "status": "201"})
        lines = reg.render()
        assert 'reqs_total{method="GET",status="200"} 2.0' in lines
        assert 'reqs_total{method="POST",status="201"} 1.0' in lines

    def test_unlabelled_counter(self) -> None:
        """A counter without labels renders with no label clause."""
        reg = MetricsRegistry()
        reg.inc("widgets", value=5)
        assert reg.render() == ["widgets 5.0"]

    def test_reset(self) -> None:
        """reset clears all counters."""
        reg = MetricsRegistry()
        reg.inc("x")
        reg.reset()
        assert reg.render() == []


class TestRenderPrometheus:
    """The full exposition document."""

    def test_includes_core_series(self) -> None:
        """Build info and the live gauges are present."""
        body = render_prometheus("9.9.9")
        assert 'pain001_build_info{version="9.9.9"} 1' in body
        assert "pain001_supported_message_types 12" in body
        # v0.0.53 added the sepa-b2b profile (issue #173); the count
        # now reflects PROFILES rather than a hard-coded number.
        from pain001.validation.schemes import PROFILES

        assert f"pain001_scheme_profiles {len(PROFILES)}" in body
        assert 'pain001_jobs{status="success"}' in body
        assert body.endswith("\n")

    def test_has_help_and_type_lines(self) -> None:
        """Each metric carries HELP/TYPE annotations."""
        body = render_prometheus("1.2.3")
        assert "# HELP pain001_build_info" in body
        assert "# TYPE pain001_jobs gauge" in body

    def test_job_gauge_reflects_live_jobs(self) -> None:
        """A created job is counted under its status gauge."""
        from pain001.api.job_manager import job_manager

        job_id = job_manager.create_job()
        try:
            body = render_prometheus("1.0.0")
            pending = next(
                ln
                for ln in body.splitlines()
                if ln.startswith('pain001_jobs{status="pending"}')
            )
            assert int(pending.rsplit(" ", 1)[1]) >= 1
        finally:
            job_manager.jobs.pop(job_id, None)


class TestMetricsEndpoint:
    """The /metrics HTTP endpoint and request-counting middleware."""

    def test_endpoint_served_as_text(self) -> None:
        """/metrics returns Prometheus text."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "pain001_build_info" in response.text

    def test_requests_are_counted(self) -> None:
        """The middleware increments the request counter per call."""
        registry.reset()
        client.get("/api/v1/health")
        client.get("/api/v1/health")
        body = client.get("/metrics").text
        line = next(
            ln
            for ln in body.splitlines()
            if ln.startswith("pain001_http_requests_total")
            and 'status="200"' in ln
        )
        # Two health probes (the /metrics GET is counted after rendering).
        assert float(line.rsplit(" ", 1)[1]) >= 2.0

    def test_endpoint_hidden_from_schema(self) -> None:
        """/metrics is not advertised in the OpenAPI document."""
        assert "/metrics" not in client.get("/openapi.json").json()["paths"]

    def test_non_http_scope_passes_through(self) -> None:
        """The middleware forwards non-HTTP scopes without counting."""
        import asyncio

        from pain001.api.metrics import MetricsMiddleware

        seen = {}

        async def downstream(scope, receive, send) -> None:
            seen["type"] = scope["type"]

        mw = MetricsMiddleware(downstream)
        asyncio.run(mw({"type": "lifespan"}, None, None))
        assert seen["type"] == "lifespan"
