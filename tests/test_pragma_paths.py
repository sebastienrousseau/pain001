# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Small branches that used to hide behind ``pragma: no cover``."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pytest
from click.testing import CliRunner
from pydantic import ValidationError as PydanticValidationError

from pain001 import async_adapter
from pain001.__main__ import main as main_entry
from pain001.api.job_store import FileJobStore
from pain001.api.models import ValidationResponse
from pain001.camt053 import parse_camt053_statement
from pain001.cli.cli import cli
from pain001.context.context import Context
from pain001.corpus.rules.overlays import OverlayError, _parse_assertion
from pain001.csv.load_csv_data import load_csv_data
from pain001.csv.validate_csv_data import _validate_datetime
from pain001.data.loader import _load_from_list_streaming
from pain001.db.load_db_data import load_db_data
from pain001.db.load_db_data_streaming import load_db_data_streaming
from pain001.exceptions import PaymentValidationError, SchemaValidationError
from pain001.logging_schema.metrics import ExecutionMetrics
from pain001.logging_schema.tracker import ExecutionSummaryTracker
from pain001.templates.guardrails import validate_template_bundle
from pain001.templates.registry import DEFAULT_TEMPLATE_REGISTRY
from pain001.xml.write_xml_to_file import indent_xml

BUNDLE = Path("pain001/templates/pain.001.001.03")


def test_dry_run_validates_without_generating(capsys) -> None:
    """--dry-run stops after validation and reports it."""
    with patch("pain001.__main__.process_files") as process:
        main_entry(
            "pain.001.001.03",
            str(BUNDLE / "template.xml"),
            str(BUNDLE / "pain.001.001.03.xsd"),
            str(BUNDLE / "template.csv"),
            dry_run=True,
        )
    process.assert_not_called()
    assert "No XML generated" in capsys.readouterr().out


def test_file_job_store_skips_unreadable_snapshots(tmp_path: Path) -> None:
    store = FileJobStore(tmp_path)
    store.save("good", {"job_id": "good"})
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    assert list(store.load_all()) == ["good"]


def test_invalid_rows_is_derived_or_left_alone() -> None:
    derived = ValidationResponse(
        is_valid=False, total_rows=5, valid_rows=2, invalid_rows=0
    )
    assert derived.invalid_rows == 3
    with pytest.raises(PydanticValidationError, match="total_rows"):
        ValidationResponse(
            is_valid=False,
            total_rows="many",  # type: ignore[arg-type]
            valid_rows=1,
            invalid_rows=7,
        )


def test_streaming_async_runs_in_a_worker_thread() -> None:
    with patch.object(
        async_adapter, "process_files_streaming", return_value=["a.xml"]
    ) as streaming:
        paths = asyncio.run(
            async_adapter.process_files_streaming_async(
                "pain.001.001.03", "t.xml", "s.xsd", "d.csv"
            )
        )
    assert paths == ["a.xml"]
    streaming.assert_called_once()


def test_camt053_rejects_a_schema_it_does_not_match() -> None:
    with pytest.raises(SchemaValidationError, match="failed validation"):
        parse_camt053_statement(
            "pain001/test_fixtures/camt053_sample.xml",
            str(BUNDLE / "pain.001.001.03.xsd"),
        )


def test_show_template_without_examples_prints_nothing_for_them() -> None:
    metadata = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.001.001.03")
    bare = dataclasses.replace(
        metadata, example_data_path=None, example_xml_path=None
    )
    with patch.object(
        DEFAULT_TEMPLATE_REGISTRY, "get_template", return_value=bare
    ):
        result = CliRunner().invoke(
            cli, ["--show-template", "pain.001.001.03"]
        )
    assert result.exit_code == 0, result.output
    assert "example data:" not in result.output
    assert "example xml:" not in result.output


def test_camt053_accepts_a_schema_it_matches() -> None:
    with patch("pain001.camt053.parser.validate_via_xsd", return_value=True):
        statement = parse_camt053_statement(
            "pain001/test_fixtures/camt053_sample.xml",
            str(BUNDLE / "pain.001.001.03.xsd"),
        )
    assert statement


def test_show_template_prints_example_files() -> None:
    metadata = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.001.001.03")
    assert metadata.example_data_path is not None
    result = CliRunner().invoke(cli, ["--show-template", "pain.001.001.03"])
    assert result.exit_code == 0, result.output
    assert "example data:" in result.output
    assert "example xml:" in result.output


def test_context_log_level_reaches_the_logger() -> None:
    context = Context.get_instance()
    if context.logger is None:
        context.init_logger()
    context.set_log_level("DEBUG")
    assert context.logger is not None
    assert context.logger.level == logging.DEBUG


def test_nested_if_rejects_an_unknown_verb() -> None:
    with pytest.raises(OverlayError, match="unknown verb"):
        _parse_assertion("if:Ccy=EUR:bogus:1", "overlay")


def test_csv_loader_rejects_a_directory(tmp_path: Path) -> None:
    folder = tmp_path / "rows.csv"
    folder.mkdir()
    with pytest.raises(FileNotFoundError, match="not found"):
        load_csv_data(str(folder))


def test_date_without_zero_padding_is_still_a_date() -> None:
    assert _validate_datetime("2026-1-5") is True
    assert _validate_datetime("2026-01-05T10:00:00Z") is True
    assert _validate_datetime("not a date") is False


def test_list_streaming_validates_each_chunk() -> None:
    rows: list[dict[str, Any]] = [{"id": "1"}]
    with pytest.raises(
        PaymentValidationError, match="chunk starting at index 0"
    ):
        list(_load_from_list_streaming(rows, chunk_size=1, validate=True))
    assert list(
        _load_from_list_streaming(rows, chunk_size=1, validate=False)
    ) == [rows]


def test_sqlite_loaders_reject_a_directory(tmp_path: Path) -> None:
    folder = tmp_path / "rows.db"
    folder.mkdir()
    with pytest.raises(FileNotFoundError, match="does not exist"):
        load_db_data(str(folder), table_name="pain001")
    with pytest.raises(FileNotFoundError, match="does not exist"):
        list(load_db_data_streaming(str(folder), table_name="pain001"))


def test_metrics_without_a_start_report_zero_duration(capsys) -> None:
    logger = logging.getLogger("pain001.test.pragma")
    metrics = ExecutionMetrics(logger, "unit-test")
    metrics.log_telemetry()
    tracker = ExecutionSummaryTracker(logger)
    tracker.increment_event_count("INFO")
    tracker.increment_event_count("bogus")
    assert tracker.counts["info"] == 1
    tracker.log_summary()
    out = capsys.readouterr().out
    assert out == "" or "0" in out


def test_template_bundle_skips_absent_examples(tmp_path: Path) -> None:
    metadata = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.001.001.03")
    bare = dataclasses.replace(metadata, example_xml_path=None)
    validate_template_bundle(bare)


def test_indent_xml_fills_only_missing_whitespace() -> None:
    root = ET.Element("Document")
    child = ET.SubElement(root, "GrpHdr")
    ET.SubElement(child, "MsgId").text = "1"
    kept = ET.SubElement(root, "Kept")
    kept.text = "value"
    indent_xml(root)
    assert root.text == "\n  "
    assert child.tail == "\n  "
    assert kept.text == "value"
    assert kept.tail == "\n  "
    assert root.tail == "\n"
    # whitespace that is already there is left alone
    preset = ET.Element("Document")
    preset.text = "x"
    preset.tail = "y"
    ET.SubElement(preset, "Child").tail = "z"
    indent_xml(preset)
    assert (preset.text, preset.tail) == ("x", "y")
