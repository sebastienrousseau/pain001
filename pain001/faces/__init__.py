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

"""Faces: project pain.001 messages into compatible standards with loss reports (ADR-0005).

A face projects a pain.001 payment message into an external industry standard
or rail convention: UK Open Banking v4.0.1 domestic payments, Berlin Group
NextGenPSD2 v1.3.16 payment initiation, or ISO 20022 element names in
snake_case. Every occurrence of every source element is either carried into the
payload or listed in an explicit :class:`LossReport`; a face never invents a
value the target requires, it refuses the document with a :class:`FaceError`.
"""

from __future__ import annotations

from pain001.faces.engine import (
    MAX_INLINE_BYTES,
    available_faces,
    detect_version,
    list_supported_faces,
    project_face,
    project_face_text,
    register_face,
)
from pain001.faces.models import FaceError, FaceResult, LossReport

__all__ = [
    "MAX_INLINE_BYTES",
    "FaceError",
    "FaceResult",
    "LossReport",
    "available_faces",
    "detect_version",
    "list_supported_faces",
    "project_face",
    "project_face_text",
    "register_face",
]
