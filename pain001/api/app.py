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
import logging
import os
import tempfile
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

from pain001 import __version__
from pain001.api.auth import require_api_key as _require_api_key
from pain001.api.guards import sanitise_message_type as _sanitise_message_type
from pain001.api.job_manager import JobStatus, job_manager
from pain001.api.metrics import (
    MetricsMiddleware,
    registry,
    render_prometheus,
)
from pain001.api.models import (
    GenerateXMLRequest,
    GenerateXMLResponse,
    HealthResponse,
    JobStatusResponse,
    ValidationRequest,
    ValidationResponse,
)
from pain001.api.models import (
    ValidationError as ValidationErrorModel,
)
from pain001.api.ratelimit import RateLimitMiddleware, parse_rate_limit
from pain001.api.ui import ui_router
from pain001.constants import TEMPLATES_DIR
from pain001.data.loader import load_payment_data
from pain001.exceptions import PaymentValidationError
from pain001.observability.otel import init_otel, traced
from pain001.security.path_validator import (
    PathValidationError,
    SecurityError,
    validate_path,
)
from pain001.validation import validate_scheme
from pain001.validation.schema_validator import SchemaValidator
from pain001.validation.schemes import SchemeValidationResult
from pain001.xml.generate_xml import generate_xml

logger = logging.getLogger(__name__)

# References to in-flight background tasks. asyncio only keeps weak
# references to tasks, so without this set a running job could be
# garbage-collected mid-flight.
_background_tasks: set[asyncio.Task[None]] = set()


