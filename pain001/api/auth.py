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

import logging
import os
import secrets

from fastapi import Header, HTTPException, status

# The settings live in a FastAPI-free module so the CLI can read them on
# a base install; they are re-exported here for the routers.
from pain001.security.api_access import (
    API_KEY_ENV,
    INSECURE_ENV,
    insecure_allowed,
)

logger = logging.getLogger(__name__)


def warn_if_unauthenticated() -> None:
    """Log a warning at start-up when the API runs without a key.

    ``pain001 serve`` refuses a non-loopback bind without a key; a
    server started by ``uvicorn`` directly cannot see its own bind
    address from the application, so it says so instead. An explicit
    opt-in (``PAIN001_ALLOW_INSECURE``) silences the warning.
    """
    if os.environ.get(API_KEY_ENV) or insecure_allowed():
        return
    # The variable names are spelled out: only names are logged here,
    # never the key, and CodeQL reads API_KEY_ENV itself as a secret.
    logger.warning(
        "PAIN001_API_KEY is unset: every endpoint is unauthenticated. "
        "Bind to loopback only, or set PAIN001_API_KEY (or "
        "PAIN001_ALLOW_INSECURE=1 to accept an open server)."
    )


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


__all__ = [
    "API_KEY_ENV",
    "INSECURE_ENV",
    "insecure_allowed",
    "require_api_key",
    "warn_if_unauthenticated",
]
