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

_ALLOWED_MESSAGE_TYPES = frozenset(valid_xml_types)


def sanitise_message_type(message_type: str) -> str:
    """Re-validate ``message_type`` against the fixed allow-list.

    Args:
        message_type: The string value of a request's message-type enum.

    Returns:
        The same string, guaranteed to be one of
        :data:`pain001.constants.valid_xml_types`, and therefore safe to
        join into the bundled template and schema paths.

    Raises:
        HTTPException: ``400`` if the value is not in the allow-list.
    """
    if message_type not in _ALLOWED_MESSAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message type",
        )
    return message_type
