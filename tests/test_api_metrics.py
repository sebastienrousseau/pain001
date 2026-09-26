# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Tests for the Prometheus metrics registry, middleware, and endpoint."""

import pytest

from pain001.constants import valid_xml_types

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
        assert (
            f"pain001_supported_message_types {len(valid_xml_types)}" in body
        )
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


class TestPrometheusObservabilityEngine:
    """Tests for the standard Prometheus observability engine."""

    def test_observe_and_render_summaries(self) -> None:
        """Summaries calculate quantiles, count, and sum correctly."""
        reg = MetricsRegistry()
        for i in range(1, 101):
            reg.observe(
                "pain001_processing_seconds",
                i / 100.0,
                {"message_type": "pain.001.001.03"},
            )

        lines = reg.render_summaries("pain001_processing_seconds")
        assert any('quantile="0.5"' in ln for ln in lines)
        assert any('quantile="0.95"' in ln for ln in lines)
        assert any('quantile="0.99"' in ln for ln in lines)
        assert any("pain001_processing_seconds_count{" in ln for ln in lines)
        assert any("pain001_processing_seconds_sum{" in ln for ln in lines)

        # Filter by different metric name returns empty
        assert reg.render_summaries("non_existent") == []

    def test_summary_single_sample(self) -> None:
        """Single sample sets all quantiles to that sample value."""
        reg = MetricsRegistry()
        reg.observe("latency", 0.042)
        lines = reg.render_summaries("latency")
        assert 'latency{quantile="0.5"} 0.042' in lines
        assert 'latency{quantile="0.95"} 0.042' in lines
        assert 'latency{quantile="0.99"} 0.042' in lines
        assert "latency_count 1" in lines
        assert "latency_sum 0.042" in lines

    def test_summary_max_samples_cap(self) -> None:
        """Samples list is bounded to 10000 items."""
        reg = MetricsRegistry()
        for _ in range(10005):
            reg.observe("latency", 1.0)
        key = ("latency", ())
        assert len(reg._summaries[key]) == 10000
        assert reg._summary_counts[key] == 10005

    def test_record_file_processed_and_payment_volume(self) -> None:
        """Convenience helpers record appropriate labels and values."""
        reg = MetricsRegistry()
        reg.record_file_processed("success", "pain.001.001.03")
        reg.record_payment_volume("EUR", 125050)
        reg.record_processing_seconds(0.123)

        assert (
            'pain001_files_processed_total{message_type="pain.001.001.03",status="success"} 1.0'
            in reg.render("pain001_files_processed_total")
        )
        assert (
            'pain001_payment_volume_cents_total{currency="EUR"} 125050.0'
            in reg.render("pain001_payment_volume_cents_total")
        )

    def test_record_data_volumes_aggregation(self) -> None:
        """Volume aggregation extracts cents across currencies and skips bad rows."""
        reg = MetricsRegistry()
        data = [
            {"payment_amount": "100.50", "currency": "EUR"},
            {"amount": "250.25", "currency": "USD"},
            {"instructed_amount": "50.00"},  # defaults to EUR
            {"payment_amount": ""},  # empty skipped
            {"payment_amount": "invalid"},  # invalid skipped
            {"payment_amount": "-10.00"},  # non-positive skipped
        ]
        reg.record_data_volumes(data)

        lines = reg.render("pain001_payment_volume_cents_total")
        assert (
            'pain001_payment_volume_cents_total{currency="EUR"} 15050.0'
            in lines
        )
        assert (
            'pain001_payment_volume_cents_total{currency="USD"} 25025.0'
            in lines
        )

    def test_render_prometheus_full_exposition(self) -> None:
        """render_prometheus emits standard headers and series."""
        registry.reset()
        registry.record_file_processed("success", "pain.001.001.03")
        registry.record_payment_volume("EUR", 50000)
        registry.record_processing_seconds(0.05)
        registry.inc("custom_counter", {"tag": "val"}, 3.0)

        body = render_prometheus("0.0.72")
        assert "# HELP pain001_files_processed_total" in body
        assert "# TYPE pain001_files_processed_total counter" in body
        assert "# HELP pain001_payment_volume_cents_total" in body
        assert "# TYPE pain001_payment_volume_cents_total counter" in body
        assert "# HELP pain001_processing_seconds" in body
        assert "# TYPE pain001_processing_seconds summary" in body
        assert "# TYPE custom_counter counter" in body
        assert 'custom_counter{tag="val"} 3.0' in body

    def test_generate_endpoint_records_metrics(self) -> None:
        """Calling /api/generate updates processed files, volume, and latency."""
        import os

        registry.reset()
        res = client.post(
            "/api/generate",
            json={
                "data_source": "csv",
                "file_path": "pain001/templates/pain.001.001.03/template.csv",
                "message_type": "pain.001.001.03",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        if data["file_path"] and os.path.exists(data["file_path"]):
            os.remove(data["file_path"])

        body = client.get("/metrics").text
        assert (
            'pain001_files_processed_total{message_type="pain.001.001.03",status="success"} 1.0'
            in body
        )
        assert 'pain001_payment_volume_cents_total{currency="EUR"}' in body
        assert "pain001_processing_seconds_count" in body

    def test_generate_endpoint_failure_records_metric(self) -> None:
        """Failed generation increments pain001_files_processed_total with status=failure."""
        registry.reset()
        res = client.post(
            "/api/generate",
            json={
                "data_source": "csv",
                "file_path": "non_existent_file.csv",
                "message_type": "pain.001.001.03",
            },
        )
        assert res.status_code == 404
        body = client.get("/metrics").text
        assert (
            'pain001_files_processed_total{message_type="pain.001.001.03",status="failure"} 1.0'
            in body
        )
