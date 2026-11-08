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

"""Pain001 FastAPI application."""

from __future__ import annotations

import asyncio
import functools
import logging
import os
import tempfile
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

from pain001 import __version__
from pain001.api._pipeline import (
    InputRefused,
    generate_pipeline,
    job_update,
    record_failure,
    record_outcome,
    reset_executor,
    run_pipeline,
    sync_response,
    validate_pipeline,
)
from pain001.api._startup import startup_checks
from pain001.api.auth import require_api_key as _require_api_key
from pain001.api.faces import faces_router
from pain001.api.guards import sanitise_message_type as _sanitise_message_type
from pain001.api.job_manager import JobStatus, job_manager, output_name
from pain001.api.meta import API_DESCRIPTION, SCALAR_HTML, TAGS_METADATA
from pain001.api.metrics import MetricsMiddleware, render_prometheus
from pain001.api.models import (
    GenerateXMLRequest,
    GenerateXMLResponse,
    HealthResponse,
    JobStatusResponse,
    ValidationRequest,
    ValidationResponse,
)
from pain001.api.ratelimit import RateLimitMiddleware, parse_rate_limit
from pain001.api.ui import ui_router
from pain001.constants import TEMPLATES_DIR
from pain001.exceptions import PaymentValidationError
from pain001.observability.otel import init_otel, traced
from pain001.security.path_validator import (
    PathValidationError,
    SecurityError,
    validate_path,
)

logger = logging.getLogger(__name__)

# References to in-flight background tasks. asyncio only keeps weak
# references to tasks, so without this set a running job could be
# garbage-collected mid-flight.
_background_tasks: set[asyncio.Task[None]] = set()


def _validate_safe_path(user_path: str, base_dir: Path | None = None) -> Path:
    """Validate and resolve path to prevent directory traversal attacks.

    Delegates to the centralized ``validate_path`` security module and
    converts library exceptions into appropriate HTTP responses.

    Args:
        user_path: User-provided path (potentially malicious).
        base_dir: Optional base directory to restrict access to.

    Returns:
        Resolved absolute Path object.

    Raises:
        HTTPException: If path is invalid or outside allowed directories.
    """
    try:
        validated = validate_path(
            user_path,
            must_exist=False,
            base_dir=str(base_dir) if base_dir else None,
        )
    except PathValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path",
        ) from e
    except SecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: path outside allowed directory",
        ) from e

    result = Path(validated)

    # Explicit startswith guard on the returned Path so CodeQL can link
    # the guard to all downstream uses of ``result`` (CWE-22 barrier).
    result_str = str(result)
    cwd_prefix = str(Path.cwd().resolve())
    tmp_prefix = str(Path(tempfile.gettempdir()).resolve())
    if not (  # pragma: no cover - CodeQL barrier; validate_path enforces it
        result_str == cwd_prefix
        or result_str.startswith(cwd_prefix + os.sep)
        or result_str == tmp_prefix
        or result_str.startswith(tmp_prefix + os.sep)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: path outside allowed directory",
        )
    return result


def _guarded_input_path(user_path: str) -> str:
    """Resolve a request's input file and refuse it unless usable.

    Args:
        user_path: The ``file_path`` the caller sent.

    Returns:
        The resolved path, inside the working directory, of a file
        that exists.

    Raises:
        InputRefused: ``403`` outside the working directory, ``404``
            when the file does not exist.
    """
    file_path = str(_validate_safe_path(user_path))
    # CodeQL CWE-22 guard: same variable for guard and sink
    if not file_path.startswith(str(Path.cwd().resolve()) + os.sep):
        raise InputRefused(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )
    if not os.path.exists(file_path):
        raise InputRefused(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )
    return file_path


