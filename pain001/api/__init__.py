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

"""Pain001 FastAPI REST API module."""

try:
    import fastapi  # noqa: F401
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "The REST API requires the 'api' extra. "
        "Install with: pip install pain001[api]"
    ) from _e

from pain001.api.app import app  # noqa: F401
from pain001.api.job_manager import (  # noqa: F401
    JobManager,
    JobStatus,
    job_manager,
)
from pain001.api.job_store import (  # noqa: F401
    FileJobStore,
    JobStore,
    job_store_from_env,
)
from pain001.api.metrics import (  # noqa: F401
    MetricsMiddleware,
    render_prometheus,
)
from pain001.api.models import (
    DataSourceType,
    GenerateXMLRequest,
    GenerateXMLResponse,
    HealthResponse,
    JobStatusResponse,
    MessageType,
    ValidationError,
    ValidationRequest,
    ValidationResponse,
)
from pain001.api.ratelimit import (  # noqa: F401
    RateLimitMiddleware,
    parse_rate_limit,
)

__all__ = [
    "app",
    "JobManager",
    "JobStatus",
    "job_manager",
    "FileJobStore",
    "JobStore",
    "job_store_from_env",
    "RateLimitMiddleware",
    "parse_rate_limit",
    "MetricsMiddleware",
    "render_prometheus",
    "DataSourceType",
    "GenerateXMLRequest",
    "GenerateXMLResponse",
    "HealthResponse",
    "JobStatusResponse",
    "MessageType",
    "ValidationError",
    "ValidationRequest",
    "ValidationResponse",
]
