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

API_KEY_ENV = "PAIN001_API_KEY"
"""Environment variable that, when set, turns bearer-token auth on."""

INSECURE_ENV = "PAIN001_ALLOW_INSECURE"
"""Environment variable that, when truthy, allows serving without a key
on a non-loopback address (the twin of ``pain001 serve --insecure``)."""

_TRUTHY = frozenset({"1", "true", "yes", "on"})

logger = logging.getLogger(__name__)


def insecure_allowed() -> bool:
    """Tell whether the operator opted into an unauthenticated server.

    Returns:
        True when ``PAIN001_ALLOW_INSECURE`` is ``1``, ``true``, ``yes``
        or ``on`` (any case).
    """
    return os.environ.get(INSECURE_ENV, "").strip().lower() in _TRUTHY


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
