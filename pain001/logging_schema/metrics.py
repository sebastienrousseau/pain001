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

"""Detailed execution telemetry for API observability and tracing."""

import logging
import time

from pain001.logging_schema.context import (
    generate_request_id,
    set_request_id,
)
from pain001.logging_schema.events import log_event
from pain001.logging_schema.schema import Events, ExecutionStatus


class ExecutionMetrics:  # pylint: disable=too-many-instance-attributes
    """Enhanced execution metrics tracking with detailed telemetry.

    This class extends ExecutionSummaryTracker with additional metrics
    for API observability, performance monitoring, and distributed tracing.
    Tracks detailed timing breakdowns, resource usage, and validation results.

    Args:
        logger: Logger instance for telemetry output.
        operation: Operation being tracked (e.g., "xml_generation").
        message_type: ISO 20022 message type (if applicable).
        request_id: Request ID for distributed tracing
            (auto-generated if None).

    Example:
        >>> metrics = ExecutionMetrics(
        ...     logger=logger,
        ...     operation="xml_generation",
        ...     message_type="pain.001.001.03"
        ... )
        >>> metrics.start()
        >>> metrics.track_phase("data_load", duration_ms=120)
        >>> metrics.track_phase("xml_generation", duration_ms=350)
        >>> metrics.track_validation("schema", "PASSED")
        >>> metrics.log_telemetry()
    """

    def __init__(
        self,
        logger: logging.Logger,
        operation: str,
        message_type: str | None = None,
        request_id: str | None = None,
    ):
        self.logger = logger
        self.operation = operation
        self.message_type = message_type
        self.request_id = request_id or generate_request_id()
        set_request_id(self.request_id)

        # Timing metrics
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.phase_timings: dict[str, int] = {}  # phase_name -> duration_ms

        # Validation tracking
        self.validation_results: dict[
            str, str
        ] = {}  # validation_type -> status

        # Record counts
        self.records_processed = 0
        self.records_failed = 0

        # Status tracking
        self.status = ExecutionStatus.SUCCESS
        self.error_message: str | None = None

    def start(self) -> None:
        """Mark operation start time."""
        self.start_time = time.time()
        log_event(
            self.logger,
            logging.INFO,
            Events.PROCESS_START,
            operation=self.operation,
            message_type=self.message_type,
            request_id=self.request_id,
        )

    def track_phase(self, phase_name: str, duration_ms: int) -> None:
        """Track timing for a specific phase.

        Args:
            phase_name: Name of the phase (e.g., "data_load", "xml_generation").
            duration_ms: Duration in milliseconds.
        """
        self.phase_timings[phase_name] = duration_ms

    def track_validation(self, validation_type: str, status: str) -> None:
        """Track validation result.

        Args:
            validation_type: Type of validation (e.g., "schema", "business_rules").
            status: Result status (e.g., "PASSED", "FAILED").
        """
        self.validation_results[validation_type] = status
        if status == "FAILED":
            self.status = ExecutionStatus.FAILED

    def increment_processed(self, count: int = 1) -> None:
        """Increment processed record count.

        Args:
            count: Number of records to add (default: 1).
        """
        self.records_processed += count

    def increment_failed(self, count: int = 1) -> None:
        """Increment failed record count.

        Args:
            count: Number of failed records to add (default: 1).
        """
        self.records_failed += count
        self.status = ExecutionStatus.FAILED

    def set_error(self, error_message: str) -> None:
        """Set error message and mark as failed.

        Args:
            error_message: Error description.
        """
        self.error_message = error_message
        self.status = ExecutionStatus.FAILED

    def log_telemetry(self) -> None:
        """Log comprehensive telemetry report."""
        self.end_time = time.time()

        duration_ms = 0
        if self.start_time is not None:  # pragma: no cover
            duration_ms = int((self.end_time - self.start_time) * 1000)

        telemetry_data = {
            "operation": self.operation,
            "status": self.status,
            "duration_ms": duration_ms,
            "records_processed": self.records_processed,
            "records_failed": self.records_failed,
        }

        # Add message type if provided
        if self.message_type:
            telemetry_data["message_type"] = self.message_type

        # Add phase timings if tracked
        if self.phase_timings:
            telemetry_data["phase_timings"] = self.phase_timings

        # Add validation results if tracked
        if self.validation_results:
            telemetry_data["validation_results"] = self.validation_results

        # Add error message if present
        if self.error_message:
            telemetry_data["error_message"] = self.error_message

        log_event(
            self.logger,
            (
                logging.INFO
                if self.status == ExecutionStatus.SUCCESS
                else logging.ERROR
            ),
            Events.EXECUTION_SUMMARY,
            message="Execution Telemetry",
            telemetry=telemetry_data,
        )