def _gate_output_dir(user_dir: str | None) -> Path:
    """Validate ``user_dir`` against a fixed allow-list of safe roots.

    Uses the canonical ``os.path.realpath`` + ``os.path.commonpath``
    sanitiser pattern that the CodeQL Python ``py/path-injection`` query
    recognises. The candidate is canonicalised first, then the common
    prefix against each allowed root is verified to *equal* that root
    (anything else would be traversal).

    Args:
        user_dir: Optional output directory supplied by the API caller.

    Returns:
        Resolved ``Path`` inside one of the allowed roots.

    Raises:
        HTTPException: ``403`` when the requested directory escapes
            both allowed roots.
    """
    cwd = os.path.realpath(str(Path.cwd()))
    tmp = os.path.realpath(tempfile.gettempdir())
    if user_dir is None:
        return Path(cwd)
    # First-line validator (string-level path guards).
    _validate_safe_path(user_dir)
    # CodeQL CWE-22 barrier: canonicalise then compare common prefixes
    # against each allowed root. Both calls are recognised sanitisers.
    candidate = os.path.realpath(user_dir)
    for base in (cwd, tmp):
        try:
            common = os.path.commonpath([candidate, base])
        except ValueError:  # pragma: no cover - different drives on Windows
            continue
        # ``commonpath`` equality plus an explicit ``startswith`` on the
        # canonicalised candidate are both barriers the CodeQL
        # py/path-injection query recognises. Requiring them together — on
        # the very value returned and later passed to ``mkdir`` — lets the
        # taint tracker clear the sink natively, without relying on the
        # neutral model in pain001-security.model.yml.
        if common == base and (
            candidate == base or candidate.startswith(base + os.sep)
        ):
            return Path(candidate)
    raise HTTPException(  # pragma: no cover - defensive barrier
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: output_dir outside allowed directory",
    )


def _resolve_generation_paths(
    request: GenerateXMLRequest,
) -> tuple[str, str, str]:
    """Resolve the output file path and bundled template/schema paths.

    Delegates the security barriers to :func:`_gate_output_dir` and
    :func:`_sanitise_message_type`; those helpers raise the relevant
    :class:`HTTPException`\\ s.

    Args:
        request: Generation request with message type and optional output dir.

    Returns:
        Tuple of (output_file_path, xsd_file_path, xml_template_path).
    """
    safe_output_dir = _gate_output_dir(request.output_dir)
    safe_output_dir.mkdir(parents=True, exist_ok=True)
    # ``request.message_type`` is a pydantic Enum, but CodeQL doesn't
    # track that the enum is constrained at deserialisation time.
    # ``_sanitise_message_type`` is marked as a neutral summary in
    # ``.github/codeql/extensions/pain001-security.model.yml`` so the
    # taint tracker treats its return value as sanitised; we *use*
    # that return value (not the original ``request.message_type.value``)
    # in every downstream path expression.
    safe_message_type = _sanitise_message_type(request.message_type.value)
    output_file_path = str(safe_output_dir / output_name(safe_message_type))

    # Bundled package data, resolved package-relative so the API works
    # regardless of the server's working directory.
    template_base = TEMPLATES_DIR / safe_message_type
    xsd_file_path = str(template_base / f"{safe_message_type}.xsd")
    xml_template_path = str(template_base / "template.xml")
    return output_file_path, xsd_file_path, xml_template_path


