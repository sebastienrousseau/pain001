# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Byte-level contract of the Prometheus exposition and its registry.

A scraper parses ``GET /metrics`` line by line, so the HELP and TYPE
annotations, the label sets, the sample order and the summary maths
are part of the API. These tests pin the exact text rather than a
substring of it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest

from pain001.api import metrics as metrics_module
from pain001.api.job_manager import JobResult, JobStatus, job_manager
from pain001.api.metrics import MetricsMiddleware, MetricsRegistry, registry
from pain001.constants import valid_xml_types
from pain001.validation.schemes import PROFILES


@pytest.fixture
def clean_registry() -> Iterator[MetricsRegistry]:
    """Yield the shared registry empty, and leave it empty afterwards."""
    registry.reset()
    yield registry
    registry.reset()


def _jobs(*statuses: JobStatus) -> dict[str, JobResult]:
    """Build an in-memory job table holding one job per given status."""
    return {
        f"job-{i}": JobResult(f"job-{i}", status)
        for i, status in enumerate(statuses)
    }


def test_full_exposition_is_byte_exact(
    clean_registry: MetricsRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole document, in order, with every annotation and sample.

    The payment-volume counter is recorded but opted out, so it appears
    nowhere; a second summary stays out of the processing-seconds block.
    """
    monkeypatch.delenv(metrics_module.PAYMENT_VOLUME_ENV, raising=False)
    monkeypatch.setattr(
        job_manager,
        "jobs",
        _jobs(JobStatus.PENDING, JobStatus.PENDING, JobStatus.SUCCESS),
    )
    clean_registry.inc(
        "pain001_http_requests_total", {"method": "GET", "status": "200"}
    )
    clean_registry.record_file_processed("success", "pain.001.001.03")
    clean_registry.record_payment_volume("eur", 100)
    clean_registry.record_processing_seconds(0.25)
    clean_registry.observe("other_seconds", 9.0)
    clean_registry.inc("zz_custom_total", {"tag": "v"}, 3.0)

    body = metrics_module.render_prometheus("9.8.7")
    assert body.splitlines() == _expected_gauges() + _expected_rest()
    assert body.endswith("\n")


def _expected_gauges() -> list[str]:
    """Return the gauge section expected for version 9.8.7."""
    return [
        "# HELP pain001_build_info Build information.",
        "# TYPE pain001_build_info gauge",
        'pain001_build_info{version="9.8.7"} 1',
        "# HELP pain001_supported_message_types Supported message types.",
        "# TYPE pain001_supported_message_types gauge",
        f"pain001_supported_message_types {len(valid_xml_types)}",
        "# HELP pain001_scheme_profiles Registered scheme profiles.",
        "# TYPE pain001_scheme_profiles gauge",
        f"pain001_scheme_profiles {len(PROFILES)}",
        "# HELP pain001_jobs Async jobs by status.",
        "# TYPE pain001_jobs gauge",
        'pain001_jobs{status="pending"} 2',
        'pain001_jobs{status="processing"} 0',
        'pain001_jobs{status="success"} 1',
        'pain001_jobs{status="failed"} 0',
        'pain001_jobs{status="cancelled"} 0',
    ]


def _expected_rest() -> list[str]:
    """Return the counter and summary sections that follow the gauges."""
    return [
        "# HELP pain001_http_requests_total HTTP requests by method/status.",
        "# TYPE pain001_http_requests_total counter",
        'pain001_http_requests_total{method="GET",status="200"} 1.0',
        "# HELP pain001_files_processed_total "
        + "Files processed by status and message type.",
        "# TYPE pain001_files_processed_total counter",
        "pain001_files_processed_total"
        + '{message_type="pain.001.001.03",status="success"} 1.0',
        "# HELP pain001_processing_seconds Payment generation processing "
        + "latency in seconds.",
        "# TYPE pain001_processing_seconds summary",
        'pain001_processing_seconds{quantile="0.5"} 0.25',
        'pain001_processing_seconds{quantile="0.95"} 0.25',
        'pain001_processing_seconds{quantile="0.99"} 0.25',
        "pain001_processing_seconds_sum 0.25",
        "pain001_processing_seconds_count 1",
        "# TYPE zz_custom_total counter",
        'zz_custom_total{tag="v"} 3.0',
    ]


def test_volume_counter_is_documented_when_opted_in(
    clean_registry: MetricsRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the opt-in set, the volume counter gets HELP and TYPE lines."""
    monkeypatch.setenv(metrics_module.PAYMENT_VOLUME_ENV, " Yes ")
    clean_registry.record_payment_volume("usd", 5)
    lines = metrics_module.render_prometheus("1").splitlines()
    start = lines.index(
        "# HELP pain001_payment_volume_cents_total "
        "Payment volume in cents by currency."
    )
    assert lines[start + 1 : start + 3] == [
        "# TYPE pain001_payment_volume_cents_total counter",
        'pain001_payment_volume_cents_total{currency="USD"} 5.0',
    ]


def test_render_orders_samples_by_name_not_value() -> None:
    """Counter samples come out sorted by metric name and labels."""
    reg = MetricsRegistry()
    reg.inc("b_total", value=1)
    reg.inc("a_total", value=5)
    assert reg.render() == ["a_total 5.0", "b_total 1.0"]


def test_summaries_sort_by_name_and_filter() -> None:
    """Summaries sort by name, not insertion or samples, and filter."""
    reg = MetricsRegistry()
    reg.observe("b_seconds", 1.0)
    reg.observe("a_seconds", 2.0)
    names = [ln.split("{")[0].split(" ")[0] for ln in reg.render_summaries()]
    assert names == ["a_seconds"] * 3 + [
        "a_seconds_sum",
        "a_seconds_count",
    ] + ["b_seconds"] * 3 + ["b_seconds_sum", "b_seconds_count"]
    assert reg.render_summaries("b_seconds", quantiles=(0.5,)) == [
        'b_seconds{quantile="0.5"} 1.0',
        "b_seconds_sum 1.0",
        "b_seconds_count 1",
    ]


def test_summary_quantiles_interpolate_linearly() -> None:
    """Quantiles interpolate between neighbouring sorted samples."""
    reg = MetricsRegistry()
    for value in (16.0, 1.0, 8.0, 2.0, 4.0):
        reg.observe("lat", value)
    lines = reg.render_summaries("lat", quantiles=(0.3, 0.5, 0.95, 1.0))
    # Sorted samples 1, 2, 4, 8, 16; rank = (n - 1) * q.
    assert lines == [
        'lat{quantile="0.3"} 2.4',  # rank 1.2: 2 + 0.2 * (4 - 2)
        'lat{quantile="0.5"} 4.0',  # rank 2.0
        'lat{quantile="0.95"} 14.4',  # rank 3.8: 8 + 0.8 * (16 - 8)
        'lat{quantile="1.0"} 16.0',  # rank 4.0: the maximum
        "lat_sum 31.0",
        "lat_count 5",
    ]


def test_summary_of_two_samples_interpolates() -> None:
    """Two samples already interpolate; the median is their midpoint."""
    reg = MetricsRegistry()
    reg.observe("lat", 1.0)
    reg.observe("lat", 3.0)
    assert reg.render_summaries("lat", quantiles=(0.5,))[0] == (
        'lat{quantile="0.5"} 2.0'
    )


def test_summary_rounds_to_six_places() -> None:
    """Quantile and sum samples are rounded to six decimal places."""
    reg = MetricsRegistry()
    reg.observe("lat", 1 / 3)
    assert reg.render_summaries("lat", quantiles=(0.5,)) == [
        'lat{quantile="0.5"} 0.333333',
        "lat_sum 0.333333",
        "lat_count 1",
    ]


def test_processing_seconds_keep_their_labels() -> None:
    """Labels passed to record_processing_seconds reach the summary."""
    reg = MetricsRegistry()
    reg.record_processing_seconds(0.5, {"message_type": "pain.001.001.09"})
    reg.record_processing_seconds(0.25, {"message_type": "pain.001.001.09"})
    assert reg.render_summaries(quantiles=()) == [
        'pain001_processing_seconds_sum{message_type="pain.001.001.09"} 0.75',
        'pain001_processing_seconds_count{message_type="pain.001.001.09"} 2',
    ]


def test_record_data_volumes_skips_rows_without_stopping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty, unparseable and zero rows are skipped; later rows count."""
    monkeypatch.setenv(metrics_module.PAYMENT_VOLUME_ENV, "true")
    reg = MetricsRegistry()
    reg.record_data_volumes(
        [
            {"currency": "USD"},
            {"amount": "not-a-number", "currency": "USD"},
            {"amount": "0", "currency": "GBP"},
            {"amount": "0.01", "currency": "USD"},
            {"amount": "2.00"},
        ]
    )
    assert reg.render() == [
        'pain001_payment_volume_cents_total{currency="EUR"} 200.0',
        'pain001_payment_volume_cents_total{currency="USD"} 1.0',
    ]


async def _run_middleware(
    scope: dict[str, Any], inner: Any
) -> list[dict[str, Any]]:
    """Drive MetricsMiddleware once and return what reached ``send``."""
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b""}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await MetricsMiddleware(inner)(scope, receive, send)
    return sent


def test_middleware_labels_method_and_status(
    clean_registry: MetricsRegistry,
) -> None:
    """The request's method and response status label the counter."""

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 201})
        await send({"type": "http.response.body", "body": b""})

    sent = asyncio.run(
        _run_middleware({"type": "http", "method": "POST"}, inner)
    )
    assert [m["type"] for m in sent] == [
        "http.response.start",
        "http.response.body",
    ]
    assert clean_registry.render() == [
        'pain001_http_requests_total{method="POST",status="201"} 1.0'
    ]


def test_middleware_defaults_when_nothing_is_known(
    clean_registry: MetricsRegistry,
) -> None:
    """No method in the scope reads GET; no response start reads 0."""

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        return None

    asyncio.run(_run_middleware({"type": "http"}, inner))
    assert clean_registry.render() == [
        'pain001_http_requests_total{method="GET",status="0"} 1.0'
    ]
