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

"""Structured event emitters that build flat, PII-redacted JSON log records."""

import json
import logging
import time
from typing import Any

from pain001.logging_schema._version import __version__
from pain001.logging_schema.context import get_request_id
from pain001.logging_schema.redaction import _redact_pii_from_dict
from pain001.logging_schema.schema import Events, Fields


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Log a structured event with standardized format and PII redaction.

    This function automatically:
    1. Adds request_id for distributed tracing
    2. Adds ISO 8601 timestamp
    3. Redacts PII before logging (GDPR/PCI-DSS compliance)
    4. Outputs flat JSON for easy indexing

    Args:
        logger: The logger instance to use.
        level: Logging level (logging.INFO, logging.ERROR, etc.).
        event: Event name from Events class.
        **fields: Additional fields to include in the log entry.

    Example:
        >>> log_event(
        ...     logger,
        ...     logging.INFO,
        ...     Events.PROCESS_START,
        ...     message_type="pain.001.001.03",
        ...     record_count=10
        ... )
        # Output: {"timestamp": "2026-01-14T21:59:55Z", "level": "INFO",
        #          "request_id": "req-88f24b21", "event": "process_start", ...}
    """

    # Build flat JSON structure
    log_data = {
        Fields.TIMESTAMP: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        Fields.LEVEL: logging.getLevelName(level),
        Fields.LOGGER_NAME: logger.name,
        Fields.REQUEST_ID: get_request_id(),
        Fields.EVENT: event,
        Fields.VERSION: __version__,
        **fields,
    }

    # Redact PII before logging
    redacted_data = _redact_pii_from_dict(log_data)

    logger.log(level, json.dumps(redacted_data, sort_keys=True))


def log_process_start(
    logger: logging.Logger,
    message_type: str,
    data_source_type: str,
    **extra_fields: Any,
) -> float:
    """Log process start event and return start timestamp.

    Args:
        logger: The logger instance to use.
        message_type: ISO 20022 message type.
        data_source_type: Type of data source (csv, sqlite, list, dict).
        **extra_fields: Additional fields to include.

    Returns:
        Start timestamp for duration calculation.
    """
    start_time = time.time()
    log_event(
        logger,
        logging.INFO,
        Events.PROCESS_START,
        message_type=message_type,
        data_source_type=data_source_type,
        **extra_fields,
    )
    return start_time


def log_process_success(
    logger: logging.Logger,
    start_time: float,
    message_type: str,
    record_count: int,
    **extra_fields: Any,
) -> None:
    """Log process success event with duration.

    Args:
        logger: The logger instance to use.
        start_time: Start timestamp from log_process_start().
        message_type: ISO 20022 message type.
        record_count: Number of records processed.
        **extra_fields: Additional fields to include.
    """
    duration_ms = int((time.time() - start_time) * 1000)
    log_event(
        logger,
        logging.INFO,
        Events.PROCESS_SUCCESS,
        message_type=message_type,
        record_count=record_count,
        duration_ms=duration_ms,
        **extra_fields,
    )


def log_process_error(
    logger: logging.Logger,
    error: Exception,
    message_type: str | None = None,
    **extra_fields: Any,
) -> None:
    """Log process error event.

    Args:
        logger: The logger instance to use.
        error: The exception that occurred.
        message_type: ISO 20022 message type (if known).
        **extra_fields: Additional fields to include.
    """
    log_event(
        logger,
        logging.ERROR,
        Events.PROCESS_ERROR,
        error_type=type(error).__name__,
        error_message=str(error),
        message_type=message_type,
        **extra_fields,
    )


def log_validation_event(
    logger: logging.Logger,
    validation_type: str,
    success: bool,
    error: Exception | None = None,
    **extra_fields: Any,
) -> None:
    """Log validation event (success or error).

    Args:
        logger: The logger instance to use.
        validation_type: Type of validation (schema, data, business_rules).
        success: Whether validation succeeded.
        error: Exception if validation failed (None if success).
        **extra_fields: Additional fields to include.
    """
    if success:
        log_event(
            logger,
            logging.INFO,
            Events.VALIDATION_SUCCESS,
            validation_type=validation_type,
            **extra_fields,
        )
    else:
        log_event(
            logger,
            logging.ERROR,
            Events.VALIDATION_ERROR,
            validation_type=validation_type,
            error_type=type(error).__name__ if error else "Unknown",
            error_message=str(error) if error else "Validation failed",
            **extra_fields,
        )


def log_data_load_event(
    logger: logging.Logger,
    data_source_type: str,
    success: bool,
    record_count: int | None = None,
    error: Exception | None = None,
    duration_ms: int | None = None,
) -> None:
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    """Log data loading event.

    Args:
        logger: The logger instance to use.
        data_source_type: Type of data source (csv, sqlite, list, dict).
        success: Whether data loading succeeded.
        record_count: Number of records loaded (if success).
        error: Exception if loading failed (None if success).
        duration_ms: Loading duration in milliseconds.
    """
    if success:
        log_event(
            logger,
            logging.INFO,
            Events.DATA_LOAD_SUCCESS,
            data_source_type=data_source_type,
            record_count=record_count,
            duration_ms=duration_ms,
        )
    else:
        log_event(
            logger,
            logging.ERROR,
            Events.DATA_LOAD_ERROR,
            data_source_type=data_source_type,
            error_type=type(error).__name__ if error else "Unknown",
            error_message=str(error) if error else "Data load failed",
        )


def log_xml_generation_event(
    logger: logging.Logger,
    message_type: str,
    success: bool,
    record_count: int | None = None,
    error: Exception | None = None,
    duration_ms: int | None = None,
) -> None:
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    """Log XML generation event.

    Args:
        logger: The logger instance to use.
        message_type: ISO 20022 message type.
        success: Whether XML generation succeeded.
        record_count: Number of records in generated XML.
        error: Exception if generation failed (None if success).
        duration_ms: Generation duration in milliseconds.
    """
    if success:
        log_event(
            logger,
            logging.INFO,
            Events.XML_GENERATE_SUCCESS,
            message_type=message_type,
            record_count=record_count,
            duration_ms=duration_ms,
        )
    else:
        log_event(
            logger,
            logging.ERROR,
            Events.XML_GENERATE_ERROR,
            message_type=message_type,
            error_type=type(error).__name__ if error else "Unknown",
            error_message=str(error) if error else "XML generation failed",
        )
