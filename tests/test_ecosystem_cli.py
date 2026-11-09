# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The publication job must fail loudly and preserve a readable report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import check_ecosystem as cli
import pytest


@pytest.mark.parametrize("complete", [True, False])
def test_json_and_file_report_keep_failure_exit_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    complete: bool,
) -> None:
    """Machine output is retained even when a publication is incomplete."""
    report = {
        "version": "0.0.82",
        "complete": complete,
        "members": {},
        "problems": [] if complete else ["pain001-fast: missing release"],
    }
    received: list[str | None] = []

    def audit(*, version: str | None) -> dict[str, Any]:
        received.append(version)
        return report

    monkeypatch.setattr(cli, "audit", audit, raising=False)
    output = tmp_path / "report.json"
    code = cli.main(["--version", "0.0.82", "--json", "--output", str(output)])
    assert code == (0 if complete else 1)
    assert json.loads(capsys.readouterr().out) == report
    assert json.loads(output.read_text()) == report
    assert received == ["0.0.82"]


@pytest.mark.parametrize("complete", [True, False])
def test_human_output_states_which_release_is_complete(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    complete: bool,
) -> None:
    """A positive label is never printed for an incomplete release."""
    report = {
        "version": "0.0.82",
        "complete": complete,
        "members": {"pain001": {}},
        "problems": [] if complete else ["website is stale"],
    }
    monkeypatch.setattr(cli, "audit", lambda **kwargs: report, raising=False)
    code = cli.main([])
    text = capsys.readouterr().out
    assert (code == 0) is complete
    assert "0.0.82" in text
    assert ("INCOMPLETE" in text) is not complete
    assert ("website is stale" in text) is not complete
