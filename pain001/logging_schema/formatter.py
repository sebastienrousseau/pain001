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

"""JSON log formatter and handler configuration (Issue #149)."""

import json
import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path
from typing import Any

from pain001.logging_schema._version import __version__
from pain001.logging_schema.context import get_request_id
from pain001.logging_schema.schema import Fields


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging output.

    This formatter ensures all log records are emitted as valid JSON,
    regardless of the logging method used (logger.info(), logger.error(), etc.).
    It automatically adds standard fields (timestamp, level, logger name,
    request_id) and merges them with structured log_event() calls.

    Example:
        >>> handler = logging.StreamHandler()
        >>> handler.setFormatter(JSONFormatter())
        >>> logger.addHandler(handler)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: LogRecord to format.

        Returns:
            JSON-formatted log entry as string.
        """

        # Try to parse existing JSON from log_event() calls
        try:
            # If message is already JSON from log_event(), use it
            log_data: dict[str, Any] = json.loads(record.getMessage())
        except (json.JSONDecodeError, ValueError):
            # Plain text message - wrap in JSON structure
            log_data = {
                Fields.TIMESTAMP: time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)
                ),
                Fields.LEVEL: record.levelname,
                Fields.LOGGER_NAME: record.name,
                Fields.REQUEST_ID: get_request_id(),
                Fields.VERSION: __version__,
                "message": record.getMessage(),
            }

            # Add exception info if present
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, sort_keys=True)


def configure_json_logging(
    logger: logging.Logger | None = None,
    level: str | int = logging.INFO,
    log_file: str | None = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    console_output: bool = True,
) -> logging.Logger:
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    """Configure structured JSON logging for Pain001.

    This function sets up production-ready JSON logging with:
    - JSON formatter for all handlers
    - Optional file rotation (for persistent logs)
    - Console output (for containerized environments)
    - PII redaction (automatic via log_event())
    - Request ID tracing

    Environment Variables:
        PAIN001_LOG_LEVEL: Override log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        PAIN001_LOG_FILE: Override log file path
        PAIN001_LOG_JSON: Enable JSON logging (true/false)

    Args:
        logger: Logger to configure (defaults to root logger).
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Path to log file (None = console only).
        max_bytes: Max file size before rotation (default: 10MB).
        backup_count: Number of backup files to keep (default: 5).
        console_output: Whether to log to console (default: True).

    Returns:
        Configured logger instance.

    Example:
        >>> # Simple console logging
        >>> logger = configure_json_logging()
        >>> log_event(logger, logging.INFO, Events.PROCESS_START)

        >>> # Production setup with file rotation
        >>> logger = configure_json_logging(
        ...     log_file="/var/log/pain001/app.log",
        ...     level=logging.INFO,
        ...     max_bytes=50*1024*1024,  # 50MB
        ...     backup_count=10
        ... )

        >>> # Docker/Kubernetes setup (console only)
        >>> logger = configure_json_logging(console_output=True)
    """
    # Default to the package logger — never reconfigure the host
    # application's root logger implicitly.
    if logger is None:
        logger = logging.getLogger("pain001")

    # Apply environment variable overrides
    env_level = os.environ.get("PAIN001_LOG_LEVEL")
    if env_level:
        level = getattr(logging, env_level.upper(), level)

    env_log_file = os.environ.get("PAIN001_LOG_FILE")
    if env_log_file:
        log_file = env_log_file

    # Clear existing handlers to avoid duplicates
    logger.handlers = []
    logger.setLevel(level)

    formatter = JSONFormatter()

    # Console handler (for Docker/K8s or dev environments)
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler with rotation (for persistent logs)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
