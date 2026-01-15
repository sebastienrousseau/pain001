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

import asyncio
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse

from pain001 import __version__
from pain001.api.job_manager import JobStatus, job_manager
from pain001.api.models import (
    GenerateXMLRequest,
    GenerateXMLResponse,
    HealthResponse,
    JobStatusResponse,
    ValidationError as ValidationErrorModel,
    ValidationRequest,
    ValidationResponse,
)
from pain001.core.core import generate_xml
from pain001.data.loader import load_payment_data
from pain001.exceptions import PaymentValidationError
from pain001.validation.schema_validator import SchemaValidator

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
        # Load data
        file_path = Path(request.file_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {request.file_path}",
            )

        data = load_payment_data(str(file_path))

        # Validate against schema
        validator = SchemaValidator(request.message_type.value)
        total, valid, errors = validator.validate_batch(data)

        # Format errors
        error_models = []
        for row_idx, row_errors in errors:
            for error in row_errors:
                error_models.append(
                    ValidationErrorModel(
                        field=error.path,
                        message=error.message,
                        value=str(error.value),
                    )
                )

        return ValidationResponse(
            is_valid=len(errors) == 0,
            total_rows=total,
            valid_rows=valid,
            errors=error_models,
        )

    except PaymentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}",
        )


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
        file_path = Path(request.file_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {request.file_path}",
            )

        # Validate first
        data = load_payment_data(str(file_path))

        validator = SchemaValidator(request.message_type.value)
        total, valid, errors = validator.validate_batch(data)

        if errors:
            error_models = []
            for row_idx, row_errors in errors:
                for error in row_errors:
                    error_models.append(
                        ValidationErrorModel(
                            field=error.path,
                            message=error.message,
                            value=str(error.value),
                        )
                    )

            return GenerateXMLResponse(
                success=False,
                message=f"Validation failed: {valid}/{total} rows valid",
                validation_errors=error_models,
            )

        # Validate-only mode
        if request.validate_only:
            return GenerateXMLResponse(
                success=True,
                message=f"✓ All {valid} rows are valid",
            )

        # Generate XML
        output_dir = (
            Path(request.output_dir) if request.output_dir else None
        )
        result = generate_xml(
            file_path=str(file_path),
            message_type=request.message_type.value,
            data_source=request.data_source.value,
            output_dir=output_dir,
            table_name=request.table_name,
        )

        return GenerateXMLResponse(
            success=True,
            message="✓ XML generated successfully",
            file_path=str(result),
        )

    except PaymentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}",
        )


@app.post(
    "/api/generate/async",
    response_model=dict,
    tags=["Generation"],
    summary="Generate XML (asynchronous)",
)
async def generate_xml_async(request: GenerateXMLRequest) -> dict:
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
        asyncio.create_task(
            _process_generation_job(job_id, request)
        )

        return {
            "job_id": job_id,
            "status": "accepted",
            "message": f"Job {job_id} created. Check status with /api/status/{job_id}",
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}",
        )


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
async def cancel_job(job_id: str) -> dict:
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

    file_path = Path(job.result["file_path"])
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_path}",
        )

    return FileResponse(
        path=file_path,
        filename=file_path.name,
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

        # Validate
        file_path = Path(request.file_path)
        if not file_path.exists():
            job_manager.update_status(
                job_id,
                JobStatus.FAILED,
                error=f"File not found: {request.file_path}",
            )
            return

        data = load_payment_data(str(file_path))

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

        # Generate XML
        output_dir = (
            Path(request.output_dir) if request.output_dir else None
        )
        result = generate_xml(
            file_path=str(file_path),
            message_type=request.message_type.value,
            data_source=request.data_source.value,
            output_dir=output_dir,
            table_name=request.table_name,
        )

        job_manager.update_status(
            job_id,
            JobStatus.SUCCESS,
            progress=100,
            result={
                "success": True,
                "message": "✓ XML generated successfully",
                "file_path": str(result),
                "validation_errors": [],
            },
        )

    except Exception as e:
        job_manager.update_status(
            job_id,
            JobStatus.FAILED,
            progress=100,
            error=f"Processing failed: {str(e)}",
        )
