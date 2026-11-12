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

"""The REST validation and generation pipelines, run off the event loop.

Loading a file, validating every row and rendering XML are CPU-bound:
run on the event loop, one 1,000-row request holds every other request
(``/health`` included) for seconds. :func:`run_pipeline` hands each
pipeline to a dedicated thread pool whose size is the number of
pipelines allowed to run at once (``PAIN001_API_CONCURRENCY``, default
the CPU count); requests beyond it wait in the pool's queue.

The synchronous ``/generate`` endpoint and the background job share
:func:`generate_pipeline`; each maps its :class:`GenerationOutcome` to
its own response shape.
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, ParamSpec, TypeVar

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from pain001.api._redact import mask_error
from pain001.api.job_manager import JobStatus
from pain001.api.metrics import registry
from pain001.api.models import (
    GenerateXMLRequest,
    GenerateXMLResponse,
    UiGenerateResponse,
    ValidationRequest,
    ValidationResponse,
)
from pain001.api.models import ValidationError as ValidationErrorModel
from pain001.validation.ladder import check_scheme, run_ladder
from pain001.validation.schemes import SchemeValidationResult
from pain001.xml.generate_xml import generate_xml

CONCURRENCY_ENV = "PAIN001_API_CONCURRENCY"
"""Environment variable naming how many pipelines may run at once."""

P = ParamSpec("P")
T = TypeVar("T")
Body = TypeVar("Body", GenerateXMLResponse, UiGenerateResponse)

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


class InputRefused(HTTPException):
    """The input file was refused before any pipeline ran.

    A subclass so the background job can tell "access denied" and
    "file not found" (reported to the caller as such) from any other
    failure (reported through ``JobManager.error_for``).
    """


def pipeline_limit() -> int:
    """Return how many pipelines may run at once.

    Returns:
        The value of ``PAIN001_API_CONCURRENCY``, or the CPU count
        (at least one) when it is unset or empty.

    Raises:
        ValueError: If the variable is set to anything but a positive
            integer.
    """
    raw = os.environ.get(CONCURRENCY_ENV, "").strip()
    if not raw:
        return os.cpu_count() or 1
    if not raw.isdigit() or int(raw) < 1:
        raise ValueError(
            f"{CONCURRENCY_ENV} must be a positive integer, got {raw!r}"
        )
    return int(raw)


def _get_executor() -> ThreadPoolExecutor:
    """Return the shared pipeline pool, creating it on first use.

    Returns:
        A thread pool with :func:`pipeline_limit` workers.
    """
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=pipeline_limit(),
                thread_name_prefix="pain001-pipeline",
            )
        return _executor


def reset_executor() -> None:
    """Drop the pipeline pool so the next pipeline re-reads the limit.

    Pipelines already running finish; the pool is not waited for.
    """
    global _executor
    with _executor_lock:
        executor, _executor = _executor, None
    if executor is not None:
        executor.shutdown(wait=False)


def _forget_executor_in_child() -> None:
    """Give a forked child its own pool and lock.

    A child inherits the pool object but none of its threads. The pool
    still counts the parent's idle workers, so it would start none and
    the child's first pipeline would wait forever; the lock may also
    have been held by a parent thread at the fork. The parent's pool is
    not shut down here: its threads are not the child's to join.
    """
    global _executor, _executor_lock
    _executor = None
    _executor_lock = threading.Lock()


# Every platform CI runs on is POSIX; Windows has no fork to guard.
if hasattr(os, "register_at_fork"):  # pragma: no branch
    os.register_at_fork(after_in_child=_forget_executor_in_child)


async def run_pipeline(
    func: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    """Run ``func`` on the bounded pipeline pool and await its result.

    The caller's context variables (the active trace span among them)
    are copied into the worker thread.

    Args:
        func: The blocking pipeline to run.
        *args: Positional arguments for ``func``.
        **kwargs: Keyword arguments for ``func``.

    Returns:
        Whatever ``func`` returns; its exceptions propagate unchanged.
    """
    context = contextvars.copy_context()
    call = functools.partial(context.run, func, *args, **kwargs)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_get_executor(), call)


def request_scheme_result(
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
    """
    try:
        return check_scheme(
            data, request.message_type.value, request.scheme, request.rules
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


def format_validation_errors(
    errors: list[tuple[int, list]],  # type: ignore[type-arg]
) -> list[ValidationErrorModel]:
    """Format schema validation errors into API response models.

    Args:
        errors: List of (row_index, error_list) tuples from SchemaValidator.

    Returns:
        List of ValidationErrorModel instances, with IBAN, BIC, account
        and name values masked (see :mod:`pain001.api._redact`).
    """
    error_models: list[ValidationErrorModel] = []
    for _, row_errors in errors:
        for error in row_errors:
            message, value = mask_error(error.path, error.message, error.value)
            error_models.append(
                ValidationErrorModel(
                    field=error.path, message=message, value=value
                )
            )
    return error_models


def validate_pipeline(
    request: ValidationRequest, file_path: str
) -> ValidationResponse:
    """Load and validate one file: the ``/validate`` endpoint's work.

    Args:
        request: Validation request (message type, scheme, rules).
        file_path: The guarded, existing input path.

    Returns:
        The validation response.
    """
    ladder = run_ladder(
        file_path,
        request.message_type.value,
        identifier_checks=request.identifier_checks,
    )

    scheme_violations: list[dict[str, Any]] = []
    is_valid = ladder.is_valid
    if request.scheme or request.rules is not None:
        scheme_result = request_scheme_result(ladder.rows, request)
        scheme_violations = [v.as_dict() for v in scheme_result.violations]
        is_valid = is_valid and scheme_result.is_valid

    return ValidationResponse(
        is_valid=is_valid,
        total_rows=ladder.total,
        valid_rows=ladder.valid,
        invalid_rows=ladder.invalid,
        errors=format_validation_errors(ladder.row_errors),
        scheme_violations=scheme_violations,
    )


@dataclass(frozen=True)
class GenerationOutcome:
    """What one run of :func:`generate_pipeline` produced.

    Attributes:
        kind: ``invalid_rows``, ``scheme_failed``, ``validated`` or
            ``generated``.
        total: Rows loaded.
        valid: Rows that passed schema validation.
        errors: Per-row schema errors, for ``invalid_rows``.
        profile: The scheme profile that failed, for ``scheme_failed``.
        violations: The scheme violations, for ``scheme_failed``.
        file_path: The written XML file, for ``generated``.
        data: The loaded rows, for ``generated`` (volume metrics).
    """

    kind: str
    total: int = 0
    valid: int = 0
    errors: list[Any] = field(default_factory=list)
    profile: str = ""
    violations: list[Any] = field(default_factory=list)
    file_path: str | None = None
    data: list[dict[str, Any]] = field(default_factory=list)


def _no_progress(_percent: int) -> None:
    """Ignore a progress report (the synchronous endpoint has none)."""


def generate_pipeline(
    request: GenerateXMLRequest,
    file_path: str,
    resolve_paths: Callable[[GenerateXMLRequest], tuple[str, str, str]],
    progress: Callable[[int], None] = _no_progress,
) -> GenerationOutcome:
    """Load, validate and (unless validate-only) render one file.

    Args:
        request: Generation request.
        file_path: The guarded, existing input path.
        resolve_paths: Returns (output, XSD, template) paths for the
            request; called only once the data has passed every check.
        progress: Receives a percentage at each stage.

    Returns:
        The outcome, for the caller to turn into its response.
    """
    progress(10)
    ladder = run_ladder(
        file_path,
        request.message_type.value,
        identifier_checks=request.identifier_checks,
        after_load=functools.partial(progress, 40),
    )
    data, total, valid, errors = (
        ladder.rows,
        ladder.total,
        ladder.valid,
        ladder.row_errors,
    )
    if errors:
        return GenerationOutcome("invalid_rows", total, valid, errors=errors)
    if request.scheme or request.rules is not None:
        scheme_result = request_scheme_result(data, request)
        if not scheme_result.is_valid:
            return GenerationOutcome(
                "scheme_failed",
                total,
                valid,
                profile=scheme_result.profile,
                violations=list(scheme_result.violations),
            )
    if request.validate_only:
        return GenerationOutcome("validated", total, valid)
    progress(70)
    output_file_path, xsd_file_path, xml_template_path = resolve_paths(request)
    result_path = generate_xml(
        data,
        request.message_type.value,
        xml_template_path,
        xsd_file_path,
        output_file_path,
    )
    return GenerationOutcome(
        "generated", total, valid, file_path=str(result_path), data=data
    )


def record_failure(message_type: str, start_time: float) -> None:
    """Count one failed file and its processing time.

    Args:
        message_type: ISO 20022 message type of the request.
        start_time: ``time.perf_counter()`` when the request began.
    """
    registry.record_file_processed("failure", message_type)
    registry.record_processing_seconds(time.perf_counter() - start_time)


def record_outcome(
    outcome: GenerationOutcome, message_type: str, start_time: float
) -> None:
    """Record the metrics for a finished generation pipeline.

    Runs on the event loop: the metrics registry is not thread-safe.
    A validate-only success records nothing, as before.

    Args:
        outcome: What the pipeline produced.
        message_type: ISO 20022 message type of the request.
        start_time: ``time.perf_counter()`` when the request began.
    """
    if outcome.kind == "generated":
        registry.record_file_processed("success", message_type)
        registry.record_data_volumes(outcome.data)
        registry.record_processing_seconds(time.perf_counter() - start_time)
    elif outcome.kind != "validated":
        record_failure(message_type, start_time)


def sync_response(
    outcome: GenerationOutcome,
) -> GenerateXMLResponse | JSONResponse:
    """Turn an outcome into the synchronous ``/generate`` response.

    Data that fails validation or a scheme rule is a ``422`` carrying
    the same body, so the status agrees with ``success``.

    Args:
        outcome: What the pipeline produced.

    Returns:
        The endpoint's response body, or a ``422`` response.
    """
    return refusal_as_422(_sync_body(outcome))


def refusal_as_422(body: Body) -> Body | JSONResponse:
    """Answer a refused generation with ``422`` and the same body.

    ``POST /generate`` and the dashboard's ``POST /ui/generate`` share
    this, so on both a ``200`` always means a document was produced.

    Args:
        body: A generation response.

    Returns:
        ``body`` itself when ``success`` is true, else a ``422``
        response carrying it.
    """
    if body.success:
        return body
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=body.model_dump(mode="json"),
    )


