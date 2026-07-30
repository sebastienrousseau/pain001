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

"""Tests for pain001.exceptions module."""

from pain001.exceptions import (
    ConfigurationError,
    DataSourceError,
    InvalidBICError,
    InvalidIBANError,
    MissingRequiredFieldError,
    Pain001Error,
    PaymentValidationError,
    SchemaValidationError,
    XMLGenerationError,
    XSDValidationError,
)


def test_pain001_error_base():
    """Test that Pain001Error is the base exception."""
    error = Pain001Error("Base error")
    assert str(error) == "Base error"
    assert isinstance(error, Exception)


def test_payment_validation_error():
    """Test PaymentValidationError with field attribute."""
    error = PaymentValidationError("Invalid IBAN", field="iban")
    assert str(error) == "Invalid IBAN"
    assert error.field == "iban"
    assert isinstance(error, Pain001Error)


def test_payment_validation_error_without_field():
    """Test PaymentValidationError without field attribute."""
    error = PaymentValidationError("Invalid data")
    assert str(error) == "Invalid data"
    assert error.field is None


def test_xml_generation_error():
    """Test XMLGenerationError."""
    error = XMLGenerationError("Template rendering failed")
    assert str(error) == "Template rendering failed"
    assert isinstance(error, Pain001Error)


def test_configuration_error():
    """Test ConfigurationError."""
    error = ConfigurationError("Invalid log level")
    assert str(error) == "Invalid log level"
    assert isinstance(error, Pain001Error)


def test_data_source_error():
    """Test DataSourceError."""
    error = DataSourceError("File not found: data.csv")
    assert str(error) == "File not found: data.csv"
    assert isinstance(error, Pain001Error)


def test_schema_validation_error():
    """Test SchemaValidationError with errors list."""
    errors = [
        "Line 10: Invalid element 'Amt'",
        "Line 15: Missing required element 'Dbtr'",
    ]
    error = SchemaValidationError("XSD validation failed", errors=errors)
    assert str(error) == "XSD validation failed"
    assert error.errors == errors
    assert isinstance(error, Pain001Error)


def test_schema_validation_error_without_errors():
    """Test SchemaValidationError without errors list."""
    error = SchemaValidationError("XSD validation failed")
    assert str(error) == "XSD validation failed"
    assert error.errors == []


def test_exception_inheritance():
    """Test that all custom exceptions inherit from Pain001Error."""
    exceptions = [
        PaymentValidationError,
        XMLGenerationError,
        ConfigurationError,
        DataSourceError,
        SchemaValidationError,
    ]
    for exc_class in exceptions:
        assert issubclass(exc_class, Pain001Error)
        assert issubclass(exc_class, Exception)


def test_exception_messages_preserved():
    """Test that exception messages are preserved through inheritance."""
    message = "Test error message with details"
    for exc_class in [
        Pain001Error,
        PaymentValidationError,
        XMLGenerationError,
        ConfigurationError,
        DataSourceError,
        SchemaValidationError,
    ]:
        error = exc_class(message)
        assert str(error) == message


def test_payment_validation_error_repr():
    """Test PaymentValidationError string representation with field."""
    error = PaymentValidationError("Invalid BIC format", field="bic")
    repr_str = repr(error)
    assert "PaymentValidationError" in repr_str
    assert "Invalid BIC format" in repr_str


def test_schema_validation_error_repr():
    """Test SchemaValidationError string representation with errors."""
    errors = ["Error 1", "Error 2"]
    error = SchemaValidationError("Validation failed", errors=errors)
    repr_str = repr(error)
    assert "SchemaValidationError" in repr_str
    assert "Validation failed" in repr_str


def test_xsd_validation_error_alias():
    """Test that XSDValidationError is an alias for SchemaValidationError."""
    assert XSDValidationError is SchemaValidationError
    error = XSDValidationError("XSD validation failed")
    assert isinstance(error, SchemaValidationError)
    assert isinstance(error, Pain001Error)


def test_invalid_iban_error():
    """Test InvalidIBANError with all attributes."""
    error = InvalidIBANError(
        message="IBAN checksum validation failed",
        iban="AT681234567890",
        field="debtor_account",
        reason="Invalid checksum (expected mod 97 = 1)",
    )
    assert str(error) == "IBAN checksum validation failed"
    assert error.iban == "AT681234567890"
    assert error.field == "debtor_account"
    assert error.reason == "Invalid checksum (expected mod 97 = 1)"
    assert isinstance(error, PaymentValidationError)
    assert isinstance(error, Pain001Error)


