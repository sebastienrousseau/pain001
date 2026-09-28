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

"""Dependency-free Prometheus metrics for the Pain001 REST API.

A tiny in-process counter registry plus an ASGI middleware that counts HTTP
requests by method and status. :func:`render_prometheus` renders the
counters together with build info and live gauges (supported message types,
scheme profiles, and async jobs by status) in the Prometheus text exposition
format, served at ``GET /metrics``.

This is a single-process exporter — sufficient for one API node. Scraped
behind a gateway or aggregated with a push-gateway for multi-node setups.
"""

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_Labels = tuple[tuple[str, str], ...]


class MetricsRegistry:
    """A minimal counter and summary registry rendering Prometheus text format."""

    def __init__(self) -> None:
        self._counters: dict[tuple[str, _Labels], float] = defaultdict(float)
        self._summaries: dict[tuple[str, _Labels], list[float]] = defaultdict(
            list
        )
        self._summary_counts: dict[tuple[str, _Labels], int] = defaultdict(int)
        self._summary_sums: dict[tuple[str, _Labels], float] = defaultdict(
            float
        )

    def inc(
        self,
        name: str,
        labels: dict[str, str] | None = None,
        value: float = 1.0,
    ) -> None:
        """Increment a counter.

        Args:
            name: Metric name (Prometheus convention, e.g. ``foo_total``).
            labels: Optional label set.
            value: Amount to add (default 1).
        """
        key = (name, tuple(sorted((labels or {}).items())))
        self._counters[key] += value

    def observe(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Observe a value in a summary metric.

        Args:
            name: Summary metric name (e.g. ``pain001_processing_seconds``).
            value: Numeric observation to record.
            labels: Optional label set.
        """
        key = (name, tuple(sorted((labels or {}).items())))
        samples = self._summaries[key]
        samples.append(value)
        if len(samples) > 10000:
            samples.pop(0)
        self._summary_counts[key] += 1
        self._summary_sums[key] += value

    def reset(self) -> None:
        """Clear all counters and summaries (used by tests)."""
        self._counters.clear()
        self._summaries.clear()
        self._summary_counts.clear()
        self._summary_sums.clear()

    def render(self, metric_name: str | None = None) -> list[str]:
        """Render the counters as Prometheus exposition lines.

        Args:
            metric_name: Optional metric name filter.

        Returns:
            One text line per counter sample.
        """
        lines: list[str] = []
        for (name, labels), value in sorted(
            self._counters.items(), key=lambda kv: kv[0]
        ):
            if metric_name is not None and name != metric_name:
                continue
            lines.append(f"{name}{_format_labels(dict(labels))} {value}")
        return lines

    def render_summaries(
        self,
        metric_name: str | None = None,
        quantiles: tuple[float, ...] = (0.5, 0.95, 0.99),
    ) -> list[str]:
        """Render summaries with quantiles, sum, and count samples.

        Args:
            metric_name: Optional metric name filter.
            quantiles: Quantiles to calculate and render.

        Returns:
            Text lines for the summary quantiles, sum, and count.
        """
        lines: list[str] = []
        for (name, labels), samples in sorted(
            self._summaries.items(), key=lambda kv: kv[0]
        ):
            if metric_name is not None and name != metric_name:
                continue
            sorted_samples = sorted(samples)
            n = len(sorted_samples)
            base_labels = dict(labels)
            for q in quantiles:
                val = 0.0
                if n == 1:
                    val = sorted_samples[0]
                elif n > 1:
                    rank = (n - 1) * q
                    low = int(rank)
                    frac = rank - low
                    high = min(low + 1, n - 1)
                    val = sorted_samples[low] + frac * (
                        sorted_samples[high] - sorted_samples[low]
                    )
                q_labels = {**base_labels, "quantile": str(q)}
                lines.append(
                    f"{name}{_format_labels(q_labels)} {round(val, 6)}"
                )
            total_sum = self._summary_sums[(name, labels)]
            total_count = self._summary_counts[(name, labels)]
            lines.append(
                f"{name}_sum{_format_labels(base_labels)} {round(total_sum, 6)}"
            )
            lines.append(
                f"{name}_count{_format_labels(base_labels)} {total_count}"
            )
        return lines

    def record_file_processed(self, status: str, message_type: str) -> None:
        """Record a file processing completion counter.

        Args:
            status: Processing status ('success' or 'failure').
            message_type: ISO 20022 message definition identifier.
        """
        self.inc(
            "pain001_files_processed_total",
            {"status": status, "message_type": message_type},
        )

    def record_payment_volume(self, currency: str, cents: int | float) -> None:
        """Record payment amount volume in cents.

        Args:
            currency: Three-letter ISO 4217 currency code.
            cents: Amount in smallest currency units (cents).
        """
        self.inc(
            "pain001_payment_volume_cents_total",
            {"currency": currency.upper()},
            value=float(cents),
        )

    def record_processing_seconds(
        self,
        seconds: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record processing duration in seconds into summary.

        Args:
            seconds: Processing time elapsed in seconds.
            labels: Optional label set.
        """
        self.observe("pain001_processing_seconds", seconds, labels)

    def record_data_volumes(self, data: list[dict[str, Any]]) -> None:
        """Extract and record payment volumes in cents by currency from rows.

        Args:
            data: List of payment record dictionaries.
        """
        for row in data:
            amt_raw = (
                row.get("payment_amount")
                or row.get("amount")
                or row.get("instructed_amount")
            )
            if amt_raw is None or amt_raw == "":
                continue
            try:
                amt_dec = Decimal(str(amt_raw).strip())
                cents = int(round(amt_dec * 100))
                if cents > 0:
                    ccy = str(row.get("currency") or "EUR").strip().upper()
                    self.record_payment_volume(ccy, cents)
            except (InvalidOperation, ValueError, TypeError):
                continue


def _format_labels(labels: dict[str, str]) -> str:
    """Format a label set as a Prometheus label clause.

    Args:
        labels: The label set (possibly empty).

    Returns:
        A ``{k="v",...}`` clause, or an empty string when there are none.
    """
    if not labels:
        return ""
    inner = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return "{" + inner + "}"


# Module-level registry shared by the middleware and the endpoint.
registry = MetricsRegistry()


class MetricsMiddleware:
    """ASGI middleware counting HTTP requests by method and status.

    Args:
        app: The wrapped ASGI application.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Count the request, then delegate to the wrapped app.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "GET")
        status_holder = {"code": 0}

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = int(message["status"])
            await send(message)

        await self.app(scope, receive, _send)
        registry.inc(
            "pain001_http_requests_total",
            {"method": method, "status": str(status_holder["code"])},
        )


def render_prometheus(version: str) -> str:
    """Render the full metrics document in Prometheus text format.

    Args:
        version: The running package version (for ``pain001_build_info``).

    Returns:
        The complete exposition body (ending with a trailing newline).
    """
    from pain001.api.job_manager import JobStatus, job_manager
    from pain001.constants import valid_xml_types
    from pain001.validation.schemes import PROFILES

    lines: list[str] = []

    lines.append("# HELP pain001_build_info Build information.")
    lines.append("# TYPE pain001_build_info gauge")
    lines.append(f'pain001_build_info{{version="{version}"}} 1')

    lines.append(
        "# HELP pain001_supported_message_types Supported message types."
    )
    lines.append("# TYPE pain001_supported_message_types gauge")
    lines.append(f"pain001_supported_message_types {len(valid_xml_types)}")

    lines.append("# HELP pain001_scheme_profiles Registered scheme profiles.")
    lines.append("# TYPE pain001_scheme_profiles gauge")
    lines.append(f"pain001_scheme_profiles {len(PROFILES)}")

    lines.append("# HELP pain001_jobs Async jobs by status.")
    lines.append("# TYPE pain001_jobs gauge")
    counts = dict.fromkeys(JobStatus, 0)
    for job in job_manager.jobs.values():
        counts[job.status] += 1
    for status, count in counts.items():
        lines.append(f'pain001_jobs{{status="{status.value}"}} {count}')

    lines.append(
        "# HELP pain001_http_requests_total HTTP requests by method/status."
    )
    lines.append("# TYPE pain001_http_requests_total counter")
    lines.extend(registry.render("pain001_http_requests_total"))

    lines.append(
        "# HELP pain001_files_processed_total Files processed by status and message type."
    )
    lines.append("# TYPE pain001_files_processed_total counter")
    lines.extend(registry.render("pain001_files_processed_total"))

    lines.append(
        "# HELP pain001_payment_volume_cents_total Payment volume in cents by currency."
    )
    lines.append("# TYPE pain001_payment_volume_cents_total counter")
    lines.extend(registry.render("pain001_payment_volume_cents_total"))

    lines.append(
        "# HELP pain001_processing_seconds Payment generation processing latency in seconds."
    )
    lines.append("# TYPE pain001_processing_seconds summary")
    lines.extend(registry.render_summaries("pain001_processing_seconds"))

    known_counters = {
        "pain001_http_requests_total",
        "pain001_files_processed_total",
        "pain001_payment_volume_cents_total",
    }
    for name in sorted(
        {n for n, _ in registry._counters if n not in known_counters}
    ):
        lines.append(f"# TYPE {name} counter")
        lines.extend(registry.render(name))

    return "\n".join(lines) + "\n"