def _request_scheme_result(
    data: list[dict[str, Any]],
    request: ValidationRequest | GenerateXMLRequest,
) -> SchemeValidationResult:
    """Evaluate request-local policy and scheme rules before any XML write.

    Args:
        data: Loaded payment records.
        request: Request carrying an optional scheme and inline policy.

    Returns:
        Combined structured validation findings.

    Raises:
        HTTPException: If policy dependencies, syntax or inputs are invalid.
        ValueError: Raised internally for missing policy dependencies and
            converted to HTTPException before returning to the caller.
    """
    try:
        if request.rules is not None:
            try:
                from pain001.validation.policy import validate_policy
            except ImportError as exc:
                raise ValueError(
                    "Custom rules require 'pain001[rules]'."
                ) from exc
            return validate_policy(
                data, request.rules, request.scheme, request.message_type.value
            )
        return validate_scheme(
            data, request.scheme or "", message_type=request.message_type.value
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


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


def _format_validation_errors(
    errors: list[tuple[int, list]],  # type: ignore[type-arg]
) -> list[ValidationErrorModel]:
    """Format schema validation errors into API response models.

    Args:
        errors: List of (row_index, error_list) tuples from SchemaValidator.

    Returns:
        List of ValidationErrorModel instances.
    """
    error_models: list[ValidationErrorModel] = []
    for _, row_errors in errors:
        for error in row_errors:
            error_models.append(
                ValidationErrorModel(
                    field=error.path,
                    message=error.message,
                    value=str(error.value),
                )
            )
    return error_models


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
    output_file_path = str(safe_output_dir / f"{safe_message_type}.xml")

    # Bundled package data, resolved package-relative so the API works
    # regardless of the server's working directory.
    template_base = TEMPLATES_DIR / safe_message_type
    xsd_file_path = str(template_base / f"{safe_message_type}.xsd")
    xml_template_path = str(template_base / "template.xml")
    return output_file_path, xsd_file_path, xml_template_path


# OpenAPI tag metadata — drives the grouped, described sections in the
# interactive docs and any generated SDKs.
TAGS_METADATA = [
    {
        "name": "Health",
        "description": "Liveness and version probe for load balancers.",
    },
    {
        "name": "Validation",
        "description": (
            "Validate payment data against the XSD schema and, optionally, "
            "a payment-scheme rulebook — without producing a file."
        ),
    },
    {
        "name": "Generation",
        "description": (
            "Generate ISO 20022 XML synchronously or as a background job, "
            "and download the result."
        ),
    },
    {
        "name": "Job Management",
        "description": "Poll, cancel, and manage asynchronous generation jobs.",
    },
    {
        "name": "UI",
        "description": (
            "Backing endpoints for the hosted dashboard at `/api/v1/ui`: "
            "the same validation and generation, fed with an uploaded "
            "file's content instead of a server-side path."
        ),
    },
]

API_DESCRIPTION = """\
RESTful API for ISO 20022 **pain.001** / **pain.008** XML generation and
validation.

* **Versioned** — all endpoints are served under `/api/v1`; the unversioned
  `/api/*` paths remain as a backwards-compatible alias.
* **Authenticated** — set `PAIN001_API_KEY` to require a
  `Authorization: Bearer <key>` header (open in local development).
* **Rate limited** — set `PAIN001_RATE_LIMIT` (e.g. `100/minute`) to cap
  requests per client.

Interactive reference: [`/api/reference`](/api/reference) ·
OpenAPI document: [`/openapi.json`](/openapi.json) ·
Dashboard: [`/api/v1/ui`](/api/v1/ui) (disable with `PAIN001_UI_DISABLED=1`)
"""


@asynccontextmanager
async def _lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialise process-wide services once, when the server starts.

    Bootstraps the OpenTelemetry SDK (a no-op unless ``OTEL_ENABLED``
    is set and the ``pain001[otel]`` extra is installed) so the first
    request does not pay for it.

    Args:
        application: The FastAPI application being started.

    Yields:
        None: Control to the server for its lifetime.
    """
    del application  # The hook is process-wide; nothing app-specific.
    init_otel()
    yield


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
        # Validate and load data (secure path)
        file_path = str(_validate_safe_path(request.file_path))
        # CodeQL CWE-22 guard: same variable for guard and sink
        if not file_path.startswith(str(Path.cwd().resolve()) + os.sep):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )

        data = load_payment_data(file_path)

        # Validate against schema
        validator = SchemaValidator(request.message_type.value)
        total, valid, errors = validator.validate_batch(data)

        # Format errors
        error_models = _format_validation_errors(errors)

        scheme_violations: list[dict[str, Any]] = []
        is_valid = len(errors) == 0
        if request.scheme or request.rules is not None:
            scheme_result = _request_scheme_result(data, request)
            scheme_violations = [v.as_dict() for v in scheme_result.violations]
            is_valid = is_valid and scheme_result.is_valid

        return ValidationResponse(
            is_valid=is_valid,
            total_rows=total,
            valid_rows=valid,
            errors=error_models,
            scheme_violations=scheme_violations,
        )

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
        # Validate file path (secure path)
        file_path = str(_validate_safe_path(request.file_path))
        # CodeQL CWE-22 guard: same variable for guard and sink
        if not file_path.startswith(str(Path.cwd().resolve()) + os.sep):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )

        # Validate first
        data = load_payment_data(str(file_path))

        validator = SchemaValidator(request.message_type.value)
        total, valid, errors = validator.validate_batch(data)

        if errors:
            registry.record_file_processed("failure", msg_type)
            registry.record_processing_seconds(
                time.perf_counter() - start_time
            )
            error_models = _format_validation_errors(errors)

            return GenerateXMLResponse(
                success=False,
                message=f"Validation failed: {valid}/{total} rows valid",
                file_path=None,
                validation_errors=error_models,
            )

        # Scheme rulebook validation (when requested)
        if request.scheme or request.rules is not None:
            scheme_result = _request_scheme_result(data, request)
            if not scheme_result.is_valid:
                registry.record_file_processed("failure", msg_type)
                registry.record_processing_seconds(
                    time.perf_counter() - start_time
                )
                return GenerateXMLResponse(
                    success=False,
                    message=(
                        f"Scheme '{scheme_result.profile}' validation failed"
                    ),
                    file_path=None,
                    scheme_violations=[
                        v.as_dict() for v in scheme_result.violations
                    ],
                )

        # Validate-only mode
        if request.validate_only:
            return GenerateXMLResponse(
                success=True,
                message=f"All {valid} rows are valid",
                file_path=None,
            )

        # Generate XML
        (
            output_file_path,
            xsd_file_path,
            xml_template_path,
        ) = _resolve_generation_paths(request)

        result_path = await asyncio.to_thread(
            generate_xml,
            data,
            request.message_type.value,
            xml_template_path,
            xsd_file_path,
            output_file_path,
        )

        registry.record_file_processed("success", msg_type)
        registry.record_data_volumes(data)
        registry.record_processing_seconds(time.perf_counter() - start_time)

        return GenerateXMLResponse(
            success=True,
            message="XML generated successfully",
            file_path=str(result_path),
        )

    except HTTPException:
        registry.record_file_processed("failure", msg_type)
        registry.record_processing_seconds(time.perf_counter() - start_time)
        raise
    except PaymentValidationError as e:
        registry.record_file_processed("failure", msg_type)
        registry.record_processing_seconds(time.perf_counter() - start_time)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        registry.record_file_processed("failure", msg_type)
        registry.record_processing_seconds(time.perf_counter() - start_time)
        logger.exception("Synchronous XML generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Generation failed",
        ) from e


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
        job_manager.update_status(
            job_id,
            JobStatus.PROCESSING,
            progress=10,
        )

        # Validate file path (secure path)
        file_path = str(_validate_safe_path(request.file_path))
        # CodeQL CWE-22 guard: same variable for guard and sink
        if not file_path.startswith(str(Path.cwd().resolve()) + os.sep):
            registry.record_file_processed("failure", msg_type)
            registry.record_processing_seconds(
                time.perf_counter() - start_time
            )
            job_manager.update_status(
                job_id, JobStatus.FAILED, error="Access denied"
            )
            return
        if not os.path.exists(file_path):
            registry.record_file_processed("failure", msg_type)
            registry.record_processing_seconds(
                time.perf_counter() - start_time
            )
            job_manager.update_status(
                job_id,
                JobStatus.FAILED,
                error="File not found",
            )
            return

        data = load_payment_data(file_path)

        job_manager.update_status(job_id, JobStatus.PROCESSING, progress=40)

        validator = SchemaValidator(request.message_type.value)
        total, valid, errors = validator.validate_batch(data)

        if errors:
            registry.record_file_processed("failure", msg_type)
            registry.record_processing_seconds(
                time.perf_counter() - start_time
            )
            job_manager.update_status(
                job_id,
                JobStatus.FAILED,
                progress=100,
                error=f"Validation failed: {valid}/{total} rows valid",
            )
            return

        if request.scheme or request.rules is not None:
            scheme_result = _request_scheme_result(data, request)
            if not scheme_result.is_valid:
                registry.record_file_processed("failure", msg_type)
                registry.record_processing_seconds(
                    time.perf_counter() - start_time
                )
                job_manager.update_status(
                    job_id,
                    JobStatus.FAILED,
                    progress=100,
                    error="Scheme validation failed: "
                    + ", ".join(v.rule for v in scheme_result.violations),
                    result={
                        "success": False,
                        "message": "Scheme validation failed",
                        "scheme_violations": [
                            v.as_dict() for v in scheme_result.violations
                        ],
                    },
                )
                return

        if request.validate_only:
            job_manager.update_status(
                job_id,
                JobStatus.SUCCESS,
                progress=100,
                result={
                    "success": True,
                    "message": f"All {valid} rows are valid",
                    "file_path": None,
                },
            )
            return

        job_manager.update_status(job_id, JobStatus.PROCESSING, progress=70)

        # Generate XML (secure paths)
        (
            output_file_path,
            xsd_file_path,
            xml_template_path,
        ) = _resolve_generation_paths(request)

        result_path = await asyncio.to_thread(
            generate_xml,
            data,
            request.message_type.value,
            xml_template_path,
            xsd_file_path,
            output_file_path,
        )

        registry.record_file_processed("success", msg_type)
        registry.record_data_volumes(data)
        registry.record_processing_seconds(time.perf_counter() - start_time)

        job_manager.update_status(
            job_id,
            JobStatus.SUCCESS,
            progress=100,
            result={
                "success": True,
                "message": "✓ XML generated successfully",
                "file_path": str(result_path),
                "validation_errors": [],
            },
        )

    except Exception:
        registry.record_file_processed("failure", msg_type)
        registry.record_processing_seconds(time.perf_counter() - start_time)
        logger.exception("Job %s failed", job_id)
        job_manager.update_status(
            job_id,
            JobStatus.FAILED,
            progress=100,
            error="Processing failed",
        )


_SCALAR_HTML = """\
<!doctype html>
<html>
  <head>
    <title>Pain001 REST API — Reference</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body>
    <script
      id="api-reference"
      data-url="/openapi.json"></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
  </body>
</html>
"""


@app.get("/api/reference", include_in_schema=False)
async def scalar_reference() -> HTMLResponse:
    """Serve an interactive Scalar API reference for the OpenAPI document.

    Returns:
        The Scalar reference UI as an HTML response.
    """
    return HTMLResponse(_SCALAR_HTML)


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


# The dashboard and its two JSON endpoints ride on the main router so
# they are served under both prefixes and share its auth and metrics.
router.include_router(ui_router)

# Mount the routes: canonical, documented ``/api/v1`` plus the legacy
# ``/api`` alias (served but hidden from the OpenAPI schema).
app.include_router(router, prefix="/api/v1")
app.include_router(router, prefix="/api", include_in_schema=False)
app.add_middleware(MetricsMiddleware)
_install_rate_limiting(app)