def test_invalid_iban_error_minimal():
    """Test InvalidIBANError with minimal attributes."""
    error = InvalidIBANError(message="Invalid IBAN format", iban="INVALID")
    assert str(error) == "Invalid IBAN format"
    assert error.iban == "INVALID"
    assert error.field is None
    assert error.reason is None


def test_invalid_bic_error():
    """Test InvalidBICError with all attributes."""
    error = InvalidBICError(
        message="BIC format validation failed",
        bic="INVALID123",
        field="debtor_agent",
        reason="BIC must be 8 or 11 characters",
    )
    assert str(error) == "BIC format validation failed"
    assert error.bic == "INVALID123"
    assert error.field == "debtor_agent"
    assert error.reason == "BIC must be 8 or 11 characters"
    assert isinstance(error, PaymentValidationError)
    assert isinstance(error, Pain001Error)


def test_invalid_bic_error_minimal():
    """Test InvalidBICError with minimal attributes."""
    error = InvalidBICError(message="Invalid BIC", bic="BAD")
    assert str(error) == "Invalid BIC"
    assert error.bic == "BAD"
    assert error.field is None
    assert error.reason is None


def test_missing_required_field_error():
    """Test MissingRequiredFieldError with all attributes."""
    required_fields = ["debtor_name", "debtor_account", "amount"]
    error = MissingRequiredFieldError(
        message="Required field 'debtor_name' is missing",
        field="debtor_name",
        row_number=5,
        required_fields=required_fields,
    )
    assert str(error) == "Required field 'debtor_name' is missing"
    assert error.field == "debtor_name"
    assert error.row_number == 5
    assert error.required_fields == required_fields
    assert isinstance(error, PaymentValidationError)
    assert isinstance(error, Pain001Error)


def test_missing_required_field_error_minimal():
    """Test MissingRequiredFieldError with minimal attributes."""
    error = MissingRequiredFieldError(message="Missing field", field="amount")
    assert str(error) == "Missing field"
    assert error.field == "amount"
    assert error.row_number is None
    assert error.required_fields == []


def test_exception_hierarchy_new_types():
    """Test that new exception types properly inherit from PaymentValidationError."""
    exceptions = [
        InvalidIBANError,
        InvalidBICError,
        MissingRequiredFieldError,
    ]
    for exc_class in exceptions:
        assert issubclass(exc_class, PaymentValidationError)
        assert issubclass(exc_class, Pain001Error)
        assert issubclass(exc_class, Exception)


def test_catch_specific_validation_errors():
    """Test that specific validation errors can be caught independently."""
    # Test catching InvalidIBANError specifically
    try:
        raise InvalidIBANError("Bad IBAN", iban="XX00")
    except InvalidIBANError as e:
        assert e.iban == "XX00"
        assert isinstance(e, PaymentValidationError)

    # Test catching InvalidBICError specifically
    try:
        raise InvalidBICError("Bad BIC", bic="BADCODE")
    except InvalidBICError as e:
        assert e.bic == "BADCODE"
        assert isinstance(e, PaymentValidationError)

    # Test catching MissingRequiredFieldError specifically
    try:
        raise MissingRequiredFieldError("Missing", field="test")
    except MissingRequiredFieldError as e:
        assert e.field == "test"
        assert isinstance(e, PaymentValidationError)


def test_catch_all_payment_validation_errors():
    """Test that all validation errors can be caught with PaymentValidationError."""
    errors_to_test = [
        InvalidIBANError("Bad IBAN", iban="XX00"),
        InvalidBICError("Bad BIC", bic="BAD"),
        MissingRequiredFieldError("Missing", field="test"),
        PaymentValidationError("Generic validation error"),
    ]

    for error in errors_to_test:
        try:
            raise error
        except PaymentValidationError as e:
            # All should be catchable as PaymentValidationError
            assert isinstance(e, PaymentValidationError)
            assert isinstance(e, Pain001Error)


def test_invalid_iban_error_repr():
    """Test InvalidIBANError string representation."""
    error = InvalidIBANError(
        "Invalid IBAN", iban="AT68", field="debtor_account"
    )
    repr_str = repr(error)
    assert "InvalidIBANError" in repr_str


def test_invalid_bic_error_repr():
    """Test InvalidBICError string representation."""
    error = InvalidBICError("Invalid BIC", bic="BAD", field="debtor_agent")
    repr_str = repr(error)
    assert "InvalidBICError" in repr_str


def test_missing_required_field_error_repr():
    """Test MissingRequiredFieldError string representation."""
    error = MissingRequiredFieldError("Missing", field="amount", row_number=10)
    repr_str = repr(error)
    assert "MissingRequiredFieldError" in repr_str
