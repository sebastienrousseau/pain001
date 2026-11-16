# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Pin what the CSV loader and row checks do, value by value.

The mutation ratchet found mutants of ``load_csv_data`` and of the row
helpers in ``validate_csv_data`` that survived because earlier tests
only killed them incidentally: they matched error text with a regex
search, or never looked at the arguments handed to ``validate_path``
and ``open``, or at the log lines. Each test here asserts one exact
behaviour (an argument, a message, a list of issues) so a change to it
fails directly.
"""

from __future__ import annotations

import builtins
import os
from pathlib import Path
from typing import Any

import pytest

from pain001.csv import load_csv_data as csv_module
from pain001.csv.load_csv_data import load_csv_data
from pain001.csv.validate_csv_data import (
    _issues_for_row,
    _validate_datetime,
    _validate_row,
)
from pain001.exceptions import DataSourceError, IssueCode, RowIssue


class _Logger:
    """Records every ``error`` call instead of logging it."""

    def __init__(self) -> None:
        self.errors: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def error(self, *args: Any, **kwargs: Any) -> None:
        self.errors.append((args, kwargs))


@pytest.fixture
def spy_logger(monkeypatch: pytest.MonkeyPatch) -> _Logger:
    """Replace the loader's module logger with a recorder."""
    spy = _Logger()
    monkeypatch.setattr(csv_module, "logger", spy)
    return spy


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run the test from ``tmp_path``: the loader only reads below cwd."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8", newline="")
    return path.name


def test_path_is_validated_against_cwd_and_must_exist(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = _write(workdir / "rows.csv", "a,b\n1,2\n")
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    real = csv_module.validate_path

    def spy(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(csv_module, "validate_path", spy)
    assert load_csv_data(name) == [{"a": "1", "b": "2"}]
    assert calls == [((name,), {"must_exist": True, "base_dir": os.getcwd()})]


def test_path_validation_failure_is_logged_and_reraised(
    workdir: Path, spy_logger: _Logger
) -> None:
    with pytest.raises(FileNotFoundError) as caught:
        load_csv_data("absent.csv")
    expected = f"Path validation failed: absent.csv - {caught.value}"
    assert spy_logger.errors == [((expected,), {})]


def test_a_directory_is_not_a_file(workdir: Path, spy_logger: _Logger) -> None:
    (workdir / "folder.csv").mkdir()
    with pytest.raises(FileNotFoundError) as caught:
        load_csv_data("folder.csv")
    assert str(caught.value) == "File 'folder.csv' not found."
    assert spy_logger.errors == [(("File not found: folder.csv",), {})]


def test_file_is_opened_as_utf8_with_universal_newlines_off(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = _write(workdir / "rows.csv", "a\n1\n")
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def spy(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return builtins.open(*args, **kwargs)

    monkeypatch.setattr(csv_module, "open", spy, raising=False)
    load_csv_data(name)
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert str(args[0]) == str(workdir.resolve() / name)
    assert kwargs == {"newline": "", "encoding": "utf-8"}


def test_rows_are_returned_unsanitised_by_default(workdir: Path) -> None:
    name = _write(workdir / "rows.csv", "a,b\n=1+1,plain\n")
    assert load_csv_data(name) == [{"a": "=1+1", "b": "plain"}]


def test_sanitise_prefixes_formulas_and_keeps_non_strings(
    workdir: Path,
) -> None:
    name = _write(workdir / "rows.csv", "a,b\n=1+1,plain,extra\n")
    rows = load_csv_data(name, sanitize_formula=True)
    assert rows == [{"a": "'=1+1", "b": "plain", None: ["extra"]}]


def test_read_error_is_logged_and_reraised(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, spy_logger: _Logger
) -> None:
    name = _write(workdir / "rows.csv", "a\n1\n")
    failure = OSError("disk gone")

    def broken(*_args: Any, **_kwargs: Any) -> Any:
        raise failure

    monkeypatch.setattr(csv_module, "open", broken, raising=False)
    with pytest.raises(OSError) as caught:
        load_csv_data(name)
    assert caught.value is failure
    assert spy_logger.errors == [(("IOError reading file: rows.csv",), {})]


def test_decode_error_is_logged_and_reraised(
    workdir: Path, spy_logger: _Logger
) -> None:
    (workdir / "rows.csv").write_bytes(b"a\n\xff\xfe\n")
    with pytest.raises(UnicodeDecodeError):
        load_csv_data("rows.csv")
    expected = "UnicodeDecodeError decoding file: rows.csv"
    assert spy_logger.errors == [((expected,), {})]


def test_header_only_file_is_empty(workdir: Path) -> None:
    name = _write(workdir / "rows.csv", "a,b\n")
    with pytest.raises(DataSourceError) as caught:
        load_csv_data(name)
    assert str(caught.value) == "The CSV file 'rows.csv' is empty."


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("2023-03-10T15:30:47Z", True),
        ("2023-03-10T15:30:47.000Z", True),
        ("2023-03-10", True),
        ("Z", False),
        ("2023-03-10 extra", False),
    ],
)
def test_datetime_values(value: str, valid: bool) -> None:
    assert _validate_datetime(value) is valid


def test_row_reports_every_missing_and_invalid_column() -> None:
    required = {"a": int, "b": str, "c": int, "d": float, "e": str}
    row = {"b": "  ", "c": "x", "d": "nan-ish", "e": " ok "}
    assert _validate_row(row, required) == (["a", "b"], ["c", "d"])


def test_row_coerces_native_values_before_checking() -> None:
    required = {"n": int, "f": float, "flag": bool}
    assert _validate_row({"n": 3, "f": 1.5, "flag": True}, required) == (
        [],
        [],
    )


def test_issues_list_surplus_first_then_missing_then_types() -> None:
    required = {"a": str, "b": int, "c": float}
    row = {"a": "", "b": "x", "c": "y", None: ["extra"]}
    assert _issues_for_row(row, required, 7) == [
        RowIssue(
            7,
            None,
            IssueCode.EXTRA_VALUES,
            "more values than the header has columns",
        ),
        RowIssue(7, "a", IssueCode.MISSING_VALUE, "missing value"),
        RowIssue(7, "b", IssueCode.NOT_INTEGER, "not a whole number"),
        RowIssue(7, "c", IssueCode.NOT_DECIMAL, "not a decimal number"),
    ]


def test_issues_without_surplus_keep_column_order() -> None:
    required = {"a": str, "b": str}
    assert _issues_for_row({}, required, 2) == [
        RowIssue(2, "a", IssueCode.MISSING_VALUE, "missing value"),
        RowIssue(2, "b", IssueCode.MISSING_VALUE, "missing value"),
    ]
