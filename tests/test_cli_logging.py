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

"""The command line shows the library's log records.

Until 0.0.86 ``--verbose`` set a level on the ``pain001`` logger but no
handler was attached (the package installs a ``NullHandler``), so every
library record was dropped; ``PAIN001_LOG_LEVEL`` and
``PAIN001_LOG_FILE`` were read only by ``configure_json_logging()``,
which no entry point called. ``generate`` and ``validate`` now attach a
stderr handler for the run: plain text by default, JSON with
``--log-format json`` or ``PAIN001_LOG_FORMAT=json``.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from pain001.cli.cli import cli
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

MTYPE = "pain.001.001.09"
SAMPLE = (
    Path(DEFAULT_TEMPLATE_REGISTRY.get_template(MTYPE).template_path).parent
    / "template.csv"
)
PKG = logging.getLogger("pain001")


@pytest.fixture
def workdir(monkeypatch, tmp_path: Path) -> Path:
    """An empty working directory holding one valid input."""
    monkeypatch.chdir(tmp_path)
    for name in (
        "PAIN001_LOG_LEVEL",
        "PAIN001_LOG_FILE",
        "PAIN001_LOG_FORMAT",
    ):
        monkeypatch.delenv(name, raising=False)
    shutil.copyfile(SAMPLE, tmp_path / "payments.csv")
    return tmp_path


def _run(*args: str) -> object:
    return CliRunner().invoke(
        cli, ["validate", "-t", MTYPE, "-d", "payments.csv", *args]
    )


def test_verbose_shows_library_records(workdir: Path) -> None:
    """``-v`` prints DEBUG and INFO records to stderr."""
    result = _run("-v")
    assert result.exit_code == 0, result.output
    assert "INFO pain001" in result.stderr
    assert "cli_args_parsed" in result.stderr


def test_default_is_quiet(workdir: Path) -> None:
    """Without -v only warnings and errors are shown."""
    result = _run()
    assert result.exit_code == 0, result.output
    assert "INFO pain001" not in result.stderr


def test_env_level(workdir: Path, monkeypatch) -> None:
    """``PAIN001_LOG_LEVEL`` sets the level without -v."""
    monkeypatch.setenv("PAIN001_LOG_LEVEL", "info")
    result = _run()
    assert "INFO pain001" in result.stderr


def test_bad_env_level(workdir: Path, monkeypatch) -> None:
    """A bad level is a usage error naming the variable."""
    monkeypatch.setenv("PAIN001_LOG_LEVEL", "LOUD")
    result = _run()
    assert result.exit_code == 2
    assert "PAIN001_LOG_LEVEL" in result.output


def test_json_format_flag(workdir: Path) -> None:
    """``--log-format json`` writes one JSON object per record."""
    result = _run("-v", "--log-format", "json")
    records = [json.loads(line) for line in result.stderr.splitlines()]
    assert any(r.get("event") == "cli_args_parsed" for r in records)


def test_json_format_env(workdir: Path, monkeypatch) -> None:
    """``PAIN001_LOG_FORMAT=json`` does the same."""
    monkeypatch.setenv("PAIN001_LOG_FORMAT", "json")
    result = _run("-v")
    assert json.loads(result.stderr.splitlines()[0])


def test_bad_env_format(workdir: Path, monkeypatch) -> None:
    """A bad format is a usage error naming the variable."""
    monkeypatch.setenv("PAIN001_LOG_FORMAT", "xml")
    result = _run()
    assert result.exit_code == 2
    assert "PAIN001_LOG_FORMAT" in result.output


def test_log_file(workdir: Path, monkeypatch) -> None:
    """``PAIN001_LOG_FILE`` also writes the records to that file."""
    monkeypatch.setenv("PAIN001_LOG_FILE", str(workdir / "logs" / "run.log"))
    result = _run("-v")
    assert result.exit_code == 0, result.output
    assert "cli_args_parsed" in (workdir / "logs" / "run.log").read_text()


def test_handlers_are_removed_after_the_run(
    workdir: Path, monkeypatch
) -> None:
    """The run leaves the package logger as it found it."""
    monkeypatch.setenv("PAIN001_LOG_FILE", str(workdir / "run.log"))
    before = list(PKG.handlers)
    level = PKG.level
    _run("-v")
    _run("-v")
    assert PKG.handlers == before
    assert PKG.level == level


def test_no_row_values_in_logs(workdir: Path) -> None:
    """A failing row is logged by line and column, never by value."""
    text = (workdir / "payments.csv").read_text(encoding="utf-8")
    (workdir / "payments.csv").write_text(
        text.replace("150.00", "SECRET-AMOUNT", 1), encoding="utf-8"
    )
    result = _run("-v")
    assert result.exit_code == 1
    assert "SECRET-AMOUNT" not in result.stderr
    assert "SECRET-AMOUNT" not in result.output
