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

"""The shared validation ladder: one sequence of checks for every surface."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

import pytest

from pain001.constants import TEMPLATES_DIR
from pain001.core.core import process_files_streaming
from pain001.exceptions import IssueCode, PaymentValidationError
from pain001.validation import ValidationConfig, ValidationService
from pain001.validation.ladder import (
    check_scheme,
    load_valid_chunks,
    read_policy,
    run_ladder,
    schema_issues,
)
from pain001.validation.schema_validator import ValidationError

MESSAGE_TYPE = "pain.001.001.03"
SAMPLE = TEMPLATES_DIR / MESSAGE_TYPE / "template.csv"


def _rows(**changes: str) -> list[dict[str, Any]]:
    """Return the bundled sample's rows with ``changes`` in every row."""
    with SAMPLE.open(encoding="utf-8", newline="") as handle:
        return [dict(row, **changes) for row in csv.DictReader(handle)]


def _write(path: Path, rows: list[dict[str, Any]]) -> str:
    """Write ``rows`` as CSV at ``path`` and return the path."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def test_counts_name_the_refused_rows() -> None:
    rows = _rows()
    rows[1]["currency"] = "EURO"
    ladder = run_ladder(rows, MESSAGE_TYPE)
    assert (ladder.total, ladder.valid, ladder.invalid) == (4, 3, 1)
    assert not ladder.is_valid
    [issue] = ladder.issues()
    assert (issue.line, issue.column, issue.code) == (
        2,
        "currency",
        IssueCode.SCHEMA_VIOLATION,
    )
    assert "EURO" not in issue.message


def test_csv_lines_count_the_header(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["currency"] = "EURO"
    with pytest.raises(PaymentValidationError) as caught:
        run_ladder(
            _write(tmp_path / "p.csv", rows), MESSAGE_TYPE
        ).require_valid()
    assert caught.value.errors[0].line == 2
    assert caught.value.field == "currency"
    assert "(1 problem)" in str(caught.value)


def test_several_problems_are_counted() -> None:
    with pytest.raises(PaymentValidationError, match=r"\(4 problems\)"):
        run_ladder(_rows(currency="EURO"), MESSAGE_TYPE).require_valid()


def test_a_path_object_is_accepted() -> None:
    assert run_ladder(Path(SAMPLE), MESSAGE_TYPE).is_valid


def test_a_whole_row_finding_has_no_column() -> None:
    error = ValidationError("'id' is a required property", "$", {}, "required")
    [issue] = schema_issues([(0, [error])], start=3, first_line=2)
    assert (issue.line, issue.column) == (5, None)
    assert issue.message == "'id' is a required property"


def test_a_non_text_value_is_left_in_the_message() -> None:
    error = ValidationError("5 is not of type 'string'", "$.id", 5, "type")
    [issue] = schema_issues([(0, [error])])
    assert issue.message == "5 is not of type 'string'"


def test_scheme_rung_runs_when_asked() -> None:
    ladder = run_ladder(_rows(), MESSAGE_TYPE, scheme="xborder-ct")
    assert ladder.scheme is not None


def test_policy_needs_the_rules_extra(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(sys.modules, "pain001.validation.policy", None)
    with pytest.raises(ValueError, match="pain001\\[rules\\]"):
        check_scheme(_rows(), MESSAGE_TYPE, rules="rules: []")
    policy = tmp_path / "policy.yaml"
    policy.write_text("rules: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="pain001\\[rules\\]"):
        read_policy(policy)


def test_read_policy_reads_the_file(tmp_path: Path) -> None:
    pytest.importorskip("celpy")
    policy = tmp_path / "policy.yaml"
    policy.write_text("rules: []\n", encoding="utf-8")
    assert read_policy(policy) == "rules: []\n"


def test_every_valid_chunk_is_yielded(tmp_path: Path) -> None:
    path = _write(tmp_path / "p.csv", _rows())
    chunks = list(load_valid_chunks(path, MESSAGE_TYPE, chunk_size=3))
    assert [len(chunk) for chunk in chunks] == [3, 1]


def test_chunks_name_lines_of_the_whole_input(tmp_path: Path) -> None:
    rows = _rows()
    rows[3]["currency"] = "EURO"
    path = _write(tmp_path / "p.csv", rows)
    chunks = load_valid_chunks(path, MESSAGE_TYPE, chunk_size=2)
    assert len(next(chunks)) == 2
    with pytest.raises(PaymentValidationError) as caught:
        next(chunks)
    assert caught.value.errors[0].line == 5


def test_streaming_generation_refuses_a_schema_violation(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path / "p.csv", _rows(currency="EURO"))
    with pytest.raises(PaymentValidationError, match="P001-E030"):
        process_files_streaming(
            MESSAGE_TYPE,
            str(TEMPLATES_DIR / MESSAGE_TYPE / "template.xml"),
            str(TEMPLATES_DIR / MESSAGE_TYPE / f"{MESSAGE_TYPE}.xsd"),
            path,
            chunk_size=2,
            output_dir=str(tmp_path),
        )


class TestValidationService:
    """``ValidationService.validate_all`` climbs the same ladder."""

    def _config(self, path: str, message_type: str) -> ValidationConfig:
        base = TEMPLATES_DIR / MESSAGE_TYPE
        return ValidationConfig(
            xml_message_type=message_type,
            xml_template_file_path=str(base / "template.xml"),
            xsd_schema_file_path=str(base / f"{MESSAGE_TYPE}.xsd"),
            data_file_path=path,
        )

    def test_refuses_a_schema_violation(self, tmp_path: Path) -> None:
        path = _write(tmp_path / "p.csv", _rows(currency="EURO"))
        report = ValidationService().validate_all(
            self._config(path, MESSAGE_TYPE)
        )
        assert not report.results["data_content"].is_valid
        assert "P001-E030" in (report.results["data_content"].error or "")

    def test_an_unknown_type_still_loads_the_data(
        self, tmp_path: Path
    ) -> None:
        path = _write(tmp_path / "p.csv", _rows(currency="EURO"))
        report = ValidationService().validate_all(
            self._config(path, "pain.999.001.01")
        )
        assert not report.results["message_type"].is_valid
        assert report.results["data_content"].is_valid
