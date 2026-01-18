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

"""ValidationService: Centralized validation orchestrator for Pain001.

This module decouples validation logic from the CLI, enabling validation
to be invoked programmatically from API endpoints, web hooks, and batch jobs.

Example:
    >>> from pain001.validation import ValidationService, ValidationConfig
    >>>
    >>> config = ValidationConfig(
    ...     xml_message_type="pain.001.001.03",
    ...     xml_template_file_path="template.xml",
    ...     xsd_schema_file_path="schema.xsd",
    ...     data_file_path="payments.csv"
    ... )
    >>>
    >>> service = ValidationService()
    >>> report = service.validate_all(config)
    >>>
    >>> if not report.is_valid:
    ...     for error in report.errors:
    ...         print(f"Validation error: {error}")
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from pain001.constants import valid_xml_types
from pain001.data.loader import load_payment_data
from pain001.exceptions import (
    ConfigurationError,
    DataSourceError,
    SchemaValidationError,
)
from pain001.xml.validate_via_xsd import validate_via_xsd


@dataclass
class ValidationResult:
    """Result of a single validation check.

    Attributes:
        is_valid: Whether the validation passed.
        error: Optional error message if validation failed.
        field: Optional field name that caused the validation error.
        details: Optional additional details about the validation.
    """

    is_valid: bool
    error: Optional[str] = None
    field: Optional[str] = None
    details: Optional[str] = None


@dataclass
class ValidationConfig:
    """Configuration for validation operations.

    Attributes:
        xml_message_type: ISO 20022 message type (e.g., 'pain.001.001.03').
        xml_template_file_path: Path to Jinja2 XML template file.
        xsd_schema_file_path: Path to XSD schema for validation.
        data_file_path: Path to CSV or SQLite data file.
        pre_validate: Whether to run pre-validation (IBAN/BIC checksums).
    """

    xml_message_type: str
    xml_template_file_path: str
    xsd_schema_file_path: str
    data_file_path: str
    pre_validate: bool = True


@dataclass
class ValidationReport:
    """Comprehensive validation report for all checks.

    Attributes:
        is_valid: Whether all validations passed.
        errors: List of error messages from failed validations.
        results: Dictionary of individual validation results.
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    results: dict[str, ValidationResult] = field(default_factory=dict)


