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

"""Engine for face projections from pain.001 to external specifications (ADR-0005).

The engine builds the ISO JSON twin, runs the face's projector and
writes the loss report from indexed leaf paths: every occurrence of a
repeated element is its own entry, so a dropped transaction can never
pass for a mapped one. Faces are outbound only.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pain001.faces import berlin_group, iso_2018, uk_open_banking
from pain001.faces.models import FaceError, FaceResult, LossReport
from pain001.faces.paths import leaf_paths
from pain001.twins.iso_json import to_iso_json

FaceFunc = Callable[
    [dict[str, Any], dict[str, Any] | None], tuple[dict[str, Any], set[str]]
]


@dataclass(frozen=True)
class _Face:
    """A registered face: its projector, description and allowed bindings."""

    func: FaceFunc
    description: str
    bindings: tuple[str, ...]


_REGISTRY: dict[str, _Face] = {
    uk_open_banking.FACE: _Face(
        uk_open_banking.project_uk_open_banking,
        "UK Open Banking Read/Write API v4.0.1 domestic payment "
        "(OBWriteDomesticConsent4; OBWriteDomestic2 with a ConsentId)",
        uk_open_banking.BINDINGS,
    ),
    berlin_group.FACE: _Face(
        berlin_group.project_berlin_group,
        "Berlin Group NextGenPSD2 XS2A v1.3.16 payment initiation "
        "(single or bulk JSON body)",
        berlin_group.BINDINGS,
    ),
    iso_2018.FACE: _Face(
        iso_2018.project_iso_2018,
        "ISO 20022 element names in snake_case, from the Message "
        "Definition Reports",
        iso_2018.BINDINGS,
    ),
}

_VERSION_RE = re.compile(
    r"urn:iso:std:iso:20022:tech:xsd:(pain\.001\.001\.\d{2})"
)


def detect_version(xml: str) -> str:
    """Detect the pain.001 edition from XML namespace declarations.

    Args:
        xml: The XML text of the document.

    Returns:
        The detected version string, e.g. ``pain.001.001.09``.

    Raises:
        FaceError: If no supported pain.001 namespace is detected.
    """
    match = _VERSION_RE.search(xml)
    if not match:
        raise FaceError(
            "could not detect pain.001 edition from XML namespace; "
            "provide explicit version parameter"
        )
    return match.group(1)


def available_faces() -> list[str]:
    """Return a sorted list of registered face names."""
    return sorted(_REGISTRY)


def list_supported_faces() -> list[dict[str, Any]]:
    """Return each face with its description and accepted binding keys."""
    return [
        {
            "name": name,
            "description": face.description,
            "bindings": list(face.bindings),
        }
        for name, face in sorted(_REGISTRY.items())
    ]


def register_face(
    name: str,
    func: FaceFunc,
    description: str,
    bindings: tuple[str, ...] = (),
) -> None:
    """Register a new projection face.

    Args:
        name: Unique name for the face.
        func: Projection function returning ``(payload, mapped_paths)``,
            where the paths are indexed leaf paths relative to
            ``Document`` (see :func:`pain001.faces.paths.leaf_paths`).
        description: Description of the target standard.
        bindings: Binding keys the face accepts; any other is refused.
    """
    _REGISTRY[name] = _Face(func, description, tuple(bindings))


def _read_source(source: str | Path) -> str:
    """The XML text of ``source``: a path, or XML given inline."""
    if isinstance(source, Path):
        return source.read_text(encoding="utf-8")
    if not source.lstrip().startswith("<") and Path(source).is_file():
        return Path(source).read_text(encoding="utf-8")
    return source


def project_face(
    source: str | Path,
    face: str = "uk_open_banking",
    *,
    version: str | None = None,
    bindings: dict[str, Any] | None = None,
) -> FaceResult:
    """Project a pain.001 document into an external industry standard face.

    Args:
        source: XML string or Path to an XML file.
        face: The name of the target standard (default: ``uk_open_banking``).
        version: Optional explicit pain.001 edition (detected if omitted).
        bindings: Optional private side inputs the face accepts (for
            example ``ConsentId`` for UK Open Banking). Keep them out of
            version control: they are never part of the source message.

    Returns:
        A :class:`FaceResult` with payload and explicit :class:`LossReport`.

    Raises:
        FaceError: If the face is unknown, a binding is not accepted, the
            twin cannot be built or the face refuses the document.
    """
    entry = _REGISTRY.get(face)
    if entry is None:
        raise FaceError(
            f"unknown face '{face}'; available faces: {', '.join(available_faces())}"
        )
    unknown = sorted(set(bindings or {}) - set(entry.bindings))
    if unknown:
        accepted = ", ".join(entry.bindings) or "none"
        raise FaceError(
            f"{face}: unknown binding(s) {', '.join(unknown)}; accepted: {accepted}"
        )
    xml_text = _read_source(source)
    if version is None:
        version = detect_version(xml_text)
    try:
        twin = to_iso_json(xml_text, version)
    except Exception as exc:
        raise FaceError(f"failed to generate ISO JSON twin: {exc}") from exc

    leaves = leaf_paths(twin)
    payload, raw_mapped = entry.func(twin, bindings)
    mapped = tuple(sorted(raw_mapped & leaves))
    return FaceResult(
        face=face,
        version=version,
        payload=payload,
        loss_report=LossReport(
            face=face,
            total_source_elements=len(leaves),
            mapped_paths=mapped,
            unmapped_paths=tuple(sorted(leaves - set(mapped))),
        ),
    )
