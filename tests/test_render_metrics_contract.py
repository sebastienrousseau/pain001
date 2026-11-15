# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Render preparation, staging and the JSON log line, pinned exactly.

These functions were caught only by tests that happened to observe
them: whether a change to them failed a test depended on which tests
mutmut selected, so the mutation ratchet saw them flip between runs.
Each behaviour is checked here directly, with a fixed clock where time
is measured.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pain001.data.loader import load_payment_data
from pain001.logging_schema.formatter import JSONFormatter
from pain001.observability import (
    MetricEvent,
    clear_metrics_callbacks,
    register_metrics_callback,
)
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.xml import _render, publish
from pain001.xml.generate_xml import generate_xml_string


@pytest.fixture
def events() -> Iterator[list[MetricEvent]]:
    """Collect the metric events emitted during the test."""
    seen: list[MetricEvent] = []
    clear_metrics_callbacks()
    register_metrics_callback(seen.append)
    yield seen
    clear_metrics_callbacks()


def _rows(message_type: str) -> list[dict[str, Any]]:
    """The bundled example rows for ``message_type``."""
    bundle = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    return load_payment_data(str(bundle.example_data_path))


def _prepare(
    monkeypatch: pytest.MonkeyPatch, message_type: str
) -> tuple[dict[str, Any], int, list[bool]]:
    """Run the preparation with a 250 ms clock; record ``compact``."""
    ticks = iter([10.0, 10.25])
    monkeypatch.setattr(
        _render, "time", SimpleNamespace(time=lambda: next(ticks))
    )
    compact: list[bool] = []
    real = _render._normalize_financial_fields

    def spy(data: list[dict[str, Any]], **kwargs: Any) -> Any:
        """Record the ``compact`` argument, then normalise as usual."""
        compact.append(kwargs.get("compact", False))
        return real(data, **kwargs)

    monkeypatch.setattr(_render, "_normalize_financial_fields", spy)
    bundle = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    _, data, count = _render._prepare_template_and_data(
        _rows(message_type), message_type, str(bundle.template_path)
    )
    return data, count, compact


def test_preparation_sets_totals_and_reports_its_duration(
    monkeypatch: pytest.MonkeyPatch, events: list[MetricEvent]
) -> None:
    """Totals come from the rows; one event carries type, count and ms."""
    data, count, compact = _prepare(monkeypatch, "pain.001.001.03")
    assert compact == [True]
    assert count == 4
    assert (
        data["nb_of_txs"],
        data["payment_nb_of_txs"],
        data["ctrl_sum"],
    ) == (
        "4",
        "4",
        "900.00",
    )
    prepared = [e for e in events if e.name == "xml_prepared"]
    assert [e.attributes for e in prepared] == [
        {
            "message_type": "pain.001.001.03",
            "record_count": 4,
            "duration_ms": 250,
        }
    ]


def test_an_edition_without_a_payment_count_gets_none(
    monkeypatch: pytest.MonkeyPatch, events: list[MetricEvent]
) -> None:
    """Only editions whose preparer has ``payment_nb_of_txs`` get it set."""
    data, _, _ = _prepare(monkeypatch, "pain.001.001.05")
    assert "payment_nb_of_txs" not in data
    assert data["nb_of_txs"] == "1"


def test_a_staged_file_is_a_private_hidden_sibling(tmp_path: Path) -> None:
    """``.name.<12 hex>.tmp`` beside the target, owner read and write only."""
    handle, staged = publish._stage(str(tmp_path / "out.xml"))
    try:
        assert Path(staged).parent == tmp_path
        assert re.fullmatch(
            r"\.out\.xml\.[0-9a-f]{12}\.tmp", Path(staged).name
        )
        assert Path(staged).stat().st_mode & 0o777 == 0o600
    finally:
        os.close(handle)


def test_a_valid_file_reports_its_schema_and_type(
    tmp_path: Path, events: list[MetricEvent]
) -> None:
    """The passed event names the schema checked and the message type."""
    message_type = "pain.001.001.03"
    bundle = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    document = tmp_path / "out.xml"
    document.write_text(
        generate_xml_string(
            _rows(message_type),
            message_type,
            str(bundle.template_path),
            str(bundle.xsd_path),
        ),
        encoding="utf-8",
    )
    events.clear()
    publish.require_xsd_valid_file(
        str(document), str(bundle.xsd_path), message_type
    )
    [passed] = [e for e in events if e.name == "xsd_validation_passed"]
    assert passed.attributes["message_type"] == message_type
    assert passed.attributes["schema_path"] == str(bundle.xsd_path)


def test_a_log_line_has_sorted_keys_and_keeps_plugin_extras() -> None:
    """Keys are sorted; the allowed plugin diagnostics are carried."""
    record = logging.LogRecord(
        "pain001.x", logging.INFO, "f", 1, "hi", None, None
    )
    record.plugin_name = "acme"
    record.plugin_kind = "loader"
    line = JSONFormatter().format(record)
    keys = json.loads(
        line, object_pairs_hook=lambda pairs: [k for k, _ in pairs]
    )
    assert keys == sorted(keys)
    data = json.loads(line)
    assert (data["plugin_name"], data["plugin_kind"]) == ("acme", "loader")
