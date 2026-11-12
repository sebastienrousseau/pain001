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

"""The dashboard's upload pipelines, run off the event loop.

Parsing a 10 MiB upload, validating every row and rendering the XML are
CPU-bound. The dashboard endpoints (:mod:`pain001.api.ui`) hand
:func:`validate_upload` and :func:`generate_upload` to
:func:`~pain001.api._pipeline.run_pipeline`, the same bounded pool the
path-based ``/validate`` and ``/generate`` use, so an upload never holds
``/health`` or any other route.
"""

from __future__ import annotations

import csv
import io
import json
import os
from typing import Any

from fastapi import HTTPException, status

from pain001.api._pipeline import format_validation_errors
from pain001.api.guards import sanitise_message_type
from pain001.api.models import (
    MAX_UPLOAD_BYTES,
    UiFilePayload,
    UiGenerateResponse,
    ValidationResponse,
)
from pain001.constants import TEMPLATES_DIR
from pain001.data.loader import load_payment_data
from pain001.exceptions import DataSourceError, PaymentValidationError
from pain001.validation import validate_scheme
from pain001.validation.ladder import Ladder, run_ladder
from pain001.xml.generate_xml import generate_xml_string

SUPPORTED_SUFFIXES: tuple[str, ...] = (".csv", ".json", ".jsonl")
"""Text formats the dashboard parses in memory."""

_BAD_REQUEST = status.HTTP_400_BAD_REQUEST


def _checked_suffix(filename: str, content: str) -> str:
    """Return the upload's suffix once its type and size are acceptable.

    Args:
        filename: The name the browser reported; only its suffix is used.
        content: The file's text.

    Returns:
        The lower-case suffix, one of :data:`SUPPORTED_SUFFIXES`.

    Raises:
        HTTPException: ``400`` for an unsupported suffix; ``413`` when
            the text exceeds :data:`MAX_UPLOAD_BYTES` in UTF-8.
    """
    suffix = os.path.splitext(filename.lower())[1]
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=_BAD_REQUEST,
            detail=f"Unsupported file type {suffix or '(none)'!r}; upload a "
            f"{', '.join(SUPPORTED_SUFFIXES)} file.",
        )
    if len(content.encode("utf-8")) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB; "
                "use the CLI or the path-based API for batches this size."
            ),
        )
    return suffix


def _json_rows(content: str) -> list[Any]:
    """Parse a JSON upload: one object, or an array of them.

    Args:
        content: The file's text.

    Returns:
        The rows, not yet checked to be objects.

    Raises:
        HTTPException: ``400`` for malformed JSON or a scalar document.
    """
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=_BAD_REQUEST, detail=f"Invalid JSON: {exc.msg}"
        ) from exc
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        return parsed
    raise HTTPException(
        status_code=_BAD_REQUEST,
        detail="JSON input must be an object or an array of objects.",
    )


def _jsonl_rows(content: str) -> list[Any]:
    """Parse a JSON Lines upload, one value per non-blank line.

    Args:
        content: The file's text.

    Returns:
        The rows, not yet checked to be objects.

    Raises:
        HTTPException: ``400`` naming the first malformed line.
    """
    rows: list[Any] = []
    for number, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=_BAD_REQUEST,
                detail=f"Invalid JSON on line {number}: {exc.msg}",
            ) from exc
    return rows


def parse_upload(
    filename: str, content: str, message_type: str | None = None
) -> list[dict[str, Any]]:
    """Turn the uploaded text into validated payment rows.

    Mirrors the file loaders: CSV through :class:`csv.DictReader`, JSON
    as a list or a single object, JSON Lines one object per line, then
    the same row validation the path-based loaders apply.

    Args:
        filename: The name the browser reported; only its suffix is used.
        content: The file's text.
        message_type: The target message type, whose columns every row
            must carry; ``None`` requires every column all bundled
            schemas describe.

    Returns:
        The validated rows.

    Raises:
        HTTPException: ``400`` for an unsupported suffix, malformed
            text, or rows that fail validation; ``413`` when the text
            exceeds :data:`MAX_UPLOAD_BYTES`.
    """
    suffix = _checked_suffix(filename, content)
    rows: list[Any]
    if suffix == ".csv":
        rows = list(csv.DictReader(io.StringIO(content)))
    elif suffix == ".json":
        rows = _json_rows(content)
    else:
        rows = _jsonl_rows(content)
    if not rows:
        raise HTTPException(
            status_code=_BAD_REQUEST, detail="The file has no payment rows."
        )
    if not all(isinstance(row, dict) for row in rows):
        raise HTTPException(
            status_code=_BAD_REQUEST,
            detail="Every payment row must be a JSON object.",
        )
    try:
        return load_payment_data(rows, message_type=message_type)
    except (DataSourceError, PaymentValidationError) as exc:
        raise HTTPException(status_code=_BAD_REQUEST, detail=str(exc)) from exc


