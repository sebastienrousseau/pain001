# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The template private bank profile in examples/bank-profile/ works.

docs/bank-profiles.md tells a bank's team to start from these two
files; each rule must fire on a document that breaks it and stay quiet
on the bundled sample, through the library and the CLI.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from pain001 import check_document
from pain001.cli.cli import cli
from pain001.constants import TEMPLATES_DIR

pytest.importorskip("celpy")

PROFILE = Path(__file__).resolve().parent.parent / "examples/bank-profile"
SAMPLE = TEMPLATES_DIR / "pain.001.001.09" / "pain.001.001.09.xml"
XML = SAMPLE.read_text(encoding="utf-8")


def _rules(xml: str) -> dict[str, str]:
    report = check_document(
        xml,
        policy=(PROFILE / "rules.yaml").read_text(encoding="utf-8"),
        schematron=str(PROFILE / "profile.sch"),
    )
    return {f.rule: f.severity for f in report.findings}


def test_the_sample_passes_with_only_the_weekend_warning() -> None:
    assert set(_rules(XML).values()) == {"warning"}
    assert "EXB-WEEKEND" in _rules(XML)


@pytest.mark.parametrize(
    ("old", "new", "rule"),
    [
        (
            '<InstdAmt Ccy="EUR">150.00</InstdAmt>',
            '<InstdAmt Ccy="EUR">75000.00</InstdAmt>',
            "EXB-LIMIT",
        ),
        (
            '<InstdAmt Ccy="EUR">150.00</InstdAmt>',
            '<InstdAmt Ccy="GBP">150.00</InstdAmt>',
            "EXB-CCY",
        ),
        ("<Nm>John Doe</Nm>", "<Nm>" + "N" * 40 + "</Nm>", "EXB-INITG-NAME"),
    ],
)
def test_each_rule_fires_on_a_document_that_breaks_it(
    old: str, new: str, rule: str
) -> None:
    assert old in XML
    assert _rules(XML.replace(old, new, 1)).get(rule) == "error"


def test_a_payment_block_without_a_service_level_fails() -> None:
    start = XML.index("<PmtTpInf>")
    end = XML.index("</PmtTpInf>") + len("</PmtTpInf>")
    assert _rules(XML[:start] + XML[end:]).get("EXB-SVCLVL") == "error"


def test_the_cli_applies_both_files(tmp_path: Path) -> None:
    bad = tmp_path / "limit.xml"
    bad.write_text(
        XML.replace(
            '<InstdAmt Ccy="EUR">150.00</InstdAmt>',
            '<InstdAmt Ccy="EUR">75000.00</InstdAmt>',
            1,
        ),
        encoding="utf-8",
    )
    args = [
        "--rules",
        str(PROFILE / "rules.yaml"),
        "--schematron",
        str(PROFILE / "profile.sch"),
    ]
    runner = CliRunner()
    assert runner.invoke(cli, ["check", str(SAMPLE), *args]).exit_code == 0
    result = runner.invoke(cli, ["check", str(bad), *args])
    assert result.exit_code == 1
    assert "EXB-LIMIT" in result.output
