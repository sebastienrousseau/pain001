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

"""Standardized logging schema for Pain001.

This package provides a centralized logging structure for consistent,
machine-parsable log output across CLI and library components.
All log entries are JSON-formatted for easy integration with log
aggregation systems (Elasticsearch, Splunk, CloudWatch, etc.).

The implementation is split across focused submodules; this package
re-exports the full public surface, so ``from pain001.logging_schema
import ...`` continues to work unchanged:

- :mod:`~pain001.logging_schema.schema` — log level, status, event, and
  field name vocabularies (``LogLevel``, ``ExecutionStatus``, ``Events``,
  ``Fields``).
- :mod:`~pain001.logging_schema.context` — per-request id propagation.
- :mod:`~pain001.logging_schema.redaction` — PII masking and log-injection
  sanitization.
- :mod:`~pain001.logging_schema.events` — structured event emitters
  (``log_event`` and friends).
- :mod:`~pain001.logging_schema.tracker` — ``ExecutionSummaryTracker``.
- :mod:`~pain001.logging_schema.formatter` — ``JSONFormatter`` and
  ``configure_json_logging``.
- :mod:`~pain001.logging_schema.metrics` — ``ExecutionMetrics``.

IMPORTANT: PII Protection
-------------------------
This module implements automatic PII redaction for sensitive fields.
Any field containing IBAN, BIC, or personal names is automatically
masked before logging to ensure GDPR/PCI-DSS compliance.

Request Tracing
---------------
Every operation is assigned a unique request_id (UUID) to enable
end-to-end request tracking across distributed systems and microservices.
This is essential for API Layer (#149) observability.

Log Severity Mapping (ISO 20022 Context)
-----------------------------------------
- DEBUG: XSD traversal, template loading, variable substitution
- INFO: Process start/success, validation success, file generation
- WARNING: Schema deprecation, character truncation, missing optional fields
- ERROR: XSD validation failure, checksum failure, bank profile violations
- CRITICAL: Missing dependencies, memory overflow, configuration corruption

Event Naming Convention:
    - Use snake_case for event names
    - Format: <component>_<action>_<state>
    - Examples: "process_start", "validation_success", "xml_generated"

Field Naming Convention:
    - Use snake_case for field names
    - Be consistent with terminology across all events
    - Include units where applicable (e.g., "duration_ms", "size_bytes")
    - All logs are flat JSON objects for easy indexing
"""

from pain001.logging_schema._version import __version__
from pain001.logging_schema.context import (
    generate_request_id,
    get_request_id,
    set_request_id,
)
from pain001.logging_schema.events import (
    log_data_load_event,
    log_event,
    log_process_error,
    log_process_start,
    log_process_success,
    log_validation_event,
    log_xml_generation_event,
)
from pain001.logging_schema.formatter import (
    JSONFormatter,
    configure_json_logging,
)
from pain001.logging_schema.metrics import ExecutionMetrics
from pain001.logging_schema.redaction import (
    _redact_pii_from_dict,
    _sanitize_value,
    mask_sensitive_data,
)
from pain001.logging_schema.schema import (
    Events,
    ExecutionStatus,
    Fields,
    LogLevel,
)
from pain001.logging_schema.tracker import ExecutionSummaryTracker

__all__ = [
    "__version__",
    # schema
    "LogLevel",
    "ExecutionStatus",
    "Events",
    "Fields",
    # context
    "generate_request_id",
    "get_request_id",
    "set_request_id",
    # redaction
    "mask_sensitive_data",
    "_redact_pii_from_dict",
    "_sanitize_value",
    # events
    "log_event",
    "log_process_start",
    "log_process_success",
    "log_process_error",
    "log_validation_event",
    "log_data_load_event",
    "log_xml_generation_event",
    # tracker
    "ExecutionSummaryTracker",
    # formatter
    "JSONFormatter",
    "configure_json_logging",
    # metrics
    "ExecutionMetrics",
]
