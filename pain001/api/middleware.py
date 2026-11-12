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

"""The REST API's middleware stack, in one place and in order."""

from __future__ import annotations

from typing import Any

from pain001.api.host_guard import HostGuardMiddleware
from pain001.api.limits import install_body_limit
from pain001.api.metrics import MetricsMiddleware
from pain001.api.ratelimit import install_rate_limiting
from pain001.api.request_context import RequestContextMiddleware


def install_middleware(application: Any) -> None:
    """Wrap the application in its middleware, innermost first.

    From the outside in: the request context (request id, inbound trace
    context, server span), so every answer is traced and carries
    ``X-Request-ID``; the host guard, which keeps a server without
    ``PAIN001_API_KEY`` to requests addressed to loopback; the body limit; the rate limiter, when
    ``PAIN001_RATE_LIMIT`` is set; then the request metrics.

    Args:
        application: The FastAPI (or Starlette) application to wrap.
    """
    application.add_middleware(MetricsMiddleware)
    install_rate_limiting(application)
    install_body_limit(application)
    application.add_middleware(HostGuardMiddleware)
    application.add_middleware(RequestContextMiddleware)