def _scheme_violations(
    rows: list[dict[str, Any]], scheme: str | None
) -> tuple[bool, list[dict[str, Any]]]:
    """Run the requested scheme rulebooks, if any.

    Args:
        rows: Validated payment rows.
        scheme: Profile spec (one name, or comma-separated names), or
            ``None`` to skip scheme validation.

    Returns:
        ``(is_valid, violations)``; ``(True, [])`` when no scheme.

    Raises:
        HTTPException: ``400`` for an unknown profile name.
    """
    if not scheme:
        return True, []
    try:
        result = validate_scheme(rows, scheme)
    except ValueError as exc:
        raise HTTPException(status_code=_BAD_REQUEST, detail=str(exc)) from exc
    return result.is_valid, [v.as_dict() for v in result.violations]


def _climb(rows: list[dict[str, Any]], message_type: str) -> Ladder:
    """Run the shared validation ladder on uploaded rows.

    Args:
        rows: The parsed rows.
        message_type: The sanitised message type.

    Returns:
        The ladder's findings.

    Raises:
        HTTPException: ``400`` when the rows do not form one batch, as
            ``POST /validate`` and generation refuse them.
    """
    try:
        return run_ladder(rows, message_type)
    except PaymentValidationError as exc:
        raise HTTPException(status_code=_BAD_REQUEST, detail=str(exc)) from exc


def validate_upload(payload: UiFilePayload) -> ValidationResponse:
    """Validate the uploaded text against the schema and optional schemes.

    Args:
        payload: The file's text, its name, the message type, and an
            optional scheme spec.

    Returns:
        The same shape as ``POST /validate``.
    """
    message_type = sanitise_message_type(payload.message_type.value)
    rows = parse_upload(payload.filename, payload.content, message_type)
    ladder = _climb(rows, message_type)
    scheme_ok, violations = _scheme_violations(rows, payload.scheme)
    return ValidationResponse(
        is_valid=ladder.is_valid and scheme_ok,
        total_rows=ladder.total,
        valid_rows=ladder.valid,
        invalid_rows=ladder.invalid,
        errors=format_validation_errors(ladder.row_errors),
        scheme_violations=violations,
    )


def generate_upload(payload: UiFilePayload) -> UiGenerateResponse:
    """Validate the upload, then render the XML and return it inline.

    Args:
        payload: The file's text, its name, the message type, and an
            optional scheme spec.

    Returns:
        ``success=True`` with the XML document and a suggested filename,
        or ``success=False`` carrying the validation errors or scheme
        violations that blocked generation.

    Raises:
        HTTPException: ``400`` when rendering fails (for example the
            rendered document does not satisfy the XSD).
    """
    # Allow-list barrier: the enum is already constrained, but the value
    # is joined into filesystem paths below and static analysis only
    # recognises an explicit membership check as a sanitiser.
    message_type = sanitise_message_type(payload.message_type.value)
    rows = parse_upload(payload.filename, payload.content, message_type)
    ladder = _climb(rows, message_type)
    total, valid, errors = ladder.total, ladder.valid, ladder.row_errors
    if errors:
        return UiGenerateResponse(
            success=False,
            message=f"Validation failed: {valid}/{total} rows valid",
            validation_errors=format_validation_errors(errors),
        )
    scheme_ok, violations = _scheme_violations(rows, payload.scheme)
    if not scheme_ok:
        return UiGenerateResponse(
            success=False,
            message=f"Scheme '{payload.scheme}' validation failed",
            scheme_violations=violations,
        )
    template_base = TEMPLATES_DIR / message_type
    try:
        xml = generate_xml_string(
            rows,
            message_type,
            str(template_base / "template.xml"),
            str(template_base / f"{message_type}.xsd"),
        )
    except (ValueError, RuntimeError, PaymentValidationError) as exc:
        raise HTTPException(
            status_code=_BAD_REQUEST, detail=f"Generation failed: {exc}"
        ) from exc
    return UiGenerateResponse(
        success=True,
        message=f"Generated {message_type} for {total} payment rows",
        filename=f"{message_type}.xml",
        xml=xml,
    )