class ValidationService:
    """Centralized validation orchestrator for Pain001.

    This service provides programmatic access to validation logic,
    decoupled from the CLI interface. It can be invoked from API
    endpoints, web hooks, batch jobs, or directly from Python code.

    Example:
        >>> service = ValidationService()
        >>> result = service.validate_template(Path("template.xml"))
        >>> if result.is_valid:
        ...     print("Template is valid")
        ... else:
        ...     print(f"Template error: {result.error}")
    """

    def validate_message_type(self, message_type: str) -> ValidationResult:
        """Validate that the message type is supported.

        Args:
            message_type: ISO 20022 message type (e.g., 'pain.001.001.03').

        Returns:
            ValidationResult indicating success or failure.

        Example:
            >>> service = ValidationService()
            >>> result = service.validate_message_type("pain.001.001.03")
            >>> assert result.is_valid
        """
        if not message_type:
            return ValidationResult(
                is_valid=False,
                error="XML message type is required",
                field="xml_message_type",
            )

        if message_type not in valid_xml_types:
            return ValidationResult(
                is_valid=False,
                error=f"Invalid XML message type: {message_type}",
                field="xml_message_type",
                details=f"Supported types: {', '.join(valid_xml_types)}",
            )

        return ValidationResult(is_valid=True)

    def validate_template(
        self, template_path: Union[str, Path]
    ) -> ValidationResult:
        """Validate that the XML template file exists and is accessible.

        Args:
            template_path: Path to XML template file.

        Returns:
            ValidationResult indicating success or failure.

        Example:
            >>> service = ValidationService()
            >>> result = service.validate_template("template.xml")
            >>> if not result.is_valid:
            ...     print(f"Template not found: {result.error}")
        """
        if not template_path:
            return ValidationResult(
                is_valid=False,
                error="XML template file path is required",
                field="xml_template_file_path",
            )

        template_path_str = str(template_path)
        if not os.path.isfile(template_path_str):
            return ValidationResult(
                is_valid=False,
                error=f"XML template file does not exist: {template_path_str}",
                field="xml_template_file_path",
            )

        return ValidationResult(is_valid=True)

    def validate_schema(
        self, schema_path: Union[str, Path]
    ) -> ValidationResult:
        """Validate that the XSD schema file exists and is accessible.

        Args:
            schema_path: Path to XSD schema file.

        Returns:
            ValidationResult indicating success or failure.

        Example:
            >>> service = ValidationService()
            >>> result = service.validate_schema("schema.xsd")
            >>> if not result.is_valid:
            ...     print(f"Schema not found: {result.error}")
        """
        if not schema_path:
            return ValidationResult(
                is_valid=False,
                error="XSD schema file path is required",
                field="xsd_schema_file_path",
            )

        schema_path_str = str(schema_path)
        if not os.path.isfile(schema_path_str):
            return ValidationResult(
                is_valid=False,
                error=f"XSD schema file does not exist: {schema_path_str}",
                field="xsd_schema_file_path",
            )

        return ValidationResult(is_valid=True)

    def validate_data_source(
        self, data_path: Union[str, Path]
    ) -> ValidationResult:
        """Validate that the data source file exists and is accessible.

        Args:
            data_path: Path to CSV or SQLite data file.

        Returns:
            ValidationResult indicating success or failure.

        Example:
            >>> service = ValidationService()
            >>> result = service.validate_data_source("payments.csv")
            >>> if not result.is_valid:
            ...     print(f"Data file not found: {result.error}")
        """
        if not data_path:
            return ValidationResult(
                is_valid=False,
                error="Data file path is required",
                field="data_file_path",
            )

        data_path_str = str(data_path)

        # Check if path is a directory instead of a file
        if os.path.isdir(data_path_str):
            # Extract directory name to suggest the correct file

            return ValidationResult(
                is_valid=False,
                error=(
                    f"Data file does not exist: {data_path_str}\n"
                    f"The path points to a directory. Please specify a data file:\n"
                    f"  Example: {data_path_str}/template.csv"
                ),
                field="data_file_path",
            )

        if not os.path.isfile(data_path_str):
            return ValidationResult(
                is_valid=False,
                error=f"Data file does not exist: {data_path_str}",
                field="data_file_path",
            )

        return ValidationResult(is_valid=True)

    def validate_template_schema_compatibility(
        self, template_path: Union[str, Path], schema_path: Union[str, Path]
    ) -> ValidationResult:
        """Validate that the XML template conforms to the XSD schema.

        Args:
            template_path: Path to XML template file.
            schema_path: Path to XSD schema file.

        Returns:
            ValidationResult indicating success or failure.

        Example:
            >>> service = ValidationService()
            >>> result = service.validate_template_schema_compatibility(
            ...     "template.xml", "schema.xsd"
            ... )
            >>> if not result.is_valid:
            ...     print(f"Schema validation failed: {result.error}")
        """
        try:
            validate_via_xsd(str(template_path), str(schema_path))
            return ValidationResult(is_valid=True)
        except SchemaValidationError as exc:
            return ValidationResult(
                is_valid=False,
                error=f"Schema validation failed: {exc}",
                details=str(exc),
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return ValidationResult(
                is_valid=False,
                error=f"Unexpected schema validation error: {exc}",
                details=str(exc),
            )

    def validate_data_content(
        self, data_path: Union[str, Path]
    ) -> ValidationResult:
        """Validate that the data file can be loaded and parsed.

        Args:
            data_path: Path to CSV or SQLite data file.

        Returns:
            ValidationResult indicating success or failure.

        Example:
            >>> service = ValidationService()
            >>> result = service.validate_data_content("payments.csv")
            >>> if not result.is_valid:
            ...     print(f"Data validation failed: {result.error}")
        """
        try:
            load_payment_data(str(data_path))
            return ValidationResult(is_valid=True)
        except (FileNotFoundError, ValueError) as exc:
            return ValidationResult(
                is_valid=False,
                error=f"Data validation failed: {exc}",
                field="data_file_path",
                details=str(exc),
            )
        except DataSourceError as exc:
            return ValidationResult(
                is_valid=False,
                error=f"Data source error: {exc}",
                field="data_file_path",
                details=str(exc),
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return ValidationResult(
                is_valid=False,
                error=f"Unexpected data validation error: {exc}",
                details=str(exc),
            )

    def validate_all(self, config: ValidationConfig) -> ValidationReport:
        """Run comprehensive validation pipeline.

        This method runs all validation checks and returns a consolidated
        report. It's the primary entry point for validation operations.

        Args:
            config: Validation configuration with all required paths.

        Returns:
            ValidationReport with results from all checks.

        Raises:
            ConfigurationError: If config is invalid.

        Example:
            >>> service = ValidationService()
            >>> config = ValidationConfig(
            ...     xml_message_type="pain.001.001.03",
            ...     xml_template_file_path="template.xml",
            ...     xsd_schema_file_path="schema.xsd",
            ...     data_file_path="payments.csv"
            ... )
            >>> report = service.validate_all(config)
            >>> if not report.is_valid:
            ...     for error in report.errors:
            ...         print(f"Error: {error}")
        """
        if not config:
            raise ConfigurationError("ValidationConfig is required")

        report = ValidationReport(is_valid=True)

        # Validate message type
        result = self.validate_message_type(config.xml_message_type)
        report.results["message_type"] = result
        if not result.is_valid:
            report.is_valid = False
            report.errors.append(
                result.error or "Message type validation failed"
            )

        # Validate template file
        result = self.validate_template(config.xml_template_file_path)
        report.results["template"] = result
        if not result.is_valid:
            report.is_valid = False
            report.errors.append(result.error or "Template validation failed")

        # Validate schema file
        result = self.validate_schema(config.xsd_schema_file_path)
        report.results["schema"] = result
        if not result.is_valid:
            report.is_valid = False
            report.errors.append(result.error or "Schema validation failed")

        # Validate data source file
        result = self.validate_data_source(config.data_file_path)
        report.results["data_source"] = result
        if not result.is_valid:
            report.is_valid = False
            report.errors.append(
                result.error or "Data source validation failed"
            )

        # Only proceed with content validation if files exist
        # SKIP template-schema validation here because the template contains
        # Jinja2 variables ({{date}}, {{id}}, etc.) which are not valid XML.
        # The generated XML (after rendering with data) will be validated
        # in the generate_xml_string() function instead.
        # if (
        #     report.results["template"].is_valid
        #     and report.results["schema"].is_valid
        # ):
        #     result = self.validate_template_schema_compatibility(
        #         config.xml_template_file_path, config.xsd_schema_file_path
        #     )
        #     report.results["template_schema_compatibility"] = result
        #     if not result.is_valid:
        #         report.is_valid = False
        #         report.errors.append(
        #             result.error
        #             or "Template/schema compatibility check failed"
        #         )

        if report.results["data_source"].is_valid:
            result = self.validate_data_content(config.data_file_path)
            report.results["data_content"] = result
            if not result.is_valid:
                report.is_valid = False
                report.errors.append(
                    result.error or "Data content validation failed"
                )

        return report
