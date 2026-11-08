# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""``pain001 check``: exit status, formats and refusals."""

from __future__ import annotations

import builtins
import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from pain001 import check
from pain001.cli.cli import cli

COVERAGE = Path(check.__file__).parent / "corpus" / "data" / "coverage"
GOOD = COVERAGE / "pain.001.001.09" / "01-transfer-every-element.xml"
GOOD_008 = COVERAGE / "pain.008.001.08" / "01-collection-every-element.xml"


def _run(*args: str) -> Any:
    return CliRunner().invoke(cli, ["check", *args])


def _bad(tmp_path: Path) -> Path:
    path = tmp_path / "bad.xml"
    path.write_text(
        GOOD.read_text(encoding="utf-8").replace(
            "<NbOfTxs>", "<Foo>x</Foo><NbOfTxs>", 1
        ),
        encoding="utf-8",
    )
    return path


def test_valid_files_exit_zero() -> None:
    result = _run(str(GOOD), str(GOOD_008))
    assert result.exit_code == 0, result.output
    assert "pain.001.001.09 passed (xsd, mdr)" in result.output
    assert "pain.008.001.08 passed (xsd, mdr)" in result.output


def test_one_failing_file_exits_one_and_reports_every_file(
    tmp_path: Path,
) -> None:
    result = _run(str(GOOD), str(_bad(tmp_path)))
    assert result.exit_code == 1
    assert "pain.001.001.09 passed" in result.output
    assert "error [xsd] xsd at /Document/CstmrCdtTrfInitn/GrpHdr" in (
        result.output
    )


def test_scheme_findings_fail_the_check() -> None:
    result = _run("--scheme", "sepa-sct", str(GOOD))
    assert result.exit_code == 1
    assert "SEPA-CHRGBR" in result.output


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--scheme", "no-such-scheme"], "no-such-scheme"),
        (["--schematron", "no-such-rulebook"], "no-such-rulebook"),
    ],
)
def test_an_unknown_scheme_or_rulebook_exits_two(
    args: list[str], message: str
) -> None:
    result = _run(*args, str(GOOD))
    assert result.exit_code == 2
    assert message in result.output


def test_a_file_that_is_not_a_payment_exits_two(tmp_path: Path) -> None:
    path = tmp_path / "notes.xml"
    path.write_text("<notes/>", encoding="utf-8")
    result = _run(str(path))
    assert result.exit_code == 2
    assert "not a pain.001 or pain.008 Document" in result.output


def test_a_file_that_is_not_utf8_exits_two(tmp_path: Path) -> None:
    path = tmp_path / "latin1.xml"
    path.write_bytes(b"<Document>\xe9</Document>")
    assert _run(str(path)).exit_code == 2


def test_no_file_is_a_usage_error() -> None:
    assert _run().exit_code == 2


def test_json_lists_each_file() -> None:
    result = _run("--format", "json", str(GOOD), str(GOOD_008))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert [entry["file"] for entry in data] == [str(GOOD), str(GOOD_008)]
    assert all(entry["passed"] for entry in data)


def test_sarif_goes_to_the_output_file(tmp_path: Path) -> None:
    out = tmp_path / "check.sarif"
    result = _run("--format", "sarif", "-o", str(out), str(_bad(tmp_path)))
    assert result.exit_code == 1
    assert f"Wrote sarif report to {out}" in result.output
    log = json.loads(out.read_text(encoding="utf-8"))
    assert log["version"] == "2.1.0"
    assert log["runs"][0]["results"][0]["ruleId"] == "xsd/xsd"


def test_rules_feed_the_policy_to_every_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("pain001.validation.policy")
    policy = tmp_path / "policy.yaml"
    policy.write_text("rules: []\n", encoding="utf-8")
    seen: list[str | None] = []

    def fake(xml: bytes, **kwargs: Any) -> check.CheckReport:
        seen.append(kwargs["policy"])
        return check.CheckReport("pain.001.001.09", ("xsd", "mdr", "scheme"))

    monkeypatch.setattr("pain001.cli._check.check_document", fake)
    result = _run("--rules", str(policy), str(GOOD), str(GOOD_008))
    assert result.exit_code == 0, result.output
    assert seen == ["rules: []\n", "rules: []\n"]


def test_rules_without_the_extra_exits_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = tmp_path / "policy.yaml"
    policy.write_text("rules: []\n", encoding="utf-8")
    real_import = builtins.__import__

    def no_policy(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "pain001.validation.policy":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_policy)
    result = _run("--rules", str(policy), str(GOOD))
    assert result.exit_code == 2
    assert "pain001[rules]" in result.output


def test_check_is_listed_in_the_cli_help() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert "check" in result.output


def test_skip_other_xml_skips_only_non_payment_xml(tmp_path: Path) -> None:
    other = tmp_path / "pom.xml"
    other.write_text("<project/>", encoding="utf-8")
    result = _run(
        "--skip-other-xml", "--format", "json", str(other), str(GOOD)
    )
    assert result.exit_code == 0, result.output
    assert f"skipped {other}: not a pain.001 or pain.008 Document" in (
        result.output
    )
    data = json.loads(result.output[result.output.index("[") :])
    assert [entry["file"] for entry in data] == [str(GOOD)]


@pytest.mark.parametrize(
    "content",
    ["<project", '<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>'],
    ids=["malformed", "dtd"],
)
def test_skip_other_xml_still_refuses_broken_xml(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "broken.xml"
    path.write_text(content, encoding="utf-8")
    assert _run("--skip-other-xml", str(path)).exit_code == 2


def test_skipping_every_file_passes(tmp_path: Path) -> None:
    other = tmp_path / "pom.xml"
    other.write_text("<project/>", encoding="utf-8")
    result = _run("--skip-other-xml", "--format", "sarif", str(other))
    assert result.exit_code == 0
