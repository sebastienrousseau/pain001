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


"""``pain001.validate`` and ``pain001.generate``: no template paths."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

import pain001
from pain001.constants import TEMPLATES_DIR
from pain001.entry import _scheme_issues
from pain001.exceptions import IssueCode, PaymentValidationError
from pain001.validation.ladder import Ladder
from pain001.validation.schemes import SchemeValidationResult, SchemeViolation

MESSAGE_TYPE = "pain.001.001.03"
SAMPLE = TEMPLATES_DIR / MESSAGE_TYPE / "template.csv"


def _rows(**changes: str) -> list[dict[str, Any]]:
    """Return the bundled sample's rows with ``changes`` in every row."""
    with SAMPLE.open(encoding="utf-8", newline="") as handle:
        return [dict(row, **changes) for row in csv.DictReader(handle)]


def test_a_private_policy_is_the_scheme_rung() -> None:
    pytest.importorskip("celpy")
    rules = (
        "- id: LIMIT\n"
        "  where: payment_amount > 200\n"
        "  severity: error\n"
        "  message: Payment requires review.\n"
    )
    report = pain001.validate(_rows(), MESSAGE_TYPE, rules=rules)
    assert not report.is_valid
    assert {v.rule for v in report.scheme_violations} == {"LIMIT"}


class TestValidate:
    """``pain001.validate``."""

    def test_report_carries_counts_and_issues(self) -> None:
        rows = _rows()
        rows[0]["currency"] = "EURO"
        report = pain001.validate(rows, MESSAGE_TYPE)
        assert isinstance(report, pain001.ValidationReport)
        assert (report.total_rows, report.valid_rows, report.invalid_rows) == (
            4,
            3,
            1,
        )
        assert report.errors == [str(report.issues[0])]

    def test_a_loader_refusal_is_a_report(self) -> None:
        report = pain001.validate(_rows(payment_amount="abc"), MESSAGE_TYPE)
        assert not report.is_valid
        assert report.total_rows == 0
        assert report.issues[0].code == IssueCode.NOT_DECIMAL

    def test_scheme_violations_are_reported(self) -> None:
        report = pain001.validate(
            _rows(payment_currency="USD"), MESSAGE_TYPE, scheme="sepa-sct"
        )
        assert not report.is_valid
        assert report.scheme_violations
        codes = {issue.code for issue in report.issues}
        assert codes == {IssueCode.SCHEME_VIOLATION}

    def test_the_default_message_type_is_pain_001_001_03(self) -> None:
        assert pain001.validate(_rows()).is_valid


class TestGenerate:
    """``pain001.generate``."""

    def test_writes_into_the_working_directory_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = pain001.generate(_rows())
        assert isinstance(result, pain001.GenerationResult)
        assert result.path == tmp_path / f"{MESSAGE_TYPE}.xml"
        assert (result.message_type, result.rows) == (MESSAGE_TYPE, 4)

    def test_creates_the_output_directory(self, tmp_path: Path) -> None:
        out = tmp_path / "a" / "b"
        result = pain001.generate(_rows(), MESSAGE_TYPE, output_dir=out)
        assert result.path.parent == out
        assert result.path.read_text(encoding="utf-8").startswith("<?xml")

    def test_a_scheme_error_refuses_generation(self, tmp_path: Path) -> None:
        with pytest.raises(PaymentValidationError) as caught:
            pain001.generate(
                _rows(payment_currency="USD"),
                MESSAGE_TYPE,
                output_dir=tmp_path,
                scheme="sepa-sct",
            )
        assert caught.value.errors[0].code == IssueCode.SCHEME_VIOLATION
        assert not list(tmp_path.iterdir())

    def test_scheme_issues_never_quote_a_value(self) -> None:
        rows = _rows()
        with pytest.raises(PaymentValidationError) as caught:
            pain001.generate(rows + rows[:1], scheme="anti-duplicate")
        assert "DE36210501700024690959" not in str(caught.value)
        assert caught.value.errors[0].message == (
            "breaks scheme rule DUP-CREDITOR-DATE"
        )

    def test_scheme_warnings_do_not_refuse(self) -> None:
        warning = SchemeViolation("W", "note", 0, None, "warning")
        ladder = Ladder(
            _rows(),
            MESSAGE_TYPE,
            [],
            scheme=SchemeValidationResult("p", [warning]),
        )
        assert _scheme_issues(ladder) == []
