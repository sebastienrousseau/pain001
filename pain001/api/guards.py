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

"""Taint barriers shared by the REST routers.

Pydantic already constrains request fields at the model boundary, but
static analysis does not track enum membership. Every router that turns
a request value into a filesystem path routes it through one of these
helpers first: an explicit allow-list check the CodeQL
``py/path-injection`` query recognises as a sanitiser, registered as a
neutral summary in ``.github/codeql/extensions/pain001-security.model.yml``.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from pain001.constants import valid_xml_types

#: The allow-list as a mapping from each accepted value to a constant
#: copy of itself. The lookup below returns the *constant*, not the
#: request string: taint does not flow from a subscript key to the
#: looked-up value, so everything downstream (template path, XSD path,
#: JSON schema path) is derived from a literal the request never touched.
_CANONICAL_MESSAGE_TYPES: dict[str, str] = {
    message_type: message_type for message_type in valid_xml_types
}


def sanitise_message_type(message_type: str) -> str:
    """Re-validate ``message_type`` against the fixed allow-list.

    Args:
        message_type: The string value of a request's message-type enum.

    Returns:
        The canonical constant for that message type, guaranteed to be
        one of :data:`pain001.constants.valid_xml_types` and therefore
        safe to join into the bundled template and schema paths.

    Raises:
        HTTPException: ``400`` if the value is not in the allow-list.
    """
    canonical = _CANONICAL_MESSAGE_TYPES.get(message_type)
    if canonical is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message type",
        )
    return canonical
