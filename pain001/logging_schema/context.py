# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Per-request ID propagation for distributed tracing."""

import uuid
from contextvars import ContextVar

# ContextVar rather than a module global or threading.local: the API
# serves concurrent async requests, and each task must see its own
# request id without leaking it to other in-flight requests.
_request_id_context: ContextVar[str | None] = ContextVar(
    "request_id", default=None
)


def generate_request_id() -> str:
    """Generate a unique request ID for request tracing.

    Returns:
        A short UUID-based request ID (format: req-<8-char-hex>).

    Example:
        >>> generate_request_id()
        'req-88f24b21'
    """
    return f"req-{uuid.uuid4().hex[:8]}"


def get_request_id() -> str:
    """Get or create request ID for current context.

    Returns:
        The request ID for the current execution context.
    """
    request_id = _request_id_context.get()
    if request_id is None:
        request_id = generate_request_id()
        _request_id_context.set(request_id)
    return request_id


def set_request_id(request_id: str) -> None:
    """Set request ID for current context (useful for API handlers).

    Args:
        request_id: The request ID to set.
    """
    _request_id_context.set(request_id)
