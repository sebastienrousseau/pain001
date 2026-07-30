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

"""Constant vocabularies for structured logging (levels, statuses, events,
fields).

These classes are namespaces of string constants rather than enums so they
serialize directly to JSON and read naturally at call sites.
"""


# Execution Status Constants
class LogLevel:  # pylint: disable=too-few-public-methods
    """Standard log level names for structured logging."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ExecutionStatus:  # pylint: disable=too-few-public-methods
    """High-level execution status for summary reports."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    ABORTED = "ABORTED"


# Standard Event Names
class Events:  # pylint: disable=too-few-public-methods
    """Standardized event names for structured logging."""

    # Process lifecycle events
    PROCESS_START = "process_start"
    PROCESS_SUCCESS = "process_success"
    PROCESS_ERROR = "process_error"
    EXECUTION_SUMMARY = "execution_summary"  # Final summary report

    # CLI events
    CLI_ARGS_PARSED = "cli_args_parsed"
    CLI_DRY_RUN = "cli_dry_run"

    # Validation events
    VALIDATION_START = "validation_start"
    VALIDATION_SUCCESS = "validation_success"
    VALIDATION_ERROR = "validation_error"

    # Data loading events
    DATA_LOAD_START = "data_load_start"
    DATA_LOAD_SUCCESS = "data_load_success"
    DATA_LOAD_ERROR = "data_load_error"

    # XML generation events
    XML_GENERATE_START = "xml_generate_start"
    XML_GENERATE_SUCCESS = "xml_generate_success"
    XML_GENERATE_ERROR = "xml_generate_error"

    # XSD validation events
    XSD_VALIDATION_START = "xsd_validation_start"
    XSD_VALIDATION_SUCCESS = "xsd_validation_success"
    XSD_VALIDATION_ERROR = "xsd_validation_error"

    # Namespace registration events
    NAMESPACE_REGISTER = "namespace_register"


# Standard Field Names
class Fields:  # pylint: disable=too-few-public-methods
    """Standardized field names for structured logging."""

    # Core fields (always present)
    EVENT = "event"
    TIMESTAMP = "timestamp"
    LEVEL = "level"
    REQUEST_ID = "request_id"  # UUID for request tracing
    LOGGER_NAME = "logger"

    # Component identification
    COMPONENT = "component"
    MODULE = "module"
    FUNCTION = "function"
    VERSION = "version"  # Pain001 library version

    # Message type and version
    MESSAGE_TYPE = "message_type"
    ISO_VERSION = "iso_version"
    DRY_RUN = "dry_run"  # Boolean flag
    BANK_PROFILE = "bank_profile"  # e.g., hsbc_uk, jpm_cbpr_plus

    # File paths (never log sensitive data)
    TEMPLATE_PATH = "template_path"
    SCHEMA_PATH = "schema_path"
    DATA_SOURCE_TYPE = "data_source_type"  # csv, sqlite, list, dict

    # Record counts and statistics
    RECORD_COUNT = "record_count"
    TRANSACTION_COUNT = "transaction_count"

    # Performance metrics
    DURATION_MS = "duration_ms"
    SIZE_BYTES = "size_bytes"

    # Error information (flat structure)
    ERROR_TYPE = "error_type"
    ERROR_MESSAGE = "error_message"
    ERROR_FIELD = "error_field"  # Which field failed validation
    ERROR_INVALID_VALUE = (
        "error_invalid_value"  # The invalid value (masked if PII)
    )
    ERROR_REASON = (
        "error_reason"  # Detailed reason (e.g., "Invalid checksum (ISO 7064)")
    )

    # Validation details
    VALIDATION_TYPE = "validation_type"  # schema, data, business_rules
    END_TO_END_ID = "end_to_end_id"  # Transaction reference for tracing
