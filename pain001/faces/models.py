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

"""Data models and results for face projections (ADR-0005)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class FaceError(ValueError):
    """Raised when a face projection fails or an unsupported face is requested."""


@dataclass(frozen=True)
class LossReport:
    """Detailed report of mapped vs unmapped element paths in a projection.

    Attributes:
        face: The name of the projection standard.
        total_source_elements: Total number of leaf element paths in the source.
        mapped_paths: Element paths whose values were carried into the projection.
        unmapped_paths: Element paths present in the source that have no counterpart.
    """

    face: str
    total_source_elements: int
    mapped_paths: tuple[str, ...]
    unmapped_paths: tuple[str, ...]

    @property
    def is_lossless(self) -> bool:
        """True when every source element path was carried into the target projection."""
        return len(self.unmapped_paths) == 0

    @property
    def loss_ratio(self) -> float:
        """Proportion of source elements not mapped into the target projection (0.0 to 1.0)."""
        if self.total_source_elements == 0:
            return 0.0
        return len(self.unmapped_paths) / self.total_source_elements

    def to_dict(self) -> dict[str, Any]:
        """Convert the loss report into a JSON-serializable dictionary."""
        return {
            "face": self.face,
            "total_source_elements": self.total_source_elements,
            "mapped_count": len(self.mapped_paths),
            "unmapped_count": len(self.unmapped_paths),
            "is_lossless": self.is_lossless,
            "loss_ratio": round(self.loss_ratio, 4),
            "mapped_paths": list(self.mapped_paths),
            "unmapped_paths": list(self.unmapped_paths),
        }


@dataclass(frozen=True)
class FaceResult:
    """The result of projecting a pain.001 document into a target face.

    Attributes:
        face: The name of the target standard (e.g. ``uk_open_banking``).
        version: The pain.001 source edition (e.g. ``pain.001.001.09``).
        payload: The JSON-serializable dictionary conforming to the target standard.
        loss_report: Details of which elements were mapped vs omitted.
    """

    face: str
    version: str
    payload: dict[str, Any]
    loss_report: LossReport

    def to_dict(self) -> dict[str, Any]:
        """Return a complete dictionary containing payload and loss metadata."""
        return {
            "face": self.face,
            "version": self.version,
            "payload": self.payload,
            "loss_report": self.loss_report.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize the projection payload to formatted JSON."""
        return json.dumps(self.payload, indent=indent)
