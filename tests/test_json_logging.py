# Copyright (C) 2023-2026 Sebastien Rousseau.
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

"""Tests for JSON logging configuration and telemetry (Issue #149)."""

import json
import logging
import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from typing import Any

from pain001.logging_schema import (
    Events,
    ExecutionMetrics,
    ExecutionStatus,
    Fields,
    JSONFormatter,
    configure_json_logging,
    log_event,
    set_request_id,
)


class TestJSONFormatter(unittest.TestCase):
    """Test JSONFormatter for structured logging."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.logger = logging.getLogger("test_json_formatter")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []

        # Add StringIO handler with JSON formatter
        self.log_stream = StringIO()
        handler = logging.StreamHandler(self.log_stream)
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.logger.handlers = []
        self.log_stream.close()

    def _get_last_log_entry(self) -> dict[str, Any]:
        """Parse the last log entry as JSON."""
        log_output = self.log_stream.getvalue()
        lines = log_output.strip().split("\n")
        if not lines or not lines[-1]:
            return {}
        parsed: dict[str, Any] = json.loads(lines[-1])
        return parsed

    def test_json_formatter_with_log_event(self) -> None:
        """Test JSONFormatter with structured log_event() calls."""
        log_event(
            self.logger,
            logging.INFO,
            Events.PROCESS_START,
            message_type="pain.001.001.03",
            data_source_type="csv",
        )

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.PROCESS_START)
        self.assertEqual(entry[Fields.MESSAGE_TYPE], "pain.001.001.03")
        self.assertEqual(entry[Fields.DATA_SOURCE_TYPE], "csv")
        self.assertIn(Fields.TIMESTAMP, entry)
        self.assertIn(Fields.REQUEST_ID, entry)

    def test_json_formatter_with_plain_text(self) -> None:
        """Test JSONFormatter wraps plain text messages in JSON."""
        self.logger.info("Plain text message")

        entry = self._get_last_log_entry()
        self.assertEqual(entry["message"], "Plain text message")
        self.assertEqual(entry[Fields.LEVEL], "INFO")
        self.assertIn(Fields.TIMESTAMP, entry)
        self.assertIn(Fields.REQUEST_ID, entry)

    def test_json_formatter_with_exception(self) -> None:
        """Test JSONFormatter includes exception info."""
        try:
            raise ValueError("Test exception")
        except ValueError:
            self.logger.exception("Error occurred")

        entry = self._get_last_log_entry()
        self.assertEqual(entry["message"], "Error occurred")
        self.assertIn("exception", entry)
        self.assertIn("ValueError: Test exception", entry["exception"])

    def test_json_formatter_sorts_keys(self) -> None:
        """Test that JSON output has sorted keys for consistency."""
        log_event(
            self.logger,
            logging.INFO,
            Events.PROCESS_START,
            zebra="last",
            alpha="first",
        )

        log_output = self.log_stream.getvalue().strip()
        # Keys should be alphabetically sorted in JSON string
        self.assertLess(
            log_output.index('"alpha"'), log_output.index('"zebra"')
        )


class TestConfigureJSONLogging(unittest.TestCase):
    """Test configure_json_logging() function."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Clear any environment variables
        for key in [
            "PAIN001_LOG_LEVEL",
            "PAIN001_LOG_FILE",
            "PAIN001_LOG_JSON",
        ]:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        # Clear environment variables
        for key in [
            "PAIN001_LOG_LEVEL",
            "PAIN001_LOG_FILE",
            "PAIN001_LOG_JSON",
        ]:
            os.environ.pop(key, None)

    def test_configure_console_only(self) -> None:
        """Test configure_json_logging with console output only."""
        logger = logging.getLogger("test_console")
        configure_json_logging(logger=logger, console_output=True)

        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], logging.StreamHandler)
        self.assertIsInstance(logger.handlers[0].formatter, JSONFormatter)

    def test_configure_with_log_file(self) -> None:
        """Test configure_json_logging with file output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            logger = logging.getLogger("test_file")

            configure_json_logging(
                logger=logger, log_file=log_file, console_output=False
            )

            self.assertEqual(len(logger.handlers), 1)
            self.assertIsInstance(
                logger.handlers[0], logging.handlers.RotatingFileHandler
            )
            self.assertTrue(Path(log_file).exists())

    def test_configure_with_both_outputs(self) -> None:
        """Test configure_json_logging with console + file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            logger = logging.getLogger("test_both")

            configure_json_logging(
                logger=logger, log_file=log_file, console_output=True
            )

            self.assertEqual(len(logger.handlers), 2)
            # Should have both console and file handlers
            handler_types = {type(h).__name__ for h in logger.handlers}
            self.assertIn("StreamHandler", handler_types)
            self.assertIn("RotatingFileHandler", handler_types)

    def test_configure_log_level(self) -> None:
        """Test configure_json_logging sets correct log level."""
        logger = logging.getLogger("test_level")
        configure_json_logging(logger=logger, level=logging.DEBUG)

        self.assertEqual(logger.level, logging.DEBUG)

    def test_configure_env_override_level(self) -> None:
        """Test PAIN001_LOG_LEVEL environment variable override."""
        os.environ["PAIN001_LOG_LEVEL"] = "DEBUG"
        logger = logging.getLogger("test_env_level")

        configure_json_logging(logger=logger, level=logging.INFO)

        self.assertEqual(logger.level, logging.DEBUG)

    def test_configure_env_override_file(self) -> None:
        """Test PAIN001_LOG_FILE environment variable override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_log_file = os.path.join(tmpdir, "env_override.log")
            os.environ["PAIN001_LOG_FILE"] = env_log_file

            logger = logging.getLogger("test_env_file")
            configure_json_logging(logger=logger, console_output=False)

            self.assertTrue(Path(env_log_file).exists())

    def test_configure_creates_log_directory(self) -> None:
        """Test that configure_json_logging creates log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "subdir", "deep", "test.log")
            logger = logging.getLogger("test_mkdir")

            configure_json_logging(
                logger=logger, log_file=log_file, console_output=False
            )

            self.assertTrue(Path(log_file).parent.exists())
            self.assertTrue(Path(log_file).exists())

    def test_configure_rotation_params(self) -> None:
        """Test file rotation parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            logger = logging.getLogger("test_rotation")

            configure_json_logging(
                logger=logger,
                log_file=log_file,
                max_bytes=1024 * 1024,  # 1MB
                backup_count=3,
                console_output=False,
            )

            file_handler = logger.handlers[0]
            self.assertIsInstance(
                file_handler, logging.handlers.RotatingFileHandler
            )
            self.assertEqual(file_handler.maxBytes, 1024 * 1024)
            self.assertEqual(file_handler.backupCount, 3)

    def test_configure_clears_existing_handlers(self) -> None:
        """Test that configure_json_logging clears existing handlers."""
        logger = logging.getLogger("test_clear")
        # Add a dummy handler
        logger.addHandler(logging.StreamHandler())
        self.assertEqual(len(logger.handlers), 1)

        configure_json_logging(logger=logger)

        # Should have replaced the handler (still 1 handler)
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0].formatter, JSONFormatter)


class TestExecutionMetrics(unittest.TestCase):
    """Test ExecutionMetrics class for telemetry tracking."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.logger = logging.getLogger("test_metrics")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []

        # Add StringIO handler to capture log output
        self.log_stream = StringIO()
        handler = logging.StreamHandler(self.log_stream)
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.logger.handlers = []
        self.log_stream.close()

    def _get_last_log_entry(self) -> dict[str, Any]:
        """Parse the last log entry as JSON."""
        log_output = self.log_stream.getvalue()
        lines = log_output.strip().split("\n")
        if not lines or not lines[-1]:
            return {}
        parsed: dict[str, Any] = json.loads(lines[-1])
        return parsed

    def test_execution_metrics_initialization(self) -> None:
        """Test ExecutionMetrics initialization."""
        metrics = ExecutionMetrics(
            logger=self.logger,
            operation="xml_generation",
            message_type="pain.001.001.03",
            request_id="req-test123",
        )

        self.assertEqual(metrics.operation, "xml_generation")
        self.assertEqual(metrics.message_type, "pain.001.001.03")
        self.assertEqual(metrics.request_id, "req-test123")
        self.assertEqual(metrics.records_processed, 0)
        self.assertEqual(metrics.records_failed, 0)
        self.assertEqual(metrics.status, ExecutionStatus.SUCCESS)

    def test_execution_metrics_auto_request_id(self) -> None:
        """Test ExecutionMetrics auto-generates request_id."""
        metrics = ExecutionMetrics(
            logger=self.logger,
            operation="xml_generation",
        )

        self.assertIsNotNone(metrics.request_id)
        self.assertTrue(metrics.request_id.startswith("req-"))

    def test_execution_metrics_start(self) -> None:
        """Test ExecutionMetrics.start() logs process start."""
        metrics = ExecutionMetrics(
            logger=self.logger,
            operation="xml_generation",
            message_type="pain.001.001.03",
        )
        metrics.start()

        self.assertIsNotNone(metrics.start_time)

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.PROCESS_START)
        self.assertEqual(entry["operation"], "xml_generation")
        self.assertEqual(entry[Fields.MESSAGE_TYPE], "pain.001.001.03")

    def test_execution_metrics_track_phase(self) -> None:
        """Test ExecutionMetrics.track_phase() records timing."""
        metrics = ExecutionMetrics(logger=self.logger, operation="test_op")
        metrics.track_phase("data_load", 120)
        metrics.track_phase("xml_generation", 350)

        self.assertEqual(metrics.phase_timings["data_load"], 120)
        self.assertEqual(metrics.phase_timings["xml_generation"], 350)

    def test_execution_metrics_track_validation(self) -> None:
        """Test ExecutionMetrics.track_validation() records results."""
        metrics = ExecutionMetrics(logger=self.logger, operation="test_op")
        metrics.track_validation("schema", "PASSED")
        metrics.track_validation("business_rules", "PASSED")

        self.assertEqual(metrics.validation_results["schema"], "PASSED")
        self.assertEqual(
            metrics.validation_results["business_rules"], "PASSED"
        )
        self.assertEqual(metrics.status, ExecutionStatus.SUCCESS)

    def test_execution_metrics_track_validation_failure(self) -> None:
        """Test ExecutionMetrics marks failure on validation failure."""
        metrics = ExecutionMetrics(logger=self.logger, operation="test_op")
        metrics.track_validation("schema", "FAILED")

        self.assertEqual(metrics.validation_results["schema"], "FAILED")
        self.assertEqual(metrics.status, ExecutionStatus.FAILED)

    def test_execution_metrics_increment_processed(self) -> None:
        """Test ExecutionMetrics.increment_processed()."""
        metrics = ExecutionMetrics(logger=self.logger, operation="test_op")
        metrics.increment_processed(10)
        metrics.increment_processed(5)

        self.assertEqual(metrics.records_processed, 15)

    def test_execution_metrics_increment_failed(self) -> None:
        """Test ExecutionMetrics.increment_failed() marks failure."""
        metrics = ExecutionMetrics(logger=self.logger, operation="test_op")
        metrics.increment_failed(2)

        self.assertEqual(metrics.records_failed, 2)
        self.assertEqual(metrics.status, ExecutionStatus.FAILED)

    def test_execution_metrics_set_error(self) -> None:
        """Test ExecutionMetrics.set_error()."""
        metrics = ExecutionMetrics(logger=self.logger, operation="test_op")
        metrics.set_error("Database connection failed")

        self.assertEqual(metrics.error_message, "Database connection failed")
        self.assertEqual(metrics.status, ExecutionStatus.FAILED)

    def test_execution_metrics_log_telemetry_success(self) -> None:
        """Test ExecutionMetrics.log_telemetry() for successful operation."""
        import time

        metrics = ExecutionMetrics(
            logger=self.logger,
            operation="xml_generation",
            message_type="pain.001.001.03",
        )
        metrics.start()
        time.sleep(0.01)  # Ensure non-zero duration
        metrics.track_phase("data_load", 120)
        metrics.track_phase("xml_generation", 350)
        metrics.track_validation("schema", "PASSED")
        metrics.increment_processed(1000)
        metrics.log_telemetry()

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.EXECUTION_SUMMARY)
        self.assertEqual(entry[Fields.LEVEL], "INFO")
        self.assertIn("telemetry", entry)

        telemetry = entry["telemetry"]
        self.assertEqual(telemetry["operation"], "xml_generation")
        self.assertEqual(telemetry["status"], ExecutionStatus.SUCCESS)
        self.assertEqual(telemetry["records_processed"], 1000)
        self.assertEqual(telemetry["records_failed"], 0)
        self.assertIn("duration_ms", telemetry)
        self.assertGreaterEqual(telemetry["duration_ms"], 0)

        # Check phase timings
        self.assertIn("phase_timings", telemetry)
        self.assertEqual(telemetry["phase_timings"]["data_load"], 120)
        self.assertEqual(telemetry["phase_timings"]["xml_generation"], 350)

        # Check validation results
        self.assertIn("validation_results", telemetry)
        self.assertEqual(telemetry["validation_results"]["schema"], "PASSED")

    def test_execution_metrics_log_telemetry_failure(self) -> None:
        """Test ExecutionMetrics.log_telemetry() for failed operation."""
        metrics = ExecutionMetrics(
            logger=self.logger,
            operation="xml_generation",
        )
        metrics.start()
        metrics.increment_processed(500)
        metrics.increment_failed(10)
        metrics.set_error("XSD validation failed")
        metrics.log_telemetry()

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.LEVEL], "ERROR")
        self.assertIn("telemetry", entry)

        telemetry = entry["telemetry"]
        self.assertEqual(telemetry["status"], ExecutionStatus.FAILED)
        self.assertEqual(telemetry["records_processed"], 500)
        self.assertEqual(telemetry["records_failed"], 10)
        self.assertEqual(telemetry["error_message"], "XSD validation failed")

    def test_execution_metrics_request_id_context(self) -> None:
        """Test ExecutionMetrics sets request_id in context."""
        custom_request_id = "req-custom123"
        metrics = ExecutionMetrics(
            logger=self.logger,
            operation="test_op",
            request_id=custom_request_id,
        )

        # Request ID should be set in context
        from pain001.logging_schema import get_request_id

        self.assertEqual(get_request_id(), custom_request_id)
        self.assertEqual(metrics.request_id, custom_request_id)