@asynccontextmanager
async def _lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialise process-wide services once, when the server starts.

    Bootstraps the OpenTelemetry SDK (a no-op unless ``OTEL_ENABLED``
    is set and the ``pain001[otel]`` extra is installed) so the first
    request does not pay for it. Runs the start-up checks (a bad
    ``PAIN001_API_CONCURRENCY`` stops the server; a missing API key is
    logged) and releases the pipeline pool on shutdown.

    Args:
        application: The FastAPI application being started.

    Yields:
        None: Control to the server for its lifetime.
    """
    del application  # The hook is process-wide; nothing app-specific.
    init_otel()
    startup_checks()
    yield
    reset_executor()


# Create FastAPI application
app = FastAPI(
    title="Pain001 REST API",
    lifespan=_lifespan,
    description=API_DESCRIPTION,
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_tags=TAGS_METADATA,
    contact={
        "name": "Pain001",
        "url": "https://github.com/sebastienrousseau/pain001",
    },
    license_info={
        "name": "Apache-2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0",
    },
)

# Routes are defined on a router and mounted twice: under the canonical
# ``/api/v1`` prefix (documented) and the legacy ``/api`` prefix (hidden
# from the schema but still served, so existing clients keep working).
router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
)
async def health() -> HealthResponse:
    """Check API health status.

    Returns:
        HealthResponse: API status and version information.
    """
    return HealthResponse(
        status="healthy",
        version=__version__,
        message="Pain001 API is running",
    )


@router.post(
    "/validate",
    response_model=ValidationResponse,
    tags=["Validation"],
    summary="Validate payment data",
    dependencies=[Depends(_require_api_key)],
)
@traced("pain001.api.validate", attributes={"http.route": "/api/v1/validate"})
async def validate_data(request: ValidationRequest) -> ValidationResponse:
    """Validate payment data against schema.

    Args:
        request: Validation request with data source and file path.

    Returns:
        ValidationResponse: Validation results with error details.

    Raises:
        HTTPException: If file not found or validation fails.
    """
    try:
        file_path = _guarded_input_path(request.file_path)
        # Loading and validating are CPU-bound: off the event loop.
        return await run_pipeline(validate_pipeline, request, file_path)

    except HTTPException:
        raise
    except PaymentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Validation failed",
        ) from e


@router.post(
    "/generate",
    response_model=GenerateXMLResponse,
    tags=["Generation"],
    summary="Generate XML (synchronous)",
    dependencies=[Depends(_require_api_key)],
)
@traced("pain001.api.generate", attributes={"http.route": "/api/v1/generate"})
async def generate_xml_sync(
    request: GenerateXMLRequest,
) -> GenerateXMLResponse:
    """Generate XML synchronously.

    Args:
        request: Generation request with data source and options.

    Returns:
        GenerateXMLResponse: Generated XML file path or errors.

    Raises:
        HTTPException: If generation fails.
    """
    start_time = time.perf_counter()
    msg_type = request.message_type.value
    try:
        file_path = _guarded_input_path(request.file_path)
        # Load, validate and render off the event loop, bounded.
        outcome = await run_pipeline(
            generate_pipeline, request, file_path, _resolve_generation_paths
        )
    except HTTPException:
        record_failure(msg_type, start_time)
        raise
    except PaymentValidationError as e:
        record_failure(msg_type, start_time)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        record_failure(msg_type, start_time)
        logger.exception("Synchronous XML generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Generation failed",
        ) from e
    record_outcome(outcome, msg_type, start_time)
    return sync_response(outcome)


@router.post(
    "/generate/async",
    response_model=dict,
    tags=["Generation"],
    summary="Generate XML (asynchronous)",
    dependencies=[Depends(_require_api_key)],
)
@traced(
    "pain001.api.generate_async",
    attributes={"http.route": "/api/v1/generate/async"},
)
async def generate_xml_async(request: GenerateXMLRequest) -> dict[str, str]:
    """Start async XML generation job.

    Args:
        request: Generation request.

    Returns:
        Dictionary with job_id for status polling.

    Raises:
        HTTPException: If job creation fails.
    """
    try:
        # Create job
        job_id = job_manager.create_job()

        # Start background task, keeping a strong reference until done
        task = asyncio.create_task(_process_generation_job(job_id, request))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        return {
            "job_id": job_id,
            "status": "accepted",
            "message": f"Job {job_id} created. Check status with /api/status/{job_id}",
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job",
        ) from e


@router.get(
    "/status/{job_id}",
    response_model=JobStatusResponse,
    tags=["Job Management"],
    summary="Get job status",
    dependencies=[Depends(_require_api_key)],
)
@traced(
    "pain001.api.status", attributes={"http.route": "/api/v1/status/{job_id}"}
)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get status of async job.

    Args:
        job_id: Job identifier.

    Returns:
        JobStatusResponse: Current job status and result.

    Raises:
        HTTPException: If job not found.
    """
    job = job_manager.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    message = {
        JobStatus.PENDING: "Job is pending",
        JobStatus.PROCESSING: "Job is processing",
        JobStatus.SUCCESS: "Job completed successfully",
        JobStatus.FAILED: "Job failed",
        JobStatus.CANCELLED: "Job was cancelled",
    }[job.status]

    return JobStatusResponse(
        job_id=job_id,
        status=job.status.value,
        message=message,
        result=GenerateXMLResponse(**job.result) if job.result else None,
        error=job.error,
        progress_percent=job.progress_percent,
    )


