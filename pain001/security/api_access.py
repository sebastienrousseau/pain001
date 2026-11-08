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

"""Who may reach the REST API: the settings, without the server.

``pain001 serve`` decides at start-up whether it may bind an address,
and the REST app enforces bearer auth per request. Both read these
settings, but the CLI runs on a base install, where FastAPI (the
``api`` extra) is absent, so they live here, free of it.
:mod:`pain001.api.auth` re-exports them.
"""

from __future__ import annotations

import os

API_KEY_ENV = "PAIN001_API_KEY"
"""Environment variable that, when set, turns bearer-token auth on."""

INSECURE_ENV = "PAIN001_ALLOW_INSECURE"
"""Environment variable that, when truthy, allows serving without a key
on a non-loopback address (the twin of ``pain001 serve --insecure``)."""

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def insecure_allowed() -> bool:
    """Tell whether the operator opted into an unauthenticated server.

    Returns:
        True when ``PAIN001_ALLOW_INSECURE`` is ``1``, ``true``, ``yes``
        or ``on`` (any case).
    """
    return os.environ.get(INSECURE_ENV, "").strip().lower() in _TRUTHY


__all__ = ["API_KEY_ENV", "INSECURE_ENV", "insecure_allowed"]