class TestJSONLoggingIntegration(unittest.TestCase):
    """Integration tests for JSON logging with real log output."""

    def test_end_to_end_json_logging(self) -> None:
        """Test end-to-end JSON logging workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "integration_test.log")

            # Configure JSON logging
            logger = configure_json_logging(
                log_file=log_file, level=logging.INFO, console_output=False
            )

            # Set a known request ID for testing
            set_request_id("req-integration")

            # Simulate a full workflow
            log_event(
                logger,
                logging.INFO,
                Events.PROCESS_START,
                message_type="pain.001.001.03",
                data_source_type="csv",
            )

            log_event(
                logger,
                logging.INFO,
                Events.DATA_LOAD_SUCCESS,
                record_count=1000,
                duration_ms=120,
            )

            log_event(
                logger,
                logging.INFO,
                Events.XML_GENERATE_SUCCESS,
                record_count=1000,
                duration_ms=350,
            )

            # Read log file and verify JSON format
            with open(log_file, encoding="utf-8") as f:
                lines = f.readlines()

            self.assertEqual(len(lines), 3)

            # Verify each line is valid JSON
            for line in lines:
                entry = json.loads(line)
                self.assertIn(Fields.TIMESTAMP, entry)
                self.assertIn(Fields.LEVEL, entry)
                self.assertIn(Fields.EVENT, entry)
                self.assertEqual(entry[Fields.REQUEST_ID], "req-integration")

            # Verify first entry
            first_entry = json.loads(lines[0])
            self.assertEqual(first_entry[Fields.EVENT], Events.PROCESS_START)
            self.assertEqual(
                first_entry[Fields.MESSAGE_TYPE], "pain.001.001.03"
            )

    def test_json_logging_with_metrics(self) -> None:
        """Test JSON logging with ExecutionMetrics tracking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "metrics_test.log")

            logger = configure_json_logging(
                log_file=log_file, level=logging.INFO, console_output=False
            )

            metrics = ExecutionMetrics(
                logger=logger,
                operation="xml_generation",
                message_type="pain.001.001.03",
            )
            metrics.start()
            metrics.track_phase("data_load", 120)
            metrics.track_phase("xml_generation", 350)
            metrics.track_validation("schema", "PASSED")
            metrics.increment_processed(1000)
            metrics.log_telemetry()

            # Read and verify log file
            with open(log_file, encoding="utf-8") as f:
                lines = f.readlines()

            # Should have 2 entries: process_start + execution_summary
            self.assertEqual(len(lines), 2)

            # Verify telemetry entry
            telemetry_entry = json.loads(lines[1])
            self.assertEqual(
                telemetry_entry[Fields.EVENT], Events.EXECUTION_SUMMARY
            )
            self.assertIn("telemetry", telemetry_entry)
            self.assertEqual(
                telemetry_entry["telemetry"]["operation"], "xml_generation"
            )


if __name__ == "__main__":
    unittest.main()
