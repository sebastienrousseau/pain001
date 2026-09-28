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

"""Security utilities for Pain001."""

from pain001.security.dsig import (
    XmlSignatureError,
    canonicalize_xml,
    compute_sha256_digest,
    sign_xml_document,
    verify_xml_signature,
)
from pain001.security.formula import (
    FORMULA_PREFIXES,
    sanitize_formula_injection,
)
from pain001.security.path_validator import sanitize_for_log, validate_path

__all__ = [
    "FORMULA_PREFIXES",
    "XmlSignatureError",
    "canonicalize_xml",
    "compute_sha256_digest",
    "sanitize_for_log",
    "sanitize_formula_injection",
    "sign_xml_document",
    "validate_path",
    "verify_xml_signature",
]
