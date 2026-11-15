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

"""The structured events the generation core emits, field by field.

Operators index these JSON log lines by event and field name, so each
step's event, its fields, and the durations it reports are pinned here,
along with the errors the input checks raise.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pain001.constants import TEMPLATES_DIR
from pain001.context.context import Context
from pain001.core import core
from pain001.exceptions import PaymentValidationError, XMLGenerationError

MT = "pain.001.001.03"
CORE_LOGGER = "pain001.core.core"


def _events(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    """The core's structured events, parsed, in order."""
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == CORE_LOGGER
    ]


def _rows(**changes: str) -> list[dict[str, Any]]:
    """The bundled sample's rows with ``changes`` in every row."""
    with (TEMPLATES_DIR / MT / "template.csv").open(encoding="utf-8") as fh:
        return [dict(row, **changes) for row in csv.DictReader(fh)]


class _Clock:
    """A stand-in for the ``time`` module whose clock reads given values."""

    def __init__(self, *readings: float) -> None:
        self.readings = list(readings)

    def time(self) -> float:
        """The next reading."""
        return self.readings.pop(0)


def test_an_unknown_message_type_is_logged_and_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The error is raised, logged plainly, and emitted as an event."""
    caplog.set_level(logging.INFO)
    message = "Error: Invalid XML message type: 'pain.999'."
    with pytest.raises(XMLGenerationError) as caught:
        core._validate_inputs("pain.999", "t.xml", "s.xsd")
    assert str(caught.value) == message
    context_name = Context.get_instance().get_logger().name
    assert message in [
        r.getMessage() for r in caplog.records if r.name == context_name
    ]
    [event] = _events(caplog)
    assert event["event"] == "validation_error"
    assert event["level"] == "ERROR"
    assert (event["validation_type"], event["message_type"]) == (
        "message_type",
        "pain.999",
    )
    assert event["error_message"] == message


def test_a_missing_template_is_logged_and_raised(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """A missing template raises FileNotFoundError naming the template."""
    caplog.set_level(logging.INFO)
    missing = str(tmp_path / "missing.xml")
    with pytest.raises(FileNotFoundError) as caught:
        core._validate_inputs(MT, missing, "s.xsd")
    text = str(caught.value)
    assert text.startswith(f"Error: XML template '{missing}' does not exist")
    context_name = Context.get_instance().get_logger().name
    logged = [r.getMessage() for r in caplog.records if r.name == context_name]
    assert logged and logged[0].startswith("Error: XML template '")
    [event] = _events(caplog)
    assert event["event"] == "validation_error"
    assert event["validation_type"] == "template_file"
    assert event["error_message"] == text


def test_a_missing_schema_is_logged_and_raised(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """A missing schema raises FileNotFoundError naming the schema."""
    caplog.set_level(logging.INFO)
    template = str(TEMPLATES_DIR / MT / "template.xml")
    missing = str(tmp_path / "missing.xsd")
    with pytest.raises(FileNotFoundError) as caught:
        core._validate_inputs(MT, template, missing)
    text = str(caught.value)
    assert text.startswith(
        f"Error: XSD schema file '{missing}' does not exist"
    )
    context_name = Context.get_instance().get_logger().name
    logged = [r.getMessage() for r in caplog.records if r.name == context_name]
    assert logged and logged[0].startswith("Error: XSD schema file '")
    [event] = _events(caplog)
    assert (event["event"], event["validation_type"]) == (
        "validation_error",
        "schema_file",
    )
    assert event["error_message"] == text


def test_loading_rows_emits_start_and_success(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defaults load the rows; the events name the source and the timing."""
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(core, "time", _Clock(1002.5))
    rows = core._load_data(_rows(), 1000.0)
    assert len(rows) == 4
    start, success = _events(caplog)
    assert (start["event"], start["data_source_type"]) == (
        "data_load_start",
        "list",
    )
    assert success["event"] == "data_load_success"
    assert (success["data_source_type"], success["record_count"]) == (
        "list",
        4,
    )
    assert success["duration_ms"] == 2500


def test_loading_reports_the_metric_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``file_loaded`` metric carries the source, count and duration."""
    from pain001 import observability

    seen: list[Any] = []
    observability.register_metrics_callback(seen.append)
    monkeypatch.setattr(core, "time", _Clock(1001.0))
    try:
        core._load_data(_rows(), 1000.0)
    finally:
        observability.clear_metrics_callbacks()
    [event] = [e for e in seen if e.name == "file_loaded"]
    assert event.attributes == {
        "data_source_type": "list",
        "record_count": 4,
        "file_size_bytes": None,
        "duration_ms": 1000,
    }


def test_a_bad_identifier_fails_loading_by_default() -> None:
    """Identifier checks are on unless the caller turns them off."""
    rows = _rows(debtor_account_IBAN="DE00512108001245126162")
    with pytest.raises(PaymentValidationError, match="not a valid IBAN"):
        core._load_data(rows, 1000.0)
    assert len(core._load_data(rows, 1000.0, identifier_checks=False)) == 4


def test_a_missing_file_is_an_error_event(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The error event names the source kind, the error and the timing."""
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(core, "time", _Clock(1000.25))
    with pytest.raises(FileNotFoundError) as caught:
        core._load_data(str(tmp_path / "missing.csv"), 1000.0)
    error = _events(caplog)[-1]
    assert error["event"] == "data_load_error"
    assert error["level"] == "ERROR"
    assert error["data_source_type"] == "csv"
    assert error["error_type"] == "FileNotFoundError"
    assert error["error_message"] == str(caught.value).replace("\n", "")
    assert error["duration_ms"] == 250


def test_registering_namespaces_is_an_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The namespace step names its message type."""
    caplog.set_level(logging.INFO)
    core._register_message_namespaces(MT)
    [event] = _events(caplog)
    assert (event["event"], event["message_type"]) == (
        "namespace_register",
        MT,
    )


def test_generation_passes_its_options_and_times_itself(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Generation gets every option; the duration is milliseconds."""
    caplog.set_level(logging.INFO)
    calls: list[dict[str, Any]] = []

    def generate_xml(*args: Any, **kwargs: Any) -> str:
        calls.append(kwargs)
        return "out.xml"

    monkeypatch.setattr(
        core, "xml_generate", SimpleNamespace(generate_xml=generate_xml)
    )
    monkeypatch.setattr(core, "time", _Clock(1000.0, 1001.5))
    result = core._generate_and_log(
        [{}, {}], MT, "t.xml", "s.xsd", xml_sign_cert="cert"
    )
    assert result == ("out.xml", 1500)
    [kwargs] = calls
    assert kwargs["envelop_bah"] is False
    assert kwargs["xml_sign_cert"] == "cert"
    [event] = _events(caplog)
    assert (event["event"], event["message_type"], event["record_count"]) == (
        "xml_generate_start",
        MT,
        2,
    )
