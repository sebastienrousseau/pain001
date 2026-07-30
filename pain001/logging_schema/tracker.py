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

"""Execution summary tracking with automatic event counting."""

import logging
import time
from typing import Any

from pain001.logging_schema.events import log_event
from pain001.logging_schema.schema import Events, ExecutionStatus


class ExecutionSummaryTracker:  # pylint: disable=too-many-instance-attributes
    """Track execution metrics for final summary report.

    This class provides automatic log event counting and execution
    metrics tracking for generating comprehensive summary reports.
    Use as a context manager for automatic start/end tracking.

    Args:
        logger: Logger instance to use for summary report.
        dry_run: Whether this is a dry-run execution.
        message_type: ISO 20022 message type (if applicable).

    Example:
        >>> with ExecutionSummaryTracker(logger) as tracker:
        ...     # Your execution logic here
        ...     tracker.increment_processed_records(1250)
        ...     tracker.set_validation_result("schema_validation", "PASSED")
        # Summary report automatically logged on exit

        >>> # Or use manually:
        >>> tracker = ExecutionSummaryTracker(logger, dry_run=True)
        >>> tracker.start()
        >>> # ... execution logic ...
        >>> tracker.log_summary()
    """

    def __init__(
        self,
        logger: logging.Logger,
        dry_run: bool = False,
        message_type: str | None = None,
    ):
        self.logger = logger
        self.dry_run = dry_run
        self.message_type = message_type

        # Execution metrics
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.start_time_iso: str | None = None
        self.end_time_iso: str | None = None

        # Event counts
        self.counts = {
            "debug": 0,
            "info": 0,
            "warning": 0,
            "error": 0,
            "critical": 0,
        }

        # Processing metrics
        self.total_records_processed = 0
        self.validation_metrics: dict[str, str] = {}
        self.output_file: str | None = None
        self.log_file: str | None = None

        # Status tracking
        self.has_errors = False
        self.has_warnings = False
        self.aborted = False

    def start(self) -> None:
        """Mark execution start time."""
        self.start_time = time.time()
        self.start_time_iso = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )

    def increment_event_count(self, level: str) -> None:
        """Increment count for a specific log level.

        Args:
            level: Log level name (debug, info, warning, error, critical).
        """
        level_lower = level.lower()
        if level_lower in self.counts:  # pragma: no cover
            self.counts[level_lower] += 1

        if level_lower in ("error", "critical"):
            self.has_errors = True
        elif level_lower == "warning":
            self.has_warnings = True

    def increment_processed_records(self, count: int = 1) -> None:
        """Increment total records processed count.

        Args:
            count: Number of records to add (default: 1).
        """
        self.total_records_processed += count

    def set_validation_result(self, validation_type: str, result: str) -> None:
        """Set validation result for a specific validation type.

        Args:
            validation_type: Type of validation (e.g., "schema_validation").
            result: Result status (e.g., "PASSED", "FAILED").
        """
        self.validation_metrics[validation_type] = result

    def set_output_file(self, file_path: str | None) -> None:
        """Set output file path.

        Args:
            file_path: Path to generated output file (None for dry-run).
        """
        self.output_file = file_path

    def set_log_file(self, file_path: str) -> None:
        """Set log file path.

        Args:
            file_path: Path to log file.
        """
        self.log_file = file_path

    def abort(self) -> None:
        """Mark execution as aborted."""
        self.aborted = True

    def _get_status(self) -> str:
        """Determine execution status based on tracked metrics.

        Returns:
            Status string from ExecutionStatus constants.
        """
        if self.aborted:
            return ExecutionStatus.ABORTED
        if self.has_errors:
            return ExecutionStatus.FAILED
        if self.has_warnings:
            return ExecutionStatus.COMPLETED_WITH_WARNINGS
        return ExecutionStatus.SUCCESS

    def log_summary(self) -> None:
        """Log execution summary report."""
        self.end_time = time.time()
        self.end_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        duration_ms = 0
        if self.start_time is not None:  # pragma: no cover
            duration_ms = int((self.end_time - self.start_time) * 1000)

        summary_data = {
            "status": self._get_status(),
            "execution_mode": "dry_run" if self.dry_run else "production",
            "total_records_processed": self.total_records_processed,
            "counts": self.counts,
            "performance": {
                "start_time": self.start_time_iso,
                "end_time": self.end_time_iso,
                "total_duration_ms": duration_ms,
            },
        }

        # Add validation metrics if any were tracked
        if self.validation_metrics:
            summary_data["validation_metrics"] = self.validation_metrics  # type: ignore[assignment]

        # Add artifacts info
        output_file_value = "None"
        if self.output_file:
            output_file_value = self.output_file
        elif self.dry_run:
            output_file_value = "None (Dry Run)"

        summary_data["artifacts"] = {  # type: ignore[assignment]
            "output_file": output_file_value,
            "log_file": self.log_file if self.log_file else "None",
        }

        # Add message type if provided
        if self.message_type:
            summary_data["message_type"] = self.message_type

        log_event(
            self.logger,
            logging.INFO,
            Events.EXECUTION_SUMMARY,
            message="Execution Summary Report",
            summary=summary_data,
        )

    def __enter__(self) -> "ExecutionSummaryTracker":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - log summary automatically."""
        if exc_type is not None:
            # Exception occurred - mark as error and aborted
            self.increment_event_count("error")
            self.abort()

        self.log_summary()
