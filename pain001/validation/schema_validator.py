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

"""JSON Schema-based validator for payment data.

This module provides schema-based validation for payment data against
ISO 20022 specifications. Schemas are externalized to JSON files to support
multiple message types and custom validation rules.

Example:
    >>> from pain001.validation.schema_validator import SchemaValidator
    >>>
    >>> validator = SchemaValidator("pain.001.001.03")
    >>> errors = validator.validate_data({
    ...     "id": "MSG001",
    ...     "date": "2024-01-15",
    ...     "nb_of_txs": 1,
    ...     # ... additional fields
    ... })
    >>> if not errors:
    ...     print("✓ Data is valid")
"""

import json
from pathlib import Path
from typing import Any

import jsonschema

from pain001.constants import valid_xml_types
from pain001.security import validate_path


class ValidationError:
    """Represents a validation error.

    Args:
        message: Human-readable error message.
        path: JSON path to the invalid field (e.g., "$.debtor_account").
        value: The invalid value.
        rule: The validation rule that failed (e.g., "pattern",
            "required").
    """

    def __init__(
        self,
        message: str,
        path: str,
        value: Any,
        rule: str,
    ):
        self.message = message
        self.path = path
        self.value = value
        self.rule = rule

    def __str__(self) -> str:
        """Return formatted error string."""
        return f"{self.path}: {self.message}"

    def __repr__(self) -> str:
        """Return repr of error."""
        return f"ValidationError(path={self.path!r}, rule={self.rule!r})"


