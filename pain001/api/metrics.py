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

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_Labels = tuple[tuple[str, str], ...]


class MetricsRegistry:
    """A minimal counter registry rendering Prometheus text format."""

    def __init__(self) -> None:
        self._counters: dict[tuple[str, _Labels], float] = defaultdict(float)

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

    def reset(self) -> None:
        """Clear all counters (used by tests)."""
        self._counters.clear()

    def render(self) -> list[str]:
        """Render the counters as Prometheus exposition lines.

        Returns:
            One text line per counter sample.
        """
        lines: list[str] = []
        for (name, labels), value in sorted(
            self._counters.items(), key=lambda kv: kv[0]
        ):
            lines.append(f"{name}{_format_labels(dict(labels))} {value}")
        return lines


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
    lines.extend(registry.render())

    return "\n".join(lines) + "\n"
