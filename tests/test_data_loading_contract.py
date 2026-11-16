# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Pin the universal loader's dispatch, refusals and messages exactly.

The mutation ratchet found mutants of ``pain001.data.loader``
(``_get_file_loaders``, ``_load_any``, ``_load_from_file``) and of
``pain001.data._checks`` (``_refuse``, ``_checked``) that survived:
earlier tests matched the error text with a regex search, or never
looked at the dispatch table, the arguments a loader is called with or
the fields of the error raised. Each test here asserts one of those
exactly so a change to it fails directly.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import pytest

import pain001.security
from pain001.csv.load_csv_data import load_csv_data
from pain001.csv.validate_csv_data import row_issues
from pain001.data import loader as loader_module
from pain001.data._checks import _checked, _refuse
from pain001.db.validate_db_data import db_row_issues
from pain001.exceptions import (
    DataSourceError,
    IssueCode,
    PaymentValidationError,
    RowIssue,
)
from pain001.json.load_json_data import load_json_data, load_jsonl_data
from pain001.parquet.load_parquet_data import load_parquet_data
from pain001.plugins.contracts import LoaderResult
from pain001.plugins.registry import registry as plugin_registry
from pain001.templates.registry import DEFAULT_TEMPLATE_REGISTRY
from pain001.validation import _identifiers

_TYPE = "pain.001.001.09"
_MISSING = IssueCode.MISSING_VALUE


def _issue(line: int, column: str | None) -> RowIssue:
    return RowIssue(line, column, _MISSING, "missing value")


def test_refuse_with_no_issues_raises_nothing() -> None:
    _refuse("Headline", [])


def test_refuse_one_issue_names_it_in_the_singular() -> None:
    issue = _issue(2, "debtor_name")
    with pytest.raises(PaymentValidationError) as caught:
        _refuse("Headline", [issue])
    assert str(caught.value) == (
        "Headline (1 problem):\n"
        f"  line 2, column debtor_name: missing value ({_MISSING})"
    )
    assert caught.value.field == "debtor_name"
    assert caught.value.errors == (issue,)


def test_refuse_two_issues_count_in_the_plural() -> None:
    issues = [_issue(3, "a"), _issue(4, "b")]
    with pytest.raises(PaymentValidationError) as caught:
        _refuse("Rows bad", issues)
    assert str(caught.value) == (
        "Rows bad (2 problems):\n"
        f"  line 3, column a: missing value ({_MISSING})\n"
        f"  line 4, column b: missing value ({_MISSING})"
    )
    assert caught.value.field == "a"
    assert caught.value.errors == tuple(issues)


