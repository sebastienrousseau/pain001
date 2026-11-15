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

"""ValidationService results in full: verdict, error, field and details.

API and MCP clients branch on ``field`` and show ``error`` verbatim, so
each check's failure is pinned exactly, including the difference
between a path that does not exist and one that is not a regular file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import pytest

from pain001.constants import valid_xml_types
from pain001.exceptions import ConfigurationError, PaymentValidationError
from pain001.validation import (
    ValidationConfig,
    ValidationResult,
    ValidationService,
)
from pain001.validation import service as service_module

TYPE_DIR = Path("pain001/templates/pain.001.001.03")


def _result(result: ValidationResult) -> tuple[object, ...]:
    """Flatten a result for one exact comparison."""
    return (result.is_valid, result.error, result.field, result.details)


def test_message_type_failures() -> None:
    """Empty and unknown message types name the field and the choices."""
    service = ValidationService()
    assert _result(service.validate_message_type("")) == (
        False,
        "XML message type is required",
        "xml_message_type",
        None,
    )
    assert _result(service.validate_message_type("pain.999")) == (
        False,
        "Invalid XML message type: pain.999",
        "xml_message_type",
        f"Supported types: {', '.join(valid_xml_types)}",
    )
    assert ", pain.001.001.04, " in (
        service.validate_message_type("x").details or ""
    )


@pytest.mark.parametrize(
    ("method", "label", "field"),
    [
        ("validate_template", "XML template file", "xml_template_file_path"),
        ("validate_schema", "XSD schema file", "xsd_schema_file_path"),
        ("validate_data_source", "Data file", "data_file_path"),
    ],
)
def test_file_checks_name_the_missing_path(
    tmp_path: Path, method: str, label: str, field: str
) -> None:
    """Empty, missing, and not-a-regular-file paths each say which."""
    check = getattr(ValidationService(), method)
    assert _result(check("")) == (
        False,
        f"{label} path is required",
        field,
        None,
    )
    missing = tmp_path / "missing.bin"
    assert _result(check(missing)) == (
        False,
        f"{label} does not exist or is invalid: Path does not exist: "
        f"{os.path.realpath(missing)}",
        field,
        None,
    )
    present = tmp_path / "present.bin"
    present.write_text("x", encoding="utf-8")
    assert _result(check(present)) == (True, None, None, None)


@pytest.mark.parametrize(
    ("method", "label", "field"),
    [
        ("validate_template", "XML template file", "xml_template_file_path"),
        ("validate_schema", "XSD schema file", "xsd_schema_file_path"),
    ],
)
def test_a_directory_is_not_a_template_or_schema(
    tmp_path: Path, method: str, label: str, field: str
) -> None:
    """A directory exists but is not a file, and is reported as such."""
    check = getattr(ValidationService(), method)
    assert _result(check(tmp_path)) == (
        False,
        f"{label} does not exist: {tmp_path}",
        field,
        None,
    )


def test_the_compatibility_check_renders_with_the_example_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The template is rendered with the type's example data, paths as str."""
    seen: list[tuple[object, ...]] = []

    def record(rows: object, kind: object, xml: object, xsd: object) -> str:
        seen.append((rows, kind, xml, xsd))
        return "<Document/>"

    monkeypatch.setattr(service_module, "generate_xml_string", record)
    result = ValidationService().validate_template_schema_compatibility(
        TYPE_DIR / "template.xml", TYPE_DIR / "pain.001.001.03.xsd"
    )
    assert _result(result) == (True, None, None, None)
    ((rows, kind, xml, xsd),) = seen
    assert isinstance(rows, list) and rows
    assert (kind, xml, xsd) == (
        "pain.001.001.03",
        str(TYPE_DIR / "template.xml"),
        str(TYPE_DIR / "pain.001.001.03.xsd"),
    )


@pytest.mark.parametrize(
    ("raised", "prefix"),
    [
        (RuntimeError("element out of order"), "Schema validation failed"),
        (
            ValueError("outside the allowed paths"),
            "Template could not be rendered",
        ),
        (OSError("disk exploded"), "Unexpected schema validation error"),
    ],
)
def test_a_compatibility_failure_carries_the_reason(
    monkeypatch: pytest.MonkeyPatch, raised: Exception, prefix: str
) -> None:
    """The error and the details both carry the renderer's own reason."""

    def fail(*_args: object) -> str:
        raise raised

    monkeypatch.setattr(service_module, "generate_xml_string", fail)
    result = ValidationService().validate_template_schema_compatibility(
        "t.xml", "pain.001.001.03.xsd"
    )
    assert _result(result) == (
        False,
        f"{prefix}: {raised}",
        None,
        str(raised),
    )


def _bad_iban_csv(tmp_path: Path) -> Path:
    """The bundled sample rows with the debtor IBAN's check digits broken."""
    text = (TYPE_DIR / "template.csv").read_text(encoding="utf-8")
    broken = tmp_path / "rows.csv"
    broken.write_text(
        text.replace("DE07512108001245126162", "DE00512108001245126162"),
        encoding="utf-8",
    )
    return broken


