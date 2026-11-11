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

"""Configuration checks the REST app runs once, when its server starts."""

from __future__ import annotations

from pain001.api._pipeline import pipeline_limit
from pain001.api.auth import warn_if_unauthenticated
from pain001.api.limits import max_body_bytes


def startup_checks() -> None:
    """Check the server's configuration before it takes traffic.

    Reads ``PAIN001_API_CONCURRENCY`` and ``PAIN001_MAX_BODY_BYTES`` so
    a bad value stops start-up rather than failing the first request,
    and warns when the API runs without ``PAIN001_API_KEY`` (a server
    started by ``uvicorn`` directly cannot refuse an open bind the way
    ``pain001 serve`` does).
    """
    pipeline_limit()
    max_body_bytes()
    warn_if_unauthenticated()