@router.delete(
    "/jobs/{job_id}",
    tags=["Job Management"],
    summary="Cancel job",
    dependencies=[Depends(_require_api_key)],
)
async def cancel_job(job_id: str) -> dict[str, str]:
    """Cancel an async job.

    Args:
        job_id: Job identifier.

    Returns:
        Dictionary with cancellation status.

    Raises:
        HTTPException: If job not found.
    """
    cancelled = job_manager.cancel_job(job_id)

    if not cancelled and job_id not in job_manager.jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    return {
        "job_id": job_id,
        "status": "cancelled",
        "message": f"Job {job_id} cancelled",
    }


@router.get(
    "/download/{job_id}",
    tags=["Generation"],
    summary="Download generated XML",
    dependencies=[Depends(_require_api_key)],
)
@traced(
    "pain001.api.download",
    attributes={"http.route": "/api/v1/download/{job_id}"},
)
async def download_xml(job_id: str) -> FileResponse:
    """Download generated XML file.

    Args:
        job_id: Job identifier.

    Returns:
        FileResponse: XML file for download.

    Raises:
        HTTPException: If job not found or file not available.
    """
    job = job_manager.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    if job.status != JobStatus.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job status is {job.status.value}, not available for download",
        )

    if not job.result or "file_path" not in job.result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No file available for download",
        )

    file_path = str(_validate_safe_path(job.result["file_path"]))
    # CodeQL CWE-22 guard: same variable for guard and sink
    if not file_path.startswith(str(Path.cwd().resolve()) + os.sep):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated file not found",
        )

    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type="application/xml",
    )


async def _process_generation_job(
    job_id: str,
    request: GenerateXMLRequest,
) -> None:
    """Process async generation job.

    Args:
        job_id: Job identifier.
        request: Generation request.
    """
    start_time = time.perf_counter()
    msg_type = request.message_type.value
    try:
        file_path = _guarded_input_path(request.file_path)
        # The job waits as PENDING until a pipeline slot is free; the
        # pipeline reports PROCESSING progress from its worker thread.
        outcome = await run_pipeline(
            generate_pipeline,
            request,
            file_path,
            _resolve_generation_paths,
            functools.partial(_report_progress, job_id),
        )
    except InputRefused as exc:
        record_failure(msg_type, start_time)
        job_manager.update_status(job_id, JobStatus.FAILED, error=exc.detail)
        return
    except Exception as exc:
        record_failure(msg_type, start_time)
        logger.exception("Job %s failed", job_id)
        job_manager.update_status(
            job_id,
            JobStatus.FAILED,
            progress=100,
            error=job_manager.error_for(exc),
        )
        return
    record_outcome(outcome, msg_type, start_time)
    job_manager.update_status(job_id, progress=100, **job_update(outcome))


def _report_progress(job_id: str, percent: int) -> None:
    """Mark a background job as processing at ``percent``.

    Args:
        job_id: Job identifier.
        percent: Progress percentage.
    """
    job_manager.update_status(job_id, JobStatus.PROCESSING, progress=percent)


@app.get("/api/reference", include_in_schema=False)
async def scalar_reference() -> HTMLResponse:
    """Serve an interactive Scalar API reference for the OpenAPI document.

    Returns:
        The Scalar reference UI as an HTML response.
    """
    return HTMLResponse(SCALAR_HTML)


@app.get("/metrics", include_in_schema=False)
async def metrics() -> PlainTextResponse:
    """Expose Prometheus metrics (build info, gauges, request counters).

    Returns:
        The metrics document in Prometheus text exposition format.
    """
    return PlainTextResponse(render_prometheus(__version__))


def _install_rate_limiting(application: FastAPI) -> None:
    """Attach the rate-limit middleware when PAIN001_RATE_LIMIT is set.

    Args:
        application: The FastAPI application to wrap.
    """
    spec = os.environ.get("PAIN001_RATE_LIMIT")
    if not spec:
        return
    max_requests, window_seconds = parse_rate_limit(spec)
    application.add_middleware(
        RateLimitMiddleware,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )


# The dashboard and its two JSON endpoints, and the faces, ride on the
# main router so they are served under both prefixes and share its auth
# and metrics.
router.include_router(ui_router)
router.include_router(faces_router)

# Mount the routes: canonical, documented ``/api/v1`` plus the legacy
# ``/api`` alias (served but hidden from the OpenAPI schema).
app.include_router(router, prefix="/api/v1")
app.include_router(router, prefix="/api", include_in_schema=False)
app.add_middleware(MetricsMiddleware)
_install_rate_limiting(app)