def test_data_content_checks_identifiers_by_default(tmp_path: Path) -> None:
    """A bad IBAN fails by default and passes when the checks are off."""
    service = ValidationService()
    broken = _bad_iban_csv(tmp_path)
    assert service.validate_data_content(
        broken, identifier_checks=False
    ).is_valid
    result = service.validate_data_content(broken)
    assert result.is_valid is False
    assert result.details
    assert result.details.startswith("Invalid identifiers")
    assert result.error == f"Data validation failed: {result.details}"
    assert result.field == "debtor_account_IBAN"


def test_a_payment_error_without_a_field_names_the_data_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bad data is a data failure even when no single column is to blame."""

    def reject(*_args: object) -> None:
        raise PaymentValidationError("rows disagree on the currency")

    monkeypatch.setattr(service_module, "load_payment_data", reject)
    result = ValidationService().validate_data_content("rows.csv")
    assert _result(result) == (
        False,
        "Data validation failed: rows disagree on the currency",
        "data_file_path",
        "rows disagree on the currency",
    )


def test_a_missing_data_file_fails_on_the_data_column(tmp_path: Path) -> None:
    """A path that does not exist is a data validation failure."""
    result = ValidationService().validate_data_content(tmp_path / "no.csv")
    assert result.is_valid is False
    assert result.field == "data_file_path"
    assert result.details and "Path does not exist" in result.details
    assert result.error == f"Data validation failed: {result.details}"


def test_data_content_reports_a_data_source_error_in_full(
    tmp_path: Path,
) -> None:
    """An empty JSONL file is a data source error on the data column."""
    empty = tmp_path / "rows.jsonl"
    empty.write_text("\n", encoding="utf-8")
    result = ValidationService().validate_data_content(empty)
    assert result.is_valid is False
    assert result.field == "data_file_path"
    assert result.details
    assert result.error == f"Data source error: {result.details}"


class _SilentFailures(ValidationService):
    """A service whose checks fail without an error message.

    The data source check passes only when ``source_ok`` is set, so the
    content check can be reached or skipped.
    """

    def __init__(self, source_ok: bool) -> None:
        self.source_ok = source_ok

    def validate_message_type(self, message_type: str) -> ValidationResult:
        """Fail silently."""
        return ValidationResult(is_valid=False)

    def validate_template(self, template_path: str | Path) -> ValidationResult:
        """Fail silently."""
        return ValidationResult(is_valid=False)

    def validate_schema(self, schema_path: str | Path) -> ValidationResult:
        """Fail silently."""
        return ValidationResult(is_valid=False)

    def validate_data_source(self, data_path: str | Path) -> ValidationResult:
        """Pass only when the content check should run."""
        return ValidationResult(is_valid=self.source_ok)

    def validate_data_content(
        self,
        data_path: str | Path,
        identifier_checks: bool = True,
        message_type: str | None = None,
    ) -> ValidationResult:
        """Fail silently."""
        return ValidationResult(is_valid=False)


def test_validate_all_names_each_silently_failed_check() -> None:
    """A failed check without its own message gets the step's fallback."""
    config = ValidationConfig("pain.001.001.03", "t.xml", "s.xsd", "d.csv")
    report = _SilentFailures(source_ok=True).validate_all(config)
    assert report.is_valid is False
    assert report.errors == [
        "Message type validation failed",
        "Template validation failed",
        "Schema validation failed",
        "Data content validation failed",
    ]
    report = _SilentFailures(source_ok=False).validate_all(config)
    assert report.errors[-1] == "Data source validation failed"
    assert "data_content" not in report.results


def test_validate_all_without_a_config_says_so() -> None:
    """A missing config is a ConfigurationError with a plain message."""
    with pytest.raises(ConfigurationError) as caught:
        ValidationService().validate_all(cast(ValidationConfig, None))
    assert str(caught.value) == "ValidationConfig is required"


def test_a_directory_is_not_a_data_file(tmp_path: Path) -> None:
    """A directory as the data file suggests a file inside it."""
    assert _result(ValidationService().validate_data_source(tmp_path)) == (
        False,
        f"Data file does not exist: {tmp_path}\n"
        "The path points to a directory. Please specify a data file:\n"
        f"  Example: {tmp_path}/template.csv",
        "data_file_path",
        None,
    )


def test_a_special_file_is_not_a_data_file(tmp_path: Path) -> None:
    """A path that exists but is neither a file nor a directory is refused."""
    fifo = tmp_path / "rows.fifo"
    os.mkfifo(fifo)
    try:
        result = ValidationService().validate_data_source(fifo)
    finally:
        # The temp tree lives inside the package; a leftover pipe would
        # break tools that copy it (mutmut's working copy).
        fifo.unlink()
    assert _result(result) == (
        False,
        f"Data file does not exist: {fifo}",
        "data_file_path",
        None,
    )


def test_a_crash_while_loading_is_an_unexpected_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anything but bad data or a bad source is reported as unexpected."""

    def crash(*_args: object) -> None:
        raise RuntimeError("loader exploded")

    monkeypatch.setattr(service_module, "load_payment_data", crash)
    result = ValidationService().validate_data_content("rows.csv")
    assert _result(result) == (
        False,
        "Unexpected data validation error: loader exploded",
        None,
        "loader exploded",
    )
