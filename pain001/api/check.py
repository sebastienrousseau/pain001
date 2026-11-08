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

"""Check over REST: ``POST /api/v1/check``.

The document travels in the request body as XML text, never as a server
path, and goes through :func:`pain001.check.check_document`, the engine
behind ``pain001 check``: the XSD of the message type its namespace
names, the MDR cross-element rules, and the scheme profiles and
Schematron preset asked for. A Schematron rulebook is named by preset
only, so a request cannot make the server read a file. The check runs
on the bounded pipeline pool, off the event loop.

A document that fails a rung is a ``200`` with ``passed: false`` and the
findings; one that cannot be checked (not a bundled pain.001 or pain.008
message, a DTD, an unknown scheme) is a ``422`` with the reason.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from pain001.api._pipeline import run_pipeline
from pain001.api.auth import require_api_key
from pain001.check import MAX_CHECK_BYTES, check_document
from pain001.observability.otel import traced


class CheckRequest(BaseModel):
    """A document to check, with the optional rungs to add."""

    xml: str = Field(
        ...,
        min_length=1,
        max_length=MAX_CHECK_BYTES,
        description="The pain.001 or pain.008 document as XML text",
    )
    scheme: str | None = Field(
        None,
        pattern=r"^[a-z0-9-]+(,[a-z0-9-]+)*$",
        description="Scheme profiles, comma-separated (e.g. sepa-sct)",
    )
    schematron: str | None = Field(
        None,
        description="A Schematron preset (sepa, fednow, cbpr); not a path",
    )

    @field_validator("schematron")
    @classmethod
    def _preset_only(cls, value: str | None) -> str | None:
        """Accept a packaged preset name, never a path on the server."""
        from pain001.schematron import PRESET_RULEBOOKS

        if value is not None and value.lower() not in PRESET_RULEBOOKS:
            presets = ", ".join(sorted(PRESET_RULEBOOKS))
            raise ValueError(f"schematron must be a preset: {presets}")
        return value


class CheckFindingModel(BaseModel):
    """One problem one rung found."""

    rung: str = Field(..., description="xsd, mdr, scheme or schematron")
    rule: str
    severity: str = Field(..., description="error or warning")
    message: str
    location: str | None = Field(
        None, description="Element path, context, or transaction N"
    )


class CheckResponse(BaseModel):
    """The report: the verdict, the rungs that ran and every finding."""

    message_type: str
    passed: bool
    errors: int
    warnings: int
    rungs: list[str]
    findings: list[CheckFindingModel]


check_router = APIRouter(tags=["Validation"])


@check_router.post(
    "/check",
    response_model=CheckResponse,
    summary="Check an existing pain.001 or pain.008 document",
    dependencies=[Depends(require_api_key)],
    responses={422: {"description": "The document cannot be checked"}},
)
@traced("pain001.api.check", attributes={"http.route": "/api/v1/check"})
async def check(request: CheckRequest) -> dict[str, Any]:
    """Run the validation ladder on the document in the body.

    Args:
        request: The document, and the scheme profiles and Schematron
            preset to add.

    Returns:
        The report, ``passed: false`` when a rung found an error.

    Raises:
        HTTPException: ``422`` when the document cannot be checked.
    """
    try:
        report = await run_pipeline(
            check_document,
            request.xml,
            scheme=request.scheme,
            schematron=request.schematron,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return report.as_dict()
