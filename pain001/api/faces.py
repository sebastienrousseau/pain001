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

"""Faces over REST: project a pain.001 document into another standard.

* ``GET /api/v1/faces`` - the faces, what each targets, and the binding
  keys each accepts.
* ``POST /api/v1/faces/{face}`` - the document as XML text in the body,
  with optional bindings; the target payload and its loss report out.

The document travels in the request body, never as a server path, and
goes through :func:`pain001.faces.project_face_text`, which refuses
anything but XML text, entity declarations and external references,
and documents over :data:`pain001.faces.MAX_INLINE_BYTES`. A face that
refuses the document (a required element missing, a binding it does
not accept) answers ``422`` with the face's reason. Bindings hold
per-customer values such as a UK Open Banking ``ConsentId``: they are
used for the one response and never stored.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from pain001.api.auth import require_api_key
from pain001.faces import (
    MAX_INLINE_BYTES,
    FaceError,
    available_faces,
    list_supported_faces,
    project_face_text,
)
from pain001.observability.otel import traced


class FaceInfo(BaseModel):
    """One face: its name, its target and the bindings it accepts."""

    name: str = Field(..., description="Face name, used in the path")
    description: str = Field(..., description="The target standard")
    bindings: list[str] = Field(
        ..., description="Binding keys the face accepts; any other is refused"
    )


class FaceRequest(BaseModel):
    """A pain.001 document to project, with optional private bindings."""

    xml: str = Field(
        ...,
        min_length=1,
        max_length=MAX_INLINE_BYTES,
        description="The pain.001 document as XML text",
    )
    version: str | None = Field(
        None,
        pattern=r"^pain\.001\.001\.\d{2}$",
        description="The pain.001 edition; detected from the namespace if omitted",
    )
    bindings: dict[str, Any] | None = Field(
        None,
        description=(
            "Side inputs the message does not carry (for example a UK Open "
            "Banking ConsentId); used for this response only"
        ),
    )


class LossReportModel(BaseModel):
    """What the projection carried and what it did not, by indexed path."""

    face: str
    total_source_elements: int
    mapped_count: int
    unmapped_count: int
    is_lossless: bool
    loss_ratio: float = Field(
        ..., description="Share of source leaves not carried"
    )
    mapped_paths: list[str]
    unmapped_paths: list[str]


class FaceResponse(BaseModel):
    """The target payload and its loss report."""

    face: str
    version: str = Field(..., description="The source pain.001 edition")
    payload: dict[str, Any] = Field(
        ..., description="The body in the target's shape"
    )
    loss_report: LossReportModel


faces_router = APIRouter(prefix="/faces", tags=["Faces"])


@faces_router.get(
    "",
    response_model=list[FaceInfo],
    summary="List faces",
    dependencies=[Depends(require_api_key)],
)
async def list_faces() -> list[dict[str, Any]]:
    """List the faces, their targets and the binding keys each accepts.

    Returns:
        One entry per face, sorted by name.
    """
    return list_supported_faces()


@faces_router.post(
    "/{face}",
    response_model=FaceResponse,
    summary="Project a pain.001 document into a face",
    dependencies=[Depends(require_api_key)],
    responses={
        404: {"description": "No face has this name"},
        422: {"description": "The face refused the document or a binding"},
    },
)
@traced("pain001.api.face", attributes={"http.route": "/api/v1/faces/{face}"})
async def project(face: str, request: FaceRequest) -> dict[str, Any]:
    """Project the document into ``face`` and report what was not carried.

    Args:
        face: The face name, one of ``GET /faces``.
        request: The document, its optional edition and the bindings.

    Returns:
        The face, the source edition, the payload and the loss report.

    Raises:
        HTTPException: ``404`` for an unknown face; ``422`` when the face
            refuses the document or a binding.
    """
    if face not in available_faces():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown face; available: {', '.join(available_faces())}",
        )
    try:
        result = await run_in_threadpool(
            project_face_text,
            request.xml,
            face,
            version=request.version,
            bindings=request.bindings,
        )
    except FaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return result.to_dict()
