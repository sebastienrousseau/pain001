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

# pylint: disable=redefined-outer-name
# ^ Pytest fixtures intentionally redefine names - this is standard practice

"""Tests for pain001.validation.service module."""

from pathlib import Path

import pytest

from pain001.exceptions import ConfigurationError
from pain001.validation import (
    ValidationConfig,
    ValidationReport,
    ValidationResult,
    ValidationService,
)


@pytest.fixture
def validation_service():
    """Fixture providing a ValidationService instance."""
    return ValidationService()


@pytest.fixture
def temp_files(tmp_path):
    """Fixture providing temporary test files."""
    # Create temporary files for testing
    template_file = tmp_path / "template.xml"
    template_file.write_text(
        '<?xml version="1.0"?><Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"></Document>'
    )

    schema_file = tmp_path / "schema.xsd"
    schema_file.write_text(
        '<?xml version="1.0"?><xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"></xs:schema>'
    )

    data_file = tmp_path / "data.csv"
    data_file.write_text("id,date,nb_of_txs\n001,2026-01-14,1\n")

    return {
        "template": str(template_file),
        "schema": str(schema_file),
        "data": str(data_file),
    }


def test_validation_result_creation():
    """Test ValidationResult creation with attributes."""
    result = ValidationResult(
        is_valid=False,
        error="Test error",
        field="test_field",
        details="Test details",
    )
    assert not result.is_valid
    assert result.error == "Test error"
    assert result.field == "test_field"
    assert result.details == "Test details"


def test_validation_result_success():
    """Test ValidationResult for successful validation."""
    result = ValidationResult(is_valid=True)
    assert result.is_valid
    assert result.error is None
    assert result.field is None


def test_validation_config_creation():
    """Test ValidationConfig creation."""
    config = ValidationConfig(
        xml_message_type="pain.001.001.03",
        xml_template_file_path="template.xml",
        xsd_schema_file_path="schema.xsd",
        data_file_path="data.csv",
        pre_validate=True,
    )
    assert config.xml_message_type == "pain.001.001.03"
    assert config.xml_template_file_path == "template.xml"
    assert config.pre_validate is True


def test_validation_config_default_pre_validate():
    """Test ValidationConfig default pre_validate value."""
    config = ValidationConfig(
        xml_message_type="pain.001.001.03",
        xml_template_file_path="template.xml",
        xsd_schema_file_path="schema.xsd",
        data_file_path="data.csv",
    )
    assert config.pre_validate is True


def test_validation_report_creation():
    """Test ValidationReport creation."""
    report = ValidationReport(is_valid=True)
    assert report.is_valid
    assert not report.errors
    assert not report.results


def test_validation_report_with_errors():
    """Test ValidationReport with errors."""
    report = ValidationReport(is_valid=False, errors=["Error 1", "Error 2"])
    assert not report.is_valid
    assert len(report.errors) == 2
    assert "Error 1" in report.errors


def test_validate_message_type_valid(validation_service):
    """Test message type validation with valid type."""
    result = validation_service.validate_message_type("pain.001.001.03")
    assert result.is_valid
    assert result.error is None


def test_validate_message_type_invalid(validation_service):
    """Test message type validation with invalid type."""
    result = validation_service.validate_message_type("pain.999.999.99")
    assert not result.is_valid
    assert "Invalid XML message type" in result.error
    assert result.field == "xml_message_type"
    assert "Supported types:" in result.details


def test_validate_message_type_empty(validation_service):
    """Test message type validation with empty type."""
    result = validation_service.validate_message_type("")
    assert not result.is_valid
    assert "required" in result.error.lower()


def test_validate_message_type_none(validation_service):
    """Test message type validation with None."""
    result = validation_service.validate_message_type(None)
    assert not result.is_valid


def test_validate_template_valid(validation_service, temp_files):
    """Test template validation with valid file."""
    result = validation_service.validate_template(temp_files["template"])
    assert result.is_valid


def test_validate_template_not_found(validation_service):
    """Test template validation with non-existent file."""
    result = validation_service.validate_template("/nonexistent/template.xml")
    assert not result.is_valid
    assert "does not exist" in result.error
    assert result.field == "xml_template_file_path"


def test_validate_template_empty(validation_service):
    """Test template validation with empty path."""
    result = validation_service.validate_template("")
    assert not result.is_valid
    assert "required" in result.error.lower()


def test_validate_template_path_object(validation_service, temp_files):
    """Test template validation with Path object."""
    result = validation_service.validate_template(Path(temp_files["template"]))
    assert result.is_valid


def test_validate_schema_valid(validation_service, temp_files):
    """Test schema validation with valid file."""
    result = validation_service.validate_schema(temp_files["schema"])
    assert result.is_valid


def test_validate_schema_not_found(validation_service):
    """Test schema validation with non-existent file."""
    result = validation_service.validate_schema("/nonexistent/schema.xsd")
    assert not result.is_valid
    assert "does not exist" in result.error
    assert result.field == "xsd_schema_file_path"