class SchemaValidator:
    """Validates payment data against JSON Schema files.

    The loaded schema dictionary is available as ``schema`` and the
    resolved schema file location as ``schema_path``.

    Args:
        message_type: ISO 20022 message type (e.g., "pain.001.001.03").
        schema_dir: Directory containing schema files. Defaults to
            pain001/schemas/.

    Raises:
        ValueError: If the message type is not supported.
        FileNotFoundError: If the schema file is missing or escapes the
            schema directory.
        json.JSONDecodeError: If the schema file is invalid JSON.
    """

    def __init__(
        self,
        message_type: str,
        schema_dir: Path | None = None,
    ):
        if schema_dir is None:  # pragma: no cover
            schema_dir = Path(__file__).parent.parent / "schemas"

        # Validate message_type to prevent path traversal (CodeQL)
        if message_type not in valid_xml_types:
            raise ValueError(f"Invalid message type: {message_type}")

        # Validate path to prevent traversal attacks
        schema_file = schema_dir / f"{message_type}.schema.json"
        try:
            # CodeQL: validate_path returns sanitized string for taint tracking
            # Ensure schema file is within the schemas directory
            validated_schema_path = validate_path(
                schema_file, must_exist=True, base_dir=schema_dir
            )  # nosec B108
        except Exception as e:  # pragma: no cover
            raise FileNotFoundError(
                f"Schema validation failed: {e}"
            ) from e  # pragma: no cover

        # Explicit startswith guard for CodeQL CWE-22 sanitiser recognition.
        # validate_path already enforces this, but CodeQL requires the guard
        # at the call site for interprocedural taint tracking.
        schema_dir_prefix = str(Path(schema_dir).resolve())
        if not validated_schema_path.startswith(
            schema_dir_prefix
        ):  # pragma: no cover
            raise FileNotFoundError(  # pragma: no cover
                f"Schema path escapes schema directory: {schema_dir}"
            )

        self.schema_path = validated_schema_path
        try:
            with open(validated_schema_path, encoding="utf-8") as f:  # nosec B108
                self.schema = json.load(f)
        except json.JSONDecodeError as e:  # pragma: no cover
            raise json.JSONDecodeError(  # pragma: no cover
                f"Invalid JSON in schema file {self.schema_path}: {e.msg}",
                e.doc,
                e.pos,
            ) from e

    def _coerce_types_for_validation(
        self, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a copy with strings coerced to the schema's declared types.

        CSV and other text-based loaders deliver every value as a string,
        while the JSON schemas declare integer/number/boolean types. Values
        that cannot be coerced are left unchanged so jsonschema reports
        them as type errors.

        Args:
            data: Dictionary containing payment data to validate.

        Returns:
            A shallow copy of ``data`` with coercible strings converted.
        """
        properties = self.schema.get("properties", {})
        coerced = dict(data)
        for key, value in data.items():
            if not isinstance(value, str):
                continue
            expected = properties.get(key, {}).get("type")
            text = value.strip()
            try:
                if expected == "integer":
                    coerced[key] = int(text)
                elif expected == "number":
                    coerced[key] = float(text)
                elif expected == "boolean" and text.lower() in {
                    "true",
                    "false",
                }:
                    coerced[key] = text.lower() == "true"
            except ValueError:
                continue
        return coerced

    def validate_data(self, data: dict[str, Any]) -> list[ValidationError]:
        """Validate a data dictionary against the schema.

        String values are first coerced to the schema's declared types so
        text-based sources (CSV, SQLite) validate the same as typed JSON.

        Args:
            data: Dictionary containing payment data to validate.

        Returns:
            List of ValidationError objects. Empty list if valid.

        Raises:
            ValueError: If the loaded JSON schema itself is invalid.
        """
        errors: list[ValidationError] = []

        try:
            jsonschema.validate(
                instance=self._coerce_types_for_validation(data),
                schema=self.schema,
            )
        except jsonschema.ValidationError as e:
            # Format the path to JSON pointer notation
            path = (
                "$." + ".".join(str(p) for p in e.absolute_path)
                if e.absolute_path
                else "$"
            )

            error = ValidationError(
                message=e.message,
                path=path,
                value=e.instance,
                rule=str(e.validator) if e.validator else "unknown",
            )
            errors.append(error)
        except jsonschema.SchemaError as e:  # pragma: no cover
            raise ValueError(
                f"Invalid schema: {e.message}"
            ) from e  # pragma: no cover

        return errors

    def validate_row(
        self, row: dict[str, Any]
    ) -> tuple[bool, list[ValidationError]]:
        """Validate a single row of data.

        Args:
            row: Dictionary containing a single row of data.

        Returns:
            Tuple of (is_valid, errors). is_valid is True if no errors.
        """
        errors = self.validate_data(row)
        return len(errors) == 0, errors

    def get_required_fields(self) -> list[str]:
        """Extract required field names from schema.

        Returns:
            List of required field names.
        """
        required = self.schema.get("required", [])
        return list(required) if required else []

    def get_field_schema(self, field_name: str) -> dict[str, Any] | None:
        """Get the schema definition for a specific field.

        Args:
            field_name: Name of the field.

        Returns:
            Field schema dictionary, or None if field not in schema.
        """
        properties = self.schema.get("properties", {})
        field_schema = properties.get(field_name)
        return (
            dict(field_schema)
            if field_schema and isinstance(field_schema, dict)
            else None
        )

    def get_field_description(self, field_name: str) -> str | None:
        """Get the description for a specific field.

        Args:
            field_name: Name of the field.

        Returns:
            Field description, or None if not available.
        """
        field_schema = self.get_field_schema(field_name)
        if field_schema:
            return field_schema.get("description")
        return None

    def validate_batch(
        self, rows: list[dict[str, Any]]
    ) -> tuple[int, int, list[tuple[int, list[ValidationError]]]]:
        """Validate a batch of rows.

        Args:
            rows: List of dictionaries containing payment data.

        Returns:
            Tuple of (total_rows, valid_rows, errors).
            errors is a list of (row_index, error_list) tuples for invalid rows.
        """
        total_rows = len(rows)
        valid_rows = 0
        errors: list[tuple[int, list[ValidationError]]] = []

        for row_idx, row in enumerate(rows):
            row_errors = self.validate_data(row)
            if row_errors:
                errors.append((row_idx, row_errors))
            else:
                valid_rows += 1

        return total_rows, valid_rows, errors