def _sync_body(outcome: GenerationOutcome) -> GenerateXMLResponse:
    """Build the synchronous ``/generate`` response body.

    Args:
        outcome: What the pipeline produced.

    Returns:
        The body, ``success=False`` when the data was refused.
    """
    if outcome.kind == "invalid_rows":
        return GenerateXMLResponse(
            success=False,
            message=f"Validation failed: {outcome.valid}/{outcome.total} rows valid",
            file_path=None,
            validation_errors=format_validation_errors(outcome.errors),
        )
    if outcome.kind == "scheme_failed":
        return GenerateXMLResponse(
            success=False,
            message=f"Scheme '{outcome.profile}' validation failed",
            file_path=None,
            scheme_violations=[v.as_dict() for v in outcome.violations],
        )
    if outcome.kind == "validated":
        return GenerateXMLResponse(
            success=True,
            message=f"All {outcome.valid} rows are valid",
            file_path=None,
        )
    return GenerateXMLResponse(
        success=True,
        message="XML generated successfully",
        file_path=outcome.file_path,
    )


def job_update(outcome: GenerationOutcome) -> dict[str, Any]:
    """Turn an outcome into the background job's final status update.

    Args:
        outcome: What the pipeline produced.

    Returns:
        Keyword arguments for ``JobManager.update_status``.
    """
    if outcome.kind == "invalid_rows":
        return {
            "status": JobStatus.FAILED,
            "error": f"Validation failed: {outcome.valid}/{outcome.total} rows valid",
        }
    if outcome.kind == "scheme_failed":
        rules = (v.rule for v in outcome.violations)
        return {
            "status": JobStatus.FAILED,
            "error": "Scheme validation failed: " + ", ".join(rules),
            "result": {
                "success": False,
                "message": "Scheme validation failed",
                "scheme_violations": [v.as_dict() for v in outcome.violations],
            },
        }
    if outcome.kind == "validated":
        message = f"All {outcome.valid} rows are valid"
        return {
            "status": JobStatus.SUCCESS,
            "result": {"success": True, "message": message, "file_path": None},
        }
    return {
        "status": JobStatus.SUCCESS,
        "result": {
            "success": True,
            "message": "✓ XML generated successfully",
            "file_path": outcome.file_path,
            "validation_errors": [],
        },
    }
