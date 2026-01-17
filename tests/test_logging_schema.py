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

"""Tests for structured logging schema."""

import json
import logging
import re
import time
import unittest
from io import StringIO
from typing import Any

from pain001.logging_schema import (
    Events,
    ExecutionSummaryTracker,
    Fields,
    _redact_pii_from_dict,
    generate_request_id,
    get_request_id,
    log_data_load_event,
    log_event,
    log_process_error,
    log_process_start,
    log_process_success,
    log_validation_event,
    log_xml_generation_event,
    mask_sensitive_data,
    set_request_id,
)


class TestLoggingSchema(unittest.TestCase):  # pylint: disable=R0904
    """Test structured logging schema functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.logger = logging.getLogger("test_logger")
        self.logger.setLevel(logging.DEBUG)
        # Remove any existing handlers
        self.logger.handlers = []
        # Add StringIO handler to capture log output
        self.log_stream = StringIO()
        handler = logging.StreamHandler(self.log_stream)
        handler.setLevel(logging.DEBUG)
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

    def test_events_constants(self) -> None:
        """Test that Events class has expected constants."""
        self.assertEqual(Events.PROCESS_START, "process_start")
        self.assertEqual(Events.PROCESS_SUCCESS, "process_success")
        self.assertEqual(Events.PROCESS_ERROR, "process_error")
        self.assertEqual(Events.CLI_ARGS_PARSED, "cli_args_parsed")
        self.assertEqual(Events.CLI_DRY_RUN, "cli_dry_run")
        self.assertEqual(Events.VALIDATION_START, "validation_start")
        self.assertEqual(Events.VALIDATION_SUCCESS, "validation_success")
        self.assertEqual(Events.VALIDATION_ERROR, "validation_error")
        self.assertEqual(Events.DATA_LOAD_START, "data_load_start")
        self.assertEqual(Events.DATA_LOAD_SUCCESS, "data_load_success")
        self.assertEqual(Events.DATA_LOAD_ERROR, "data_load_error")
        self.assertEqual(Events.XML_GENERATE_START, "xml_generate_start")
        self.assertEqual(Events.XML_GENERATE_SUCCESS, "xml_generate_success")
        self.assertEqual(Events.XML_GENERATE_ERROR, "xml_generate_error")
        self.assertEqual(Events.XSD_VALIDATION_START, "xsd_validation_start")
        self.assertEqual(
            Events.XSD_VALIDATION_SUCCESS, "xsd_validation_success"
        )
        self.assertEqual(Events.XSD_VALIDATION_ERROR, "xsd_validation_error")
        self.assertEqual(Events.NAMESPACE_REGISTER, "namespace_register")

    def test_fields_constants(self) -> None:
        """Test that Fields class has expected constants."""
        self.assertEqual(Fields.EVENT, "event")
        self.assertEqual(Fields.TIMESTAMP, "timestamp")
        self.assertEqual(Fields.LEVEL, "level")
        self.assertEqual(Fields.COMPONENT, "component")
        self.assertEqual(Fields.MODULE, "module")
        self.assertEqual(Fields.FUNCTION, "function")
        self.assertEqual(Fields.MESSAGE_TYPE, "message_type")
        self.assertEqual(Fields.ISO_VERSION, "iso_version")
        self.assertEqual(Fields.TEMPLATE_PATH, "template_path")
        self.assertEqual(Fields.SCHEMA_PATH, "schema_path")
        self.assertEqual(Fields.DATA_SOURCE_TYPE, "data_source_type")
        self.assertEqual(Fields.RECORD_COUNT, "record_count")
        self.assertEqual(Fields.TRANSACTION_COUNT, "transaction_count")
        self.assertEqual(Fields.DURATION_MS, "duration_ms")
        self.assertEqual(Fields.SIZE_BYTES, "size_bytes")
        self.assertEqual(Fields.ERROR_TYPE, "error_type")
        self.assertEqual(Fields.ERROR_MESSAGE, "error_message")
        self.assertEqual(Fields.ERROR_FIELD, "error_field")
        self.assertEqual(Fields.ERROR_INVALID_VALUE, "error_invalid_value")
        self.assertEqual(Fields.ERROR_REASON, "error_reason")
        self.assertEqual(Fields.VALIDATION_TYPE, "validation_type")
        self.assertEqual(Fields.REQUEST_ID, "request_id")
        self.assertEqual(Fields.LOGGER_NAME, "logger")
        self.assertEqual(Fields.VERSION, "version")

    def test_mask_sensitive_data(self) -> None:
        """Test sensitive data masking."""
        # Test IBAN masking
        iban = "GB29NWBK60161331926819"
        masked = mask_sensitive_data(iban, 4)
        self.assertEqual(masked, "GB29**************6819")

        # Test short string
        short = "ABC"
        masked_short = mask_sensitive_data(short, 4)
        self.assertEqual(masked_short, "****")

        # Test exact boundary (8 chars with 4 visible each side)
        boundary = "12345678"
        masked_boundary = mask_sensitive_data(boundary, 4)
        self.assertEqual(masked_boundary, "****")

        # Test 9 chars (just above boundary)
        nine = "123456789"
        masked_nine = mask_sensitive_data(nine, 4)
        self.assertEqual(masked_nine, "1234*6789")

    def test_log_event(self) -> None:
        """Test basic event logging."""
        log_event(
            self.logger,
            logging.INFO,
            Events.PROCESS_START,
            message_type="pain.001.001.03",
            record_count=10,
        )

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.PROCESS_START)
        self.assertEqual(entry["message_type"], "pain.001.001.03")
        self.assertEqual(entry["record_count"], 10)
        self.assertIn(Fields.TIMESTAMP, entry)

    def test_log_process_start(self) -> None:
        """Test process start logging."""
        start_time = log_process_start(
            self.logger,
            "pain.001.001.03",
            "csv",
            extra_field="extra_value",
        )

        self.assertIsInstance(start_time, float)
        self.assertGreater(start_time, 0)

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.PROCESS_START)
        self.assertEqual(entry["message_type"], "pain.001.001.03")
        self.assertEqual(entry["data_source_type"], "csv")
        self.assertEqual(entry["extra_field"], "extra_value")

    def test_log_process_success(self) -> None:
        """Test process success logging."""
        start_time = time.time()
        time.sleep(0.01)  # Small delay to ensure measurable duration

        log_process_success(
            self.logger,
            start_time,
            "pain.001.001.03",
            100,
            output_file="test.xml",
        )

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.PROCESS_SUCCESS)
        self.assertEqual(entry["message_type"], "pain.001.001.03")
        self.assertEqual(entry["record_count"], 100)
        self.assertIn(Fields.DURATION_MS, entry)
        self.assertGreater(entry[Fields.DURATION_MS], 0)
        self.assertEqual(entry["output_file"], "test.xml")

    def test_log_process_error(self) -> None:
        """Test process error logging."""
        error = ValueError("Test error message")

        log_process_error(
            self.logger,
            error,
            "pain.001.001.03",
            extra_context="additional info",
        )

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.PROCESS_ERROR)
        self.assertEqual(entry[Fields.ERROR_TYPE], "ValueError")
        self.assertEqual(entry[Fields.ERROR_MESSAGE], "Test error message")
        self.assertEqual(entry["message_type"], "pain.001.001.03")
        self.assertEqual(entry["extra_context"], "additional info")

    def test_log_validation_event_success(self) -> None:
        """Test validation success logging."""
        log_validation_event(
            self.logger,
            "schema",
            True,
            message_type="pain.001.001.03",
        )

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.VALIDATION_SUCCESS)
        self.assertEqual(entry[Fields.VALIDATION_TYPE], "schema")
        self.assertEqual(entry["message_type"], "pain.001.001.03")

    def test_log_validation_event_error(self) -> None:
        """Test validation error logging."""
        error = ValueError("Invalid data")

        log_validation_event(
            self.logger,
            "data",
            False,
            error,
            message_type="pain.001.001.03",
        )

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.VALIDATION_ERROR)
        self.assertEqual(entry[Fields.VALIDATION_TYPE], "data")
        self.assertEqual(entry[Fields.ERROR_TYPE], "ValueError")
        self.assertEqual(entry[Fields.ERROR_MESSAGE], "Invalid data")
        self.assertEqual(entry["message_type"], "pain.001.001.03")

    def test_log_validation_event_error_without_exception(self) -> None:
        """Test validation error logging without exception object."""
        log_validation_event(
            self.logger,
            "business_rules",
            False,
            None,
            message_type="pain.001.001.03",
        )

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.VALIDATION_ERROR)
        self.assertEqual(entry[Fields.VALIDATION_TYPE], "business_rules")
        self.assertEqual(entry[Fields.ERROR_TYPE], "Unknown")
        self.assertEqual(entry[Fields.ERROR_MESSAGE], "Validation failed")

    def test_log_data_load_event_success(self) -> None:
        """Test data load success logging."""
        log_data_load_event(
            self.logger,
            "csv",
            True,
            record_count=50,
            duration_ms=125,
        )

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.DATA_LOAD_SUCCESS)
        self.assertEqual(entry[Fields.DATA_SOURCE_TYPE], "csv")
        self.assertEqual(entry[Fields.RECORD_COUNT], 50)
        self.assertEqual(entry[Fields.DURATION_MS], 125)

    def test_log_data_load_event_error(self) -> None:
        """Test data load error logging."""
        error = FileNotFoundError("File not found")

        log_data_load_event(
            self.logger,
            "sqlite",
            False,
            error=error,
        )

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.DATA_LOAD_ERROR)
        self.assertEqual(entry[Fields.DATA_SOURCE_TYPE], "sqlite")
        self.assertEqual(entry[Fields.ERROR_TYPE], "FileNotFoundError")
        self.assertEqual(entry[Fields.ERROR_MESSAGE], "File not found")

    def test_log_xml_generation_event_success(self) -> None:
        """Test XML generation success logging."""
        log_xml_generation_event(
            self.logger,
            "pain.001.001.03",
            True,
            record_count=25,
            duration_ms=450,
        )

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.XML_GENERATE_SUCCESS)
        self.assertEqual(entry["message_type"], "pain.001.001.03")
        self.assertEqual(entry[Fields.RECORD_COUNT], 25)
        self.assertEqual(entry[Fields.DURATION_MS], 450)

    def test_log_xml_generation_event_error(self) -> None:
        """Test XML generation error logging."""
        error = RuntimeError("Template error")

        log_xml_generation_event(
            self.logger,
            "pain.001.001.03",
            False,
            error=error,
        )

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.XML_GENERATE_ERROR)
        self.assertEqual(entry["message_type"], "pain.001.001.03")
        self.assertEqual(entry[Fields.ERROR_TYPE], "RuntimeError")
        self.assertEqual(entry[Fields.ERROR_MESSAGE], "Template error")

    def test_json_serialization(self) -> None:
        """Test that all log entries are valid JSON."""
        # Log multiple events
        log_process_start(self.logger, "pain.001.001.03", "csv")
        log_validation_event(self.logger, "schema", True)
        log_process_error(self.logger, ValueError("test"))

        # Verify each line is valid JSON
        log_output = self.log_stream.getvalue()
        lines = log_output.strip().split("\n")

        for line in lines:
            try:
                json.loads(line)
            except json.JSONDecodeError:
                self.fail(f"Invalid JSON: {line}")

    def test_timestamp_format(self) -> None:
        """Test that timestamps are ISO 8601 formatted."""
        log_event(self.logger, logging.INFO, Events.PROCESS_START)

        entry = self._get_last_log_entry()
        timestamp = entry[Fields.TIMESTAMP]

        # Verify ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
        self.assertIsInstance(timestamp, str)
        iso8601_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
        self.assertIsNotNone(
            re.match(iso8601_pattern, timestamp),
            f"Timestamp '{timestamp}' does not match ISO 8601 format",
        )

    def test_multiple_extra_fields(self) -> None:
        """Test logging with multiple extra fields."""
        log_event(
            self.logger,
            logging.INFO,
            Events.PROCESS_START,
            field1="value1",
            field2=123,
            field3=True,
            field4={"nested": "dict"},
        )

        entry = self._get_last_log_entry()
        self.assertEqual(entry["field1"], "value1")
        self.assertEqual(entry["field2"], 123)
        self.assertEqual(entry["field3"], True)
        self.assertEqual(entry["field4"], {"nested": "dict"})

    def test_pii_redaction_iban(self) -> None:
        """Test that IBANs are properly redacted in logs."""
        data = {
            "debtor_iban": "GB29NWBK60161331926819",  # 22 chars
            "creditor_iban": "DE89370400440532013000",  # 22 chars
            "other_field": "not_sensitive",
        }
        redacted = _redact_pii_from_dict(data)

        # IBANs show first 4 and last 4 characters, middle chars masked
        # GB29NWBK60161331926819 -> GB29 (14 *) 6819
        self.assertEqual(redacted["debtor_iban"], "GB29**************6819")
        self.assertEqual(redacted["creditor_iban"], "DE89**************3000")
        self.assertEqual(redacted["other_field"], "not_sensitive")

    def test_pii_redaction_bic(self) -> None:
        """Test that BICs are properly redacted in logs."""
        data = {
            "debtor_bic": "NWBKGB2L",  # 8 chars
            "creditor_bic": "COBADEFF",  # 8 chars
            "another_bic": "CHASUS33XXX",  # 11 chars
        }
        redacted = _redact_pii_from_dict(data)

        # BICs show first 4 and last 2 characters only
        self.assertEqual(redacted["debtor_bic"], "NWBK**2L")
        self.assertEqual(redacted["creditor_bic"], "COBA**FF")
        # 11 char BIC: CHAS + ** + XX (fixed 2-star separator)
        self.assertEqual(redacted["another_bic"], "CHAS**XX")

    def test_pii_redaction_names(self) -> None:
        """Test that names are properly redacted in logs."""
        data = {
            "debtor_name": "John Smith Ltd",
            "creditor_name": "Acme Corporation",
            # Note: 'debtor' and 'cdtr' don't contain 'name' so won't be redacted
            "debtor": "Jane Doe",
            "cdtr": "Bob Johnson",
        }
        redacted = _redact_pii_from_dict(data)

        # Only fields containing 'name' are redacted
        self.assertEqual(redacted["debtor_name"], "[REDACTED]")
        self.assertEqual(redacted["creditor_name"], "[REDACTED]")
        # Fields without 'name' in key are NOT redacted
        self.assertEqual(redacted["debtor"], "Jane Doe")
        self.assertEqual(redacted["cdtr"], "Bob Johnson")

    def test_pii_redaction_accounts(self) -> None:
        """Test that account numbers are properly redacted in logs."""
        data = {
            "account_number": "1234567890123456",
            "account": "9876543210",
        }
        redacted = _redact_pii_from_dict(data)

        # Account numbers should show first 4 and last 4 only
        self.assertEqual(redacted["account_number"], "1234********3456")
        self.assertEqual(redacted["account"], "9876**3210")

    def test_pii_redaction_nested_structures(self) -> None:
        """Test PII redaction in nested dictionaries and lists."""
        data = {
            "transaction": {
                "debtor_iban": "GB29NWBK60161331926819",
                "creditor": {
                    "name": "Secret Corp",
                    "bic": "NWBKGB2L",
                },
            },
            "payments": [
                {"iban": "DE89370400440532013000", "amount": 100.00},
                {"iban": "FR1420041010050500013M02606", "amount": 200.00},
            ],
        }
        redacted = _redact_pii_from_dict(data)

        # Nested dict redaction
        self.assertEqual(
            redacted["transaction"]["debtor_iban"], "GB29**************6819"
        )
        self.assertEqual(
            redacted["transaction"]["creditor"]["name"], "[REDACTED]"
        )
        self.assertEqual(
            redacted["transaction"]["creditor"]["bic"], "NWBK**2L"
        )

        # List redaction (FR IBAN is 27 chars -> 4 + 19* + 4)
        self.assertEqual(
            redacted["payments"][0]["iban"], "DE89**************3000"
        )
        self.assertEqual(redacted["payments"][0]["amount"], 100.00)
        self.assertEqual(
            redacted["payments"][1]["iban"], "FR14*******************2606"
        )

    def test_pii_redaction_preserves_non_sensitive_data(self) -> None:
        """Test that non-sensitive data is preserved during redaction."""
        data = {
            "message_type": "pain.001.001.03",
            "record_count": 42,
            "timestamp": "2025-01-15T10:30:00Z",
            "success": True,
            "debtor_iban": "GB29NWBK60161331926819",
        }
        redacted = _redact_pii_from_dict(data)

        # Non-sensitive fields unchanged
        self.assertEqual(redacted["message_type"], "pain.001.001.03")
        self.assertEqual(redacted["record_count"], 42)
        self.assertEqual(redacted["timestamp"], "2025-01-15T10:30:00Z")
        self.assertEqual(redacted["success"], True)

        # Sensitive field redacted (22 chars -> 4 + 14* + 4)
        self.assertEqual(redacted["debtor_iban"], "GB29**************6819")

    def test_log_event_auto_redacts_pii(self) -> None:
        """Test that log_event automatically redacts PII before logging."""
        log_event(
            self.logger,
            logging.INFO,
            Events.DATA_LOAD_SUCCESS,
            debtor_iban="GB29NWBK60161331926819",  # 22 chars
            debtor_name="John Doe",
            record_count=10,
        )

        entry = self._get_last_log_entry()

        # PII should be automatically redacted (22 chars -> 4 + 14* + 4)
        self.assertEqual(entry["debtor_iban"], "GB29**************6819")
        self.assertEqual(entry["debtor_name"], "[REDACTED]")
        self.assertEqual(entry["record_count"], 10)

    def test_request_id_generation(self) -> None:
        """Test that request IDs are generated and consistent within context."""
        # Test generate_request_id format
        req_id = generate_request_id()
        self.assertTrue(req_id.startswith("req-"))
        self.assertEqual(len(req_id), 12)  # req- + 8 hex chars

        # Test get_request_id creates one if missing
        req_id1 = get_request_id()
        req_id2 = get_request_id()
        self.assertEqual(req_id1, req_id2)  # Should be same within context

        # Test set_request_id
        custom_id = "req-custom01"
        set_request_id(custom_id)
        self.assertEqual(get_request_id(), custom_id)

    def test_log_event_includes_request_id(self) -> None:
        """Test that all log events include request_id."""
        custom_id = "req-test1234"
        set_request_id(custom_id)

        log_event(
            self.logger,
            logging.INFO,
            Events.PROCESS_START,
            message_type="pain.001.001.03",
        )

        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.REQUEST_ID], custom_id)
        self.assertEqual(entry[Fields.LOGGER_NAME], "test_logger")
        self.assertIn(Fields.VERSION, entry)
        self.assertEqual(entry[Fields.LEVEL], "INFO")

    def test_execution_summary_tracker_context_manager(self) -> None:
        """Test ExecutionSummaryTracker as context manager."""
        with ExecutionSummaryTracker(
            self.logger, dry_run=True, message_type="pain.001.001.03"
        ) as tracker:
            tracker.increment_processed_records(1250)
            tracker.set_validation_result("schema_validation", "PASSED")
            tracker.set_validation_result("checksum_validation", "PASSED")
            tracker.increment_event_count("info")
            tracker.increment_event_count("info")
            tracker.increment_event_count("warning")

        # Check summary was logged
        entry = self._get_last_log_entry()
        self.assertEqual(entry[Fields.EVENT], Events.EXECUTION_SUMMARY)
        self.assertIn("summary", entry)

        summary = entry["summary"]
        self.assertEqual(summary["status"], "COMPLETED_WITH_WARNINGS")
        self.assertEqual(summary["execution_mode"], "dry_run")
        self.assertEqual(summary["total_records_processed"], 1250)
        self.assertEqual(summary["counts"]["info"], 2)
        self.assertEqual(summary["counts"]["warning"], 1)
        self.assertEqual(
            summary["validation_metrics"]["schema_validation"], "PASSED"
        )
        self.assertIn("performance", summary)
        self.assertIn("artifacts", summary)

    def test_execution_summary_tracker_manual_usage(self) -> None:
        """Test ExecutionSummaryTracker with manual start/stop."""
        import os
        import tempfile

        output_file = os.path.join(tempfile.gettempdir(), "output.xml")
        log_file = os.path.join(tempfile.gettempdir(), "pain001.log")

        tracker = ExecutionSummaryTracker(
            self.logger, dry_run=False, message_type="pain.001.001.09"
        )
        tracker.start()
        tracker.increment_processed_records(500)
        tracker.set_output_file(output_file)
        tracker.set_log_file(log_file)
        tracker.log_summary()

        entry = self._get_last_log_entry()
        summary = entry["summary"]
        self.assertEqual(summary["status"], "SUCCESS")
        self.assertEqual(summary["execution_mode"], "production")
        self.assertEqual(summary["total_records_processed"], 500)
        self.assertEqual(
            summary["artifacts"]["output_file"],
            output_file,
        )
        self.assertEqual(
            summary["artifacts"]["log_file"],
            log_file,
        )

    def test_execution_summary_tracker_with_errors(self) -> None:
        """Test ExecutionSummaryTracker status with errors."""
        tracker = ExecutionSummaryTracker(self.logger)
        tracker.start()
        tracker.increment_event_count("error")
        tracker.increment_event_count("error")
        tracker.log_summary()

        entry = self._get_last_log_entry()
        summary = entry["summary"]
        self.assertEqual(summary["status"], "FAILED")
        self.assertEqual(summary["counts"]["error"], 2)

    def test_execution_summary_tracker_aborted(self) -> None:
        """Test ExecutionSummaryTracker abort status."""
        tracker = ExecutionSummaryTracker(self.logger)
        tracker.start()
        tracker.abort()
        tracker.log_summary()

        entry = self._get_last_log_entry()
        summary = entry["summary"]
        self.assertEqual(summary["status"], "ABORTED")

    def test_execution_summary_tracker_exception_handling(self) -> None:
        """Test ExecutionSummaryTracker handles exceptions in context."""
        try:
            with ExecutionSummaryTracker(self.logger) as tracker:
                tracker.increment_processed_records(100)
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected

        # Summary should still be logged with ABORTED status
        entry = self._get_last_log_entry()
        summary = entry["summary"]
        self.assertEqual(summary["status"], "ABORTED")
        self.assertEqual(summary["counts"]["error"], 1)  # Auto-incremented


if __name__ == "__main__":
    unittest.main()