def test_validate_schema_empty(validation_service):
    """Test schema validation with empty path."""
    result = validation_service.validate_schema("")
    assert not result.is_valid


def test_validate_data_source_valid(validation_service, temp_files):
    """Test data source validation with valid file."""
    result = validation_service.validate_data_source(temp_files["data"])
    assert result.is_valid


def test_validate_data_source_not_found(validation_service):
    """Test data source validation with non-existent file."""
    result = validation_service.validate_data_source("/nonexistent/data.csv")
    assert not result.is_valid
    assert "does not exist" in result.error
    assert result.field == "data_file_path"


def test_validate_data_source_empty(validation_service):
    """Test data source validation with empty path."""
    result = validation_service.validate_data_source("")
    assert not result.is_valid


def test_validate_all_valid_config(validation_service, temp_files):
    """Test comprehensive validation with valid config."""
    config = ValidationConfig(
        xml_message_type="pain.001.001.03",
        xml_template_file_path=temp_files["template"],
        xsd_schema_file_path=temp_files["schema"],
        data_file_path=temp_files["data"],
    )

    # Note: This may fail template_schema_compatibility check since
    # we're using minimal test files, but it should validate file existence
    report = validation_service.validate_all(config)

    # Check that all basic validations passed
    assert report.results["message_type"].is_valid
    assert report.results["template"].is_valid
    assert report.results["schema"].is_valid
    assert report.results["data_source"].is_valid


def test_validate_all_invalid_message_type(validation_service, temp_files):
    """Test comprehensive validation with invalid message type."""
    config = ValidationConfig(
        xml_message_type="invalid.type",
        xml_template_file_path=temp_files["template"],
        xsd_schema_file_path=temp_files["schema"],
        data_file_path=temp_files["data"],
    )

    report = validation_service.validate_all(config)

    assert not report.is_valid
    assert not report.results["message_type"].is_valid
    assert any("Invalid XML message type" in error for error in report.errors)


def test_validate_all_missing_files(validation_service):
    """Test comprehensive validation with missing files."""
    config = ValidationConfig(
        xml_message_type="pain.001.001.03",
        xml_template_file_path="/nonexistent/template.xml",
        xsd_schema_file_path="/nonexistent/schema.xsd",
        data_file_path="/nonexistent/data.csv",
    )

    report = validation_service.validate_all(config)

    assert not report.is_valid
    assert not report.results["template"].is_valid
    assert not report.results["schema"].is_valid
    assert not report.results["data_source"].is_valid
    assert len(report.errors) >= 3


def test_validate_all_none_config(validation_service):
    """Test comprehensive validation with None config."""
    with pytest.raises(ConfigurationError):
        validation_service.validate_all(None)


def test_validation_report_aggregates_errors(validation_service):
    """Test that ValidationReport properly aggregates errors."""
    config = ValidationConfig(
        xml_message_type="invalid",
        xml_template_file_path="/missing/template.xml",
        xsd_schema_file_path="/missing/schema.xsd",
        data_file_path="/missing/data.csv",
    )

    report = validation_service.validate_all(config)

    assert not report.is_valid
    # Should have at least 4 errors (message type + 3 missing files)
    assert len(report.errors) >= 4


def test_validation_service_multiple_invocations(
    validation_service, temp_files
):
    """Test that ValidationService can be used multiple times."""
    # First invocation
    result1 = validation_service.validate_template(temp_files["template"])
    assert result1.is_valid

    # Second invocation
    result2 = validation_service.validate_schema(temp_files["schema"])
    assert result2.is_valid

    # Third invocation
    result3 = validation_service.validate_data_source(temp_files["data"])
    assert result3.is_valid


def test_validation_result_can_be_used_in_conditional(validation_service):
    """Test that ValidationResult works properly in conditionals."""
    valid_result = validation_service.validate_message_type("pain.001.001.03")
    if valid_result.is_valid:
        assert True  # Expected path
    else:
        pytest.fail("Valid result should be truthy")

    invalid_result = validation_service.validate_message_type("invalid")
    if not invalid_result.is_valid:
        assert True  # Expected path
    else:
        pytest.fail("Invalid result should be falsy")


def test_validate_data_content_file_not_found(validation_service, tmp_path):
    """Test validate_data_content with non-existent file."""
    nonexistent = tmp_path / "nonexistent.csv"
    result = validation_service.validate_data_content(str(nonexistent))
    assert not result.is_valid
    assert (
        "Data validation failed" in result.error
        or "Data source error" in result.error
    )


def test_validate_data_content_invalid_csv(validation_service, tmp_path):
    """Test validate_data_content with malformed CSV data."""
    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text("not,a,valid,csv\nfor,pain,data")

    result = validation_service.validate_data_content(str(csv_file))
    # This will fail during data loading
    assert not result.is_valid
