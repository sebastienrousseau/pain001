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

"""Row problems are reported by line, column and code, never by value.

Until 0.0.86 a missing column, a bad date or a bad amount failed with
only "CSV data validation failed for <file>": the details went to a
logger nothing listened to. The validators now return one
:class:`~pain001.exceptions.RowIssue` per problem, the loader attaches
them to the :class:`~pain001.exceptions.PaymentValidationError` it
raises, and the command line prints them.
"""

from __future__ import annotations

import csv
import dataclasses
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from pain001.cli.cli import cli
from pain001.csv.validate_csv_data import row_issues, validate_csv_data
from pain001.data.loader import (
    load_payment_data,
    load_payment_data_streaming,
)
from pain001.db.validate_db_data import validate_db_data
from pain001.exceptions import (
    IssueCode,
    PaymentValidationError,
    RowIssue,
    format_issues,
)
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

MTYPE = "pain.001.001.09"
SAMPLE = (
    Path(DEFAULT_TEMPLATE_REGISTRY.get_template(MTYPE).template_path).parent
    / "template.csv"
)
SECRET = "SECRET-VALUE-7"


def _rows() -> list[dict[str, str]]:
    with SAMPLE.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def workdir(monkeypatch, tmp_path: Path) -> Path:
    """An empty working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _bad_amount(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows[1]["payment_amount"] = SECRET
    return rows


def _bad_date(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows[0]["date"] = SECRET
    return rows


def _missing_column(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {k: v for k, v in row.items() if k != "creditor_name"} for row in rows
    ]


def _bad_iban(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows[1]["creditor_account_IBAN"] = "DE00" + SECRET
    return rows


CASES = {
    "bad amount": (
        _bad_amount,
        ["line 3, column payment_amount: not a decimal number (P001-E012)"],
    ),
    "bad date": (
        _bad_date,
        [
            "line 2, column date: not a date (YYYY-MM-DD or ISO 8601) "
            "(P001-E014)"
        ],
    ),
    "missing column": (
        _missing_column,
        [
            "line 2, column creditor_name: missing value (P001-E010)",
            "line 3, column creditor_name: missing value (P001-E010)",
        ],
    ),
    "bad IBAN": (
        _bad_iban,
        ["line 3, column creditor_account_IBAN: not a valid IBAN"],
    ),
}


@pytest.mark.parametrize("case", sorted(CASES))
@pytest.mark.parametrize("command", ["generate", "validate"])
def test_cli_prints_each_problem(
    workdir: Path, case: str, command: str
) -> None:
    """Each failure class names its line, column and code."""
    mutate, expected = CASES[case]
    _write(workdir / "payments.csv", mutate(_rows()))
    result = CliRunner().invoke(
        cli,
        [command, "-t", MTYPE, "-d", "payments.csv"],
        terminal_width=200,
    )
    assert result.exit_code == 1, result.output
    for line in expected:
        assert line in result.output
    assert SECRET not in result.output


def test_cli_caps_the_listing(workdir: Path) -> None:
    """Past twenty problems the listing ends with a count."""
    rows = _rows()
    template = rows[0]
    rows = [dict(template, payment_amount=SECRET) for _ in range(25)]
    _write(workdir / "payments.csv", rows)
    result = CliRunner().invoke(
        cli,
        ["validate", "-t", MTYPE, "-d", "payments.csv"],
        terminal_width=200,
    )
    assert result.exit_code == 1
    assert "line 21, column payment_amount" in result.output
    assert "line 22, column payment_amount" not in result.output
    assert "... and 5 more" in result.output


def test_loader_attaches_issues(workdir: Path) -> None:
    """The exception carries the issues as frozen records."""
    _write(workdir / "payments.csv", _bad_amount(_rows()))
    with pytest.raises(PaymentValidationError) as caught:
        load_payment_data("payments.csv")
    (issue,) = caught.value.errors
    assert issue == RowIssue(
        3, "payment_amount", IssueCode.NOT_DECIMAL, "not a decimal number"
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        issue.line = 4  # type: ignore[misc]
    assert str(caught.value).startswith(
        "CSV data validation failed for payments.csv"
    )
    assert SECRET not in str(caught.value)


def test_json_records_count_from_one(workdir: Path) -> None:
    """Formats without a header line count records from 1."""
    import json

    (workdir / "p.json").write_text(json.dumps(_bad_amount(_rows())))
    with pytest.raises(PaymentValidationError) as caught:
        load_payment_data("p.json")
    assert caught.value.errors[0].line == 2


def test_streaming_lines_continue_across_chunks(workdir: Path) -> None:
    """A later chunk names the line in the whole file."""
    rows = _rows()
    rows = rows + [dict(rows[0]) for _ in range(3)]
    rows[4]["payment_amount"] = SECRET
    _write(workdir / "payments.csv", rows)
    with pytest.raises(PaymentValidationError) as caught:
        list(load_payment_data_streaming("payments.csv", chunk_size=2))
    assert [i.line for i in caught.value.errors] == [6]


def test_identifier_lines_are_one_based(workdir: Path) -> None:
    """An identifier problem names the spreadsheet line too."""
    _write(workdir / "payments.csv", _bad_iban(_rows()))
    with pytest.raises(PaymentValidationError) as caught:
        load_payment_data("payments.csv")
    (issue,) = caught.value.errors
    assert (issue.line, issue.column, issue.code) == (
        3,
        "creditor_account_IBAN",
        IssueCode.INVALID_IBAN,
    )
    assert "line 3, column creditor_account_IBAN" in str(caught.value)


def test_list_input_issues() -> None:
    """A list of rows reports issues from record 1."""
    rows = _bad_date(_rows())
    with pytest.raises(PaymentValidationError) as caught:
        load_payment_data(rows)
    assert caught.value.errors[0].line == 1
    assert caught.value.errors[0].code == IssueCode.NOT_DATE


def test_row_issue_codes_by_type() -> None:
    """Integers and booleans have their own codes."""
    required = {"n": int, "flag": bool}
    from pain001.csv import validate_csv_data as module

    issues = module._issues_for_row({"n": "x", "flag": "maybe"}, required, 7)
    assert [(i.line, i.column, i.code) for i in issues] == [
        (7, "n", IssueCode.NOT_INTEGER),
        (7, "flag", IssueCode.NOT_BOOLEAN),
    ]


def test_empty_input_issue() -> None:
    """An empty input is one issue with no line or column."""
    (issue,) = row_issues([])
    assert issue == RowIssue(
        None, None, IssueCode.EMPTY_INPUT, "the input has no payment rows"
    )
    assert str(issue) == "the input has no payment rows (P001-E001)"


def test_bool_validators_still_answer(caplog) -> None:
    """The boolean validators keep their answer and log no values."""
    rows = _bad_amount(_rows())
    with caplog.at_level("ERROR", logger="pain001"):
        assert validate_csv_data(rows) is False
        assert validate_db_data(rows) is False
    assert "payment_amount" in caplog.text
    assert SECRET not in caplog.text
    assert validate_db_data(_rows()) is True


def test_format_issues_caps() -> None:
    """The shared formatter lists twenty and counts the rest."""
    issues = [
        RowIssue(n, "c", IssueCode.MISSING_VALUE, "missing value")
        for n in range(1, 23)
    ]
    text = format_issues(issues)
    assert text.count("\n") == 21
    assert text.endswith("... and 2 more")
    assert format_issues(issues[:1]) == (
        "\n  line 1, column c: missing value (P001-E010)"
    )


def test_payment_validation_error_defaults() -> None:
    """An error raised without issues has an empty tuple."""
    assert PaymentValidationError("x").errors == ()


def test_copy_of_sample_still_loads(workdir: Path) -> None:
    """A clean file loads with no issues."""
    shutil.copyfile(SAMPLE, workdir / "payments.csv")
    assert len(load_payment_data("payments.csv")) == len(_rows())


def test_package_exports() -> None:
    """The issue types are importable from the package root."""
    import pain001

    assert pain001.RowIssue is RowIssue
    assert pain001.IssueCode is IssueCode