def _spy_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[Any, ...]]:
    calls: list[tuple[Any, ...]] = []

    def spy(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(_identifiers, "check_identifiers", spy)
    return calls


def test_checked_passes_its_defaults_to_the_identifier_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _spy_identifiers(monkeypatch)
    rows = [{"a": "1"}]
    assert _checked(rows, True) is rows
    assert calls == [((rows, 0, 1), {})]


def test_checked_forwards_start_and_first_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _spy_identifiers(monkeypatch)
    rows = [{"a": "1"}]
    assert _checked(rows, True, start=5, first_line=2) is rows
    assert calls == [((rows, 5, 2), {})]


def test_checked_skips_the_check_when_not_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _spy_identifiers(monkeypatch)
    rows = [{"a": "1"}]
    assert _checked(rows, False) is rows
    assert calls == []


def test_dispatch_table_names_each_loader_and_check() -> None:
    table = loader_module._get_file_loaders()
    assert list(table) == [".csv", ".db", ".json", ".jsonl", ".parquet"]
    assert table[".csv"] == (load_csv_data, row_issues, "CSV")
    assert table[".json"] == (load_json_data, row_issues, "JSON")
    assert table[".jsonl"] == (load_jsonl_data, row_issues, "JSONL")
    assert table[".parquet"] == (load_parquet_data, row_issues, "Parquet")
    assert len(table[".db"]) == 3
    assert table[".db"][1:] == (db_row_issues, "Database")


def test_db_entry_reads_the_pain001_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Any, ...]] = []

    def spy(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        calls.append((args, kwargs))
        return [{"row": 1}]

    monkeypatch.setattr(loader_module, "load_db_data", spy)
    db_loader = loader_module._get_file_loaders()[".db"][0]
    assert db_loader("x.db") == [{"row": 1}]
    assert calls == [(("x.db",), {"table_name": "pain001"})]


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("rows.csv", "_load_from_file"),
        ([{"a": 1}], "_load_from_list"),
        ({"a": 1}, "_load_from_dict"),
    ],
)
def test_load_any_dispatches_with_the_message_type(
    monkeypatch: pytest.MonkeyPatch, source: Any, target: str
) -> None:
    calls: list[tuple[Any, ...]] = []

    def spy(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        calls.append((args, kwargs))
        return [{"done": target}]

    monkeypatch.setattr(loader_module, target, spy)
    assert loader_module._load_any(source, _TYPE) == [{"done": target}]
    assert calls == [((source, _TYPE), {})]


def test_load_any_names_an_unsupported_type() -> None:
    source: Any = 42
    with pytest.raises(DataSourceError) as caught:
        loader_module._load_any(source)
    assert str(caught.value) == (
        "Unsupported data source type: int. "
        "Expected str (file path), list, or dict."
    )


def test_unknown_extension_names_the_supported_set() -> None:
    with pytest.raises(DataSourceError) as caught:
        loader_module._load_from_file("rows.RTF")
    assert str(caught.value) == (
        "Unsupported file type: rows.RTF. "
        "Expected .csv, .db, .json, .jsonl, or .parquet file, or "
        "install a plugin that registers the '.rtf' extension "
        "(see `pain001 plugins list`)."
    )


def test_companion_extension_names_the_package() -> None:
    with pytest.raises(DataSourceError) as caught:
        loader_module._load_from_file("rows.XLSX")
    assert str(caught.value) == (
        "No loader registered for .xlsx; install pain001-loader-xlsx "
        "(file: rows.XLSX)."
    )


def test_path_failure_becomes_file_not_found_with_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError) as caught:
        loader_module._load_from_file("absent.csv")
    cause = caught.value.__cause__
    assert isinstance(cause, FileNotFoundError)
    assert str(caught.value) == (
        f"Data file validation failed: absent.csv\nError: {cause}"
    )


class _Loader:
    """A plugin loader that records the path it is given."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.paths: list[str] = []

    def load(self, path: str) -> LoaderResult:
        self.paths.append(path)
        return LoaderResult(rows=self.rows, source_hint=path)


def _spy_validate_path(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[Any, ...]]:
    calls: list[tuple[Any, ...]] = []
    real = pain001.security.validate_path

    def spy(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(pain001.security, "validate_path", spy)
    return calls


def test_loader_gets_the_validated_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    example = DEFAULT_TEMPLATE_REGISTRY.get_template(_TYPE).example_data_path
    assert example is not None
    shutil.copy(example, tmp_path / "rows.csv")
    monkeypatch.chdir(tmp_path)
    fake = _Loader(load_csv_data("rows.csv"))
    extensions: list[str] = []

    def lookup(ext: str) -> _Loader:
        extensions.append(ext)
        return fake

    monkeypatch.setattr(plugin_registry, "get_loader_for_extension", lookup)
    validated = _spy_validate_path(monkeypatch)
    assert loader_module._load_from_file("rows.csv", _TYPE) is fake.rows
    assert extensions == [".csv"]
    kwargs = {"must_exist": True, "base_dir": os.getcwd()}
    assert validated == [(("rows.csv",), kwargs)]
    expected = str(tmp_path.resolve() / "rows.csv")
    assert [str(path) for path in fake.paths] == [expected]


def test_loaded_rows_are_refused_with_the_format_headline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "rows.csv").write_text("a\n1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    fake = _Loader([{"id": "1"}])
    monkeypatch.setattr(
        plugin_registry, "get_loader_for_extension", lambda _ext: fake
    )
    with pytest.raises(PaymentValidationError) as caught:
        loader_module._load_from_file("rows.csv", _TYPE)
    headline = str(caught.value).split(" (", 1)[0]
    assert headline == "CSV data validation failed for rows.csv"
    assert caught.value.errors[0].line == 2
