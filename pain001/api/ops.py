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

"""Operator endpoints: ``/metrics``, ``/api/v1/ready``, ``/api/reference``.

``/metrics`` takes a bearer token whenever the API has one:
``PAIN001_METRICS_TOKEN`` when set (a scraper credential that cannot
call the payment routes), else ``PAIN001_API_KEY``. With neither set it
stays open, like the rest of an unauthenticated server.

``/api/v1/ready`` says whether this replica can do its work: every
bundled template and XSD loads, and the job store (a directory or
Redis), when one is configured, answers. It returns ``503`` otherwise,
so a load balancer stops routing to the replica. ``/api/v1/health``
stays a liveness check and does not look at dependencies.
"""

from __future__ import annotations

import functools
import logging
import os
from collections.abc import Callable

from defusedxml import ElementTree as defused_et
from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from pain001 import __version__
from pain001.api.auth import check_bearer, require_api_key
from pain001.api.job_manager import job_manager
from pain001.api.meta import SCALAR_HTML
from pain001.api.metrics import render_prometheus
from pain001.api.models import ReadyResponse
from pain001.constants import TEMPLATES_DIR, valid_xml_types

logger = logging.getLogger(__name__)

METRICS_AUTH_ENV = "PAIN001_METRICS_TOKEN"
"""Environment variable holding a bearer token for ``/metrics`` only."""


def require_metrics_token(
    authorization: str | None = Header(default=None),
) -> None:
    """Guard ``/metrics`` with its own token, or the API key.

    Answers ``401`` (through :func:`check_bearer`) when a token or key
    is configured and the header does not carry it.

    Args:
        authorization: The raw ``Authorization`` header, if any.
    """
    expected = os.environ.get(METRICS_AUTH_ENV)
    if expected:
        check_bearer(
            authorization, expected, "Invalid or missing metrics token"
        )
    else:
        require_api_key(authorization)


metrics_router = APIRouter()


@metrics_router.get(
    "/metrics",
    include_in_schema=False,
    dependencies=[Depends(require_metrics_token)],
)
async def metrics() -> PlainTextResponse:
    """Expose Prometheus metrics (build info, gauges, request counters).

    Returns:
        The metrics document in Prometheus text exposition format.
    """
    return PlainTextResponse(render_prometheus(__version__))


@metrics_router.get("/api/reference", include_in_schema=False)
async def scalar_reference() -> HTMLResponse:
    """Serve an interactive Scalar API reference for the OpenAPI document.

    Returns:
        The Scalar reference UI as an HTML response.
    """
    return HTMLResponse(SCALAR_HTML)


@functools.cache
def _check_templates() -> None:
    """Load every bundled template and XSD once; remember success.

    A missing or unreadable file raises :class:`OSError`; one that is not
    XML raises the parser's ``ParseError``. ``functools.cache`` keeps only
    a successful return, so a failed check is retried on the next probe.
    """
    for message_type in valid_xml_types:
        base = TEMPLATES_DIR / message_type
        defused_et.parse(str(base / "template.xml"))
        defused_et.parse(str(base / f"{message_type}.xsd"))


def _check_job_store() -> None:
    """Ask the configured job store whether it answers.

    A third-party store without a ``ping`` method counts as reachable.
    """
    ping = getattr(job_manager.store, "ping", None)
    if ping is not None:
        ping()


def _outcome(check: Callable[[], None], name: str) -> str:
    """Run one readiness check.

    Args:
        check: The check; it raises when the dependency is unusable.
        name: The check's name, for the log.

    Returns:
        ``ok`` or ``failed``. The reason is logged, never returned.
    """
    try:
        check()
    except Exception:  # noqa: BLE001 - any failure means not ready
        logger.warning("Readiness check %s failed", name, exc_info=True)
        return "failed"
    return "ok"


ready_router = APIRouter()


@ready_router.get(
    "/ready",
    response_model=ReadyResponse,
    tags=["Health"],
    summary="Readiness check",
    responses={
        503: {"model": ReadyResponse, "description": "Not ready"},
    },
)
def ready() -> JSONResponse:
    """Report whether this replica can validate and generate.

    Runs in the thread pool: a job-store ping is blocking I/O.

    Returns:
        ``200`` with ``status=ready`` when every check passes, else
        ``503`` with ``status=not_ready``; ``checks`` names each result.
    """
    checks = {"templates": _outcome(_check_templates, "templates")}
    checks["job_store"] = (
        "disabled"
        if job_manager.store is None
        else _outcome(_check_job_store, "job_store")
    )
    is_ready = "failed" not in checks.values()
    body = ReadyResponse(
        status="ready" if is_ready else "not_ready", checks=checks
    )
    return JSONResponse(
        body.model_dump(),
        status_code=status.HTTP_200_OK
        if is_ready
        else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
