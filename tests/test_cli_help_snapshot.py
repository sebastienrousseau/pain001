# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Every ``--help`` page is pinned, and every example in one runs.

``tests/data/cli-help.txt`` holds the help of every command at 80
columns, so a change to what a user reads shows up in review. After an
intended change, regenerate it with::

    PAIN001_UPDATE_HELP=1 pytest tests/test_cli_help_snapshot.py

The examples are run as printed, in an empty directory holding only
the bundled sample data, so none can drift into a command that fails.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shlex
import shutil
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from pain001.cli.cli import cli
from pain001.constants import TEMPLATES_DIR

SNAPSHOT = Path(__file__).parent / "data" / "cli-help.txt"
SAMPLE = "pain.001.001.09"
_EXAMPLES = re.compile(r"^ *Examples:\n((?: {3,}.*\n)+)", re.MULTILINE)


def _paths(
    group: click.Group, prefix: tuple[str, ...] = ()
) -> list[tuple[str, ...]]:
    """The group and every command under it, as paths of names."""
    paths = [prefix]
    for name in sorted(group.commands):
        command = group.commands[name]
        if isinstance(command, click.Group):
            paths.extend(_paths(command, (*prefix, name)))
        else:
            paths.append((*prefix, name))
    return paths


def _help(path: tuple[str, ...]) -> str:
    """``pain001 <path> --help`` as a user at an 80-column terminal sees it."""
    result = CliRunner().invoke(
        cli, [*path, "--help"], prog_name="pain001", terminal_width=80
    )
    assert result.exit_code == 0, result.output
    return result.output


def render_help() -> str:
    """Every help page, each under a ``$ pain001 ... --help`` heading."""
    return "".join(
        f"$ {' '.join(('pain001', *path, '--help'))}\n{_help(path)}\n"
        for path in _paths(cli)
    )


def test_help_matches_the_snapshot() -> None:
    """The help text changes only together with the snapshot."""
    rendered = render_help()
    if os.environ.get("PAIN001_UPDATE_HELP") == "1":
        SNAPSHOT.write_text(rendered, encoding="utf-8")
    assert rendered == SNAPSHOT.read_text(encoding="utf-8")


def _examples() -> list[str]:
    """Every ``pain001 ...`` line under an ``Examples:`` heading."""
    lines = []
    for path in _paths(cli):
        for block in _EXAMPLES.findall(_help(path)):
            lines.extend(
                line.strip()
                for line in block.splitlines()
                if line.strip().startswith("pain001 ")
            )
    return lines


@pytest.fixture
def sample_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty directory with the files the examples name."""
    monkeypatch.chdir(tmp_path)
    bundle = TEMPLATES_DIR / SAMPLE
    shutil.copyfile(bundle / "template.csv", "payments.csv")
    shutil.copyfile(bundle / "template.xml", "template.xml")
    shutil.copyfile(bundle / f"{SAMPLE}.xsd", "schema.xsd")
    with open("payments.csv", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    Path("payments.json").write_text(json.dumps(rows), encoding="utf-8")
    return tmp_path


def test_there_are_examples() -> None:
    """The parser finds the examples, so the next test is not vacuous."""
    assert len(_examples()) >= 5


@pytest.mark.parametrize("example", _examples())
def test_every_help_example_runs(sample_dir: Path, example: str) -> None:
    """Each example exits 0 with the bundled sample data."""
    args = shlex.split(example)[1:]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, f"{example}\n{result.output}"
