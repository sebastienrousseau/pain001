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

"""Twins: lossless representations of the same pain.001 message (ADR-0005).

A twin carries everything the XML carries and comes back as the same
XML, element for element. The canonical twin is the ISO 20022
Registration Authority's JSON convention of 2025
(:mod:`pain001.twins.iso_json`); the records twin
(:mod:`pain001.twins.records`) is the library's own flat input rows with
the list of what they cannot carry. Faces, which project a message for a
compatible standard with a loss report, are a later layer.
"""

from pain001.twins.iso_json import (
    SUPPORTED_PREFIX,
    TwinError,
    from_iso_json,
    supported,
    to_iso_json,
)
from pain001.twins.records import (
    RecordsTwin,
    column_paths,
    preparer_required,
    to_records,
)
from pain001.twins.schema import (
    generate_schema,
    iso_json_schema,
    validate_iso_json,
)

__all__ = [
    "RecordsTwin",
    "SUPPORTED_PREFIX",
    "TwinError",
    "column_paths",
    "preparer_required",
    "to_records",
    "from_iso_json",
    "generate_schema",
    "iso_json_schema",
    "supported",
    "to_iso_json",
    "validate_iso_json",
]
