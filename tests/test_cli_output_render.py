# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Rendered output of the shared CLI print helpers.

These tests read what a user sees: the text, the table layout and,
where colour carries meaning (error versus warning), the ANSI style.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from pain001.cli import _output
from pain001.templates.registry import TemplateMetadata
from pain001.validation import SchemeValidationResult
from pain001.validation._scheme_types import SchemeViolation

RED = "\x1b[31m"
YELLOW = "\x1b[33m"


def _plain_console(width: int = 120) -> Console:
    """Return a recording console that emits no colour codes."""
    return Console(
        width=width, record=True, color_system=None, legacy_windows=False
    )


def _ansi_console() -> Console:
    """Return a recording console that keeps standard ANSI colours."""
    return Console(
        width=200,
        record=True,
        force_terminal=True,
        color_system="standard",
        legacy_windows=False,
    )


def _meta(message_type: str, *, deprecated: bool) -> TemplateMetadata:
    """Build a template record with distinct, recognisable fields."""
    return TemplateMetadata(
        message_type=message_type,
        message_category=f"Cat-{message_type}",
        template_path=Path(f"/t/{message_type}/template.xml"),
        xsd_path=Path(f"/t/{message_type}/schema.xsd"),
        example_data_path=None,
        example_xml_path=None,
        supported_input_formats=["csv", "json"],
        iso_version="09",
        deprecated=deprecated,
    )


class _FakeRegistry:
    """Template registry stand-in with one live and one deprecated entry."""

    def __init__(self) -> None:
        """Hold two templates, the second deprecated."""
        self.items = [
            _meta("live.001", deprecated=False),
            _meta("old.001", deprecated=True),
        ]

    def list_templates(self) -> list[TemplateMetadata]:
        """Return both templates in order."""
        return self.items

    def get_template(self, message_type: str) -> TemplateMetadata:
        """Return the template named ``message_type``."""
        return next(m for m in self.items if m.message_type == message_type)


def test_banner_renders_rounded_80_column_box() -> None:
    """The banner is an 80-column rounded box, title and text centred."""
    console = _plain_console()
    _output.print_banner(console)
    bar = "─" * 78
    blank = "│" + " " * 78 + "│"
    expected = [
        " " * 36 + "Pain001" + " " * 37,
        f"╭{bar}╮",
        blank,
        "│      Generates ISO 20022 payment initiation files "
        "(pain.001, pain.008)       │",
        "│                from CSV, SQLite, JSON, JSONL or Parquet data."
        "                │",
        blank,
        "│" + " " * 29 + "https://pain001.com" + " " * 30 + "│",
        blank,
        f"╰{bar}╯",
    ]
    assert console.export_text().splitlines() == expected


def test_template_list_shows_headers_rows_and_deprecation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Headers, every column value and the yes/no flag all render."""
    monkeypatch.setattr(_output, "DEFAULT_TEMPLATE_REGISTRY", _FakeRegistry())
    console = _plain_console()
    _output.print_template_list(console)
    lines = [ln.strip() for ln in console.export_text().splitlines()]
    lines = [ln for ln in lines if ln]
    assert lines[0].split() == ["Message", "Type", "Category", "Deprecated"]
    # SIMPLE_HEAVY draws a heavy rule under the header and nothing else.
    assert set(lines[1]) == {"━"}
    assert lines[2].split() == ["live.001", "Cat-live.001", "no"]
    assert lines[3].split() == ["old.001", "Cat-old.001", "yes"]
    assert len(lines) == 4


def test_template_details_prints_every_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every metadata field appears, with input formats comma-joined."""
    registry = _FakeRegistry()
    registry.items[0] = TemplateMetadata(
        **{
            **registry.items[0].__dict__,
            "example_data_path": Path("/t/data.csv"),
            "example_xml_path": Path("/t/example.xml"),
        }
    )
    monkeypatch.setattr(_output, "DEFAULT_TEMPLATE_REGISTRY", registry)
    console = _plain_console()
    _output.print_template_details(console, "live.001")
    assert console.export_text().splitlines() == [
        "live.001",
        "category: Cat-live.001",
        "template: /t/live.001/template.xml",
        "schema: /t/live.001/schema.xsd",
        "example data: /t/data.csv",
        "example xml: /t/example.xml",
        "input formats: csv, json",
    ]


def _result(*violations: SchemeViolation) -> SchemeValidationResult:
    """Wrap ``violations`` in a scheme result."""
    return SchemeValidationResult(profile="p", violations=list(violations))


def test_scheme_result_lines_for_a_failure_without_explain() -> None:
    """Failure output names the scheme, each violation and the verdict."""
    console = _plain_console()
    result = _result(
        SchemeViolation(rule="R-1", message="bad ccy", index=0, field="ccy"),
        SchemeViolation(
            rule="R-2", message="odd", index=3, severity="warning"
        ),
    )
    _output.print_scheme_result(console, result, "sepa-sct", explain=False)
    assert console.export_text().splitlines() == [
        "→ Validating against scheme 'sepa-sct'...",
        "  row 0 [R-1] ccy: bad ccy",
        "  row 3 [R-2] : odd",
        "✗ Scheme 'sepa-sct' validation failed",
    ]


def test_scheme_result_pass_prints_success_line() -> None:
    """A clean result prints the header and the pass line only."""
    console = _plain_console()
    _output.print_scheme_result(console, _result(), "sepa-inst", explain=True)
    assert console.export_text().splitlines() == [
        "→ Validating against scheme 'sepa-inst'...",
        "✓ Scheme 'sepa-inst' passed",
    ]


def test_scheme_result_remediation_only_when_explaining() -> None:
    """The fix hint is printed under a violation only with ``explain``."""
    violation = SchemeViolation(
        rule="SEPA-CCY", message="m", index=1, field="payment_currency"
    )
    assert violation.remediation
    quiet = _plain_console()
    _output.print_scheme_result(quiet, _result(violation), "s", explain=False)
    assert "fix:" not in quiet.export_text()
    loud = _plain_console(width=400)
    _output.print_scheme_result(loud, _result(violation), "s", explain=True)
    assert f"    fix: {violation.remediation}" in loud.export_text()


def test_scheme_result_colours_errors_red_and_warnings_yellow() -> None:
    """Error rows are red, warning rows yellow, header cyan."""
    console = _ansi_console()
    result = _result(
        SchemeViolation(rule="E", message="err", index=0, field="f"),
        SchemeViolation(rule="W", message="warn", index=1, severity="warning"),
    )
    _output.print_scheme_result(console, result, "s", explain=False)
    lines = console.export_text(styles=True).splitlines()
    assert lines[0].startswith("\x1b[36m")
    assert lines[1].startswith(RED) and "err" in lines[1]
    assert lines[2].startswith(YELLOW) and "warn" in lines[2]
    assert lines[3].startswith("\x1b[1;31m")


def test_scheme_result_pass_line_is_bold_green() -> None:
    """The pass verdict carries bold green styling."""
    console = _ansi_console()
    _output.print_scheme_result(console, _result(), "s", explain=False)
    last = console.export_text(styles=True).splitlines()[-1]
    assert "\x1b[1;32m" in last
