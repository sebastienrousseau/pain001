# Copyright (C) 2023-2026 Sebastien Rousseau.
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

"""Pain001 FastAPI application."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse

from pain001 import __version__
from pain001.api.job_manager import JobStatus, job_manager
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
from pain001.data.loader import load_payment_data
from pain001.exceptions import PaymentValidationError
from pain001.security.path_validator import (
    PathValidationError,
    SecurityError,
    validate_path,
)
from pain001.validation.schema_validator import SchemaValidator
from pain001.xml.generate_updated_xml_file_path import (
    generate_updated_xml_file_path,
)
from pain001.xml.generate_xml import generate_xml


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
    if not (
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


def _resolve_generation_paths(
    request: GenerateXMLRequest,
) -> tuple[str, str, str]:
    """Resolve and validate output directory and template paths for XML generation.

    Args:
        request: Generation request with message type and optional output dir.

    Returns:
        Tuple of (output_dir, xsd_file_path, xml_template_path) as strings.
    """
    if request.output_dir:
        output_dir = str(_validate_safe_path(request.output_dir))
    else:
        output_dir = str(Path.cwd())
    # CodeQL CWE-22 guard: same variable for guard and sink
    if not output_dir.startswith(str(Path.cwd().resolve())):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )
    os.makedirs(output_dir, exist_ok=True)

    template_base = Path("pain001/templates") / request.message_type.value
    xsd_file_path = str(
        _validate_safe_path(
            str(template_base / f"{request.message_type.value}.xsd")
        )
    )
    xml_template_path = str(
        _validate_safe_path(str(template_base / "template.xml"))
    )
    return output_dir, xsd_file_path, xml_template_path


# Create FastAPI application
app = FastAPI(
    title="Pain001 REST API",
    description="RESTful API for ISO 20022 pain.001 XML generation and validation",
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


@app.get(
    "/api/health",
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


@app.post(
    "/api/validate",
    response_model=ValidationResponse,
    tags=["Validation"],
    summary="Validate payment data",
)
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

        return ValidationResponse(
            is_valid=len(errors) == 0,
            total_rows=total,
            valid_rows=valid,
            errors=error_models,
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


@app.post(
    "/api/generate",
    response_model=GenerateXMLResponse,
    tags=["Generation"],
    summary="Generate XML (synchronous)",
)
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
            error_models = _format_validation_errors(errors)

            return GenerateXMLResponse(
                success=False,
                message=f"Validation failed: {valid}/{total} rows valid",
                file_path=None,
                validation_errors=error_models,
            )

        # Validate-only mode
        if request.validate_only:
            return GenerateXMLResponse(
                success=True,
                message=f"All {valid} rows are valid",
                file_path=None,
            )

        # Generate XML
        _, xsd_file_path, xml_template_path = _resolve_generation_paths(
            request
        )

        generate_xml(
            data,
            request.message_type.value,
            xml_template_path,
            xsd_file_path,
        )

        # Get the generated file path
        result_path = generate_updated_xml_file_path(
            xml_template_path,
            request.message_type.value,
        )

        return GenerateXMLResponse(
            success=True,
            message="XML generated successfully",
            file_path=str(result_path),
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
            detail="Generation failed",
        ) from e


@app.post(
    "/api/generate/async",
    response_model=dict,
    tags=["Generation"],
    summary="Generate XML (asynchronous)",
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

        # Start background task
        asyncio.create_task(_process_generation_job(job_id, request))

        return {
            "job_id": job_id,
            "status": "accepted",
            "message": f"Job {job_id} created. Check status with /api/status/{job_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job",
        ) from e


@app.get(
    "/api/status/{job_id}",
    response_model=JobStatusResponse,
    tags=["Job Management"],
    summary="Get job status",
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


@app.delete(
    "/api/jobs/{job_id}",
    tags=["Job Management"],
    summary="Cancel job",
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


@app.get(
    "/api/download/{job_id}",
    tags=["Generation"],
    summary="Download generated XML",
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
            job_manager.update_status(
                job_id, JobStatus.FAILED, error="Access denied"
            )
            return
        if not os.path.exists(file_path):
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
            job_manager.update_status(
                job_id,
                JobStatus.FAILED,
                progress=100,
                error=f"Validation failed: {valid}/{total} rows valid",
            )
            return

        job_manager.update_status(job_id, JobStatus.PROCESSING, progress=70)

        # Generate XML (secure paths)
        _, xsd_file_path, xml_template_path = _resolve_generation_paths(
            request
        )

        generate_xml(
            data,
            request.message_type.value,
            xml_template_path,
            xsd_file_path,
        )

        # Get the generated file path
        result_path = generate_updated_xml_file_path(
            xml_template_path,
            request.message_type.value,
        )

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
        job_manager.update_status(
            job_id,
            JobStatus.FAILED,
            progress=100,
            error="Processing failed",
        )
