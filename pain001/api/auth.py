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

"""Bearer-token authentication shared by every REST router.

Lives in its own module so the dashboard router (:mod:`pain001.api.ui`)
and the application module can both depend on it without importing
each other.
"""

from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException, status

API_KEY_ENV = "PAIN001_API_KEY"
"""Environment variable that, when set, turns bearer-token auth on."""


def require_api_key(
    authorization: str | None = Header(default=None),
) -> None:
    """Enforce bearer-token auth when ``PAIN001_API_KEY`` is configured.

    When the environment variable is unset the API remains open
    (local development mode); set it in any shared deployment.

    Args:
        authorization: The raw ``Authorization`` header, if any.

    Raises:
        HTTPException: ``401`` when a key is configured and the header
            does not carry it.
    """
    expected = os.environ.get(API_KEY_ENV)
    if not expected:
        return
    provided = ""
    if authorization and authorization.startswith("Bearer "):
        provided = authorization[len("Bearer ") :]
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
