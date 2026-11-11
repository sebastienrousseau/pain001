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

"""Input files the user names on the command line.

The command line runs as its user, on that user's files: an input file
named there is read wherever it lives. The base-directory jail stays
for the REST API, the MCP server and the dashboard, which take paths
from a request. A missing input is a usage error (exit 2), reported
before anything is printed as progress or any output directory is
created.
"""

from __future__ import annotations

import shlex
import shutil
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from pain001.cli.cli import cli
from pain001.data.loader import load_payment_data
from pain001.security.path_validator import (
    SecurityError,
    trusted_paths,
    validate_path,
)
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

MTYPE = "pain.001.001.09"
BUNDLE = Path(DEFAULT_TEMPLATE_REGISTRY.get_template(MTYPE).template_path)
SAMPLE = BUNDLE.parent / "template.csv"


@pytest.fixture
def dirs(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    """A working directory and a sibling directory holding the input."""
    work = tmp_path / "work"
    elsewhere = tmp_path / "elsewhere"
    work.mkdir()
    elsewhere.mkdir()
    shutil.copyfile(SAMPLE, elsewhere / "payments.csv")
    monkeypatch.chdir(work)
    return work, elsewhere


def _flat(text: str) -> str:
    return text.replace("\n", "")


@pytest.mark.parametrize("command", ["generate", "validate"])
def test_input_outside_working_directory(
    dirs: tuple[Path, Path], command: str
) -> None:
    """A data file outside the working directory is read."""
    work, elsewhere = dirs
    args = [command, "-t", MTYPE, "-d", str(elsewhere / "payments.csv")]
    if command == "generate":
        args += ["-o", "out"]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    if command == "generate":
        assert (work / "out" / f"{MTYPE}.xml").is_file()


def test_relative_input_with_parent_segment(dirs: tuple[Path, Path]) -> None:
    """``../elsewhere/payments.csv`` names the same file and is read."""
    result = CliRunner().invoke(
        cli,
        ["validate", "-t", MTYPE, "-d", "../elsewhere/payments.csv"],
    )
    assert result.exit_code == 0, result.output


def test_streaming_input_outside_working_directory(
    dirs: tuple[Path, Path],
) -> None:
    """Streaming mode reads an outside input as well."""
    work, elsewhere = dirs
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "-t",
            MTYPE,
            "-d",
            str(elsewhere / "payments.csv"),
            "-o",
            "out",
            "--streaming",
        ],
    )
    assert result.exit_code == 0, result.output
    assert list((work / "out").glob("*.xml"))


def test_template_and_schema_outside_working_directory(
    dirs: tuple[Path, Path],
) -> None:
    """A template and schema the user names are read wherever they are."""
    _, elsewhere = dirs
    shutil.copyfile(BUNDLE, elsewhere / "template.xml")
    shutil.copyfile(BUNDLE.parent / f"{MTYPE}.xsd", elsewhere / "s.xsd")
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "-t",
            MTYPE,
            "-d",
            str(elsewhere / "payments.csv"),
            "-m",
            str(elsewhere / "template.xml"),
            "-s",
            str(elsewhere / "s.xsd"),
            "-o",
            "out",
        ],
    )
    assert result.exit_code == 0, result.output


def test_outside_template_with_worker_processes(
    dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spawned workers read an outside template and schema too.

    The session keeps TMPDIR and pytest's base directory under the
    package, an allowed base, so the template goes to a fresh directory
    under ``/tmp``; the temporary-directory base is then moved inside
    the working directory (here, and through ``TMPDIR`` for the spawned
    workers), which leaves the template outside every allowed base.
    """
    work, elsewhere = dirs
    outside = Path(tempfile.mkdtemp(dir="/tmp"))
    try:
        shutil.copyfile(BUNDLE, outside / "template.xml")
        shutil.copyfile(BUNDLE.parent / f"{MTYPE}.xsd", outside / "s.xsd")
        scratch = work / "tmp"
        scratch.mkdir()
        monkeypatch.setenv("TMPDIR", str(scratch))
        monkeypatch.setattr(tempfile, "tempdir", str(scratch))
        monkeypatch.setenv("PAIN001_WORKERS", "1")
        rows = (elsewhere / "payments.csv").read_text().splitlines()
        (elsewhere / "payments.csv").write_text(
            "\n".join([rows[0]] + [rows[1]] * 4) + "\n"
        )
        result = CliRunner().invoke(
            cli,
            [
                "generate",
                "-t",
                MTYPE,
                "-d",
                str(elsewhere / "payments.csv"),
                "-m",
                str(outside / "template.xml"),
                "-s",
                str(outside / "s.xsd"),
                "-o",
                "out",
                "--streaming",
                "--chunk-size",
                "2",
                "--workers",
                "2",
            ],
        )
    finally:
        shutil.rmtree(outside)
    assert result.exit_code == 0, result.output
    assert len(list((work / "out").glob("*.chunk*.xml"))) == 2


@pytest.mark.parametrize("command", ["generate", "validate"])
def test_missing_input_is_a_usage_error(
    dirs: tuple[Path, Path], command: str
) -> None:
    """A missing input exits 2 before progress or an output directory."""
    work, _ = dirs
    args = [command, "-t", MTYPE, "-d", "nope.csv"]
    if command == "generate":
        args += ["-o", "newdir"]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 2, result.output
    assert "Input file not found: nope.csv" in _flat(result.output)
    assert "→" not in result.output
    assert "Output directory" not in result.output
    assert not (work / "newdir").exists()


@pytest.mark.parametrize("flag", ["-m", "-s"])
def test_missing_template_or_schema_is_a_usage_error(
    dirs: tuple[Path, Path], flag: str
) -> None:
    """A template or schema that does not exist exits 2 as well."""
    _, elsewhere = dirs
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "-t",
            MTYPE,
            "-d",
            str(elsewhere / "payments.csv"),
            flag,
            "missing.file",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "Input file not found: missing.file" in _flat(result.output)


def test_library_keeps_the_jail(dirs: tuple[Path, Path]) -> None:
    """Outside the CLI, a path outside the working directory is refused."""
    _, elsewhere = dirs
    with pytest.raises(FileNotFoundError, match="escapes base directory"):
        load_payment_data(str(elsewhere / "payments.csv"))


def test_trust_is_exact_and_scoped(dirs: tuple[Path, Path]) -> None:
    """Only the named file passes, and only inside the ``with`` block."""
    work, elsewhere = dirs
    named = elsewhere / "payments.csv"
    other = elsewhere / "other.csv"
    shutil.copyfile(named, other)
    with trusted_paths(str(named)):
        assert validate_path(str(named), base_dir=work) == str(named.resolve())
        with pytest.raises(SecurityError):
            validate_path(str(other), base_dir=work)
    with pytest.raises(SecurityError):
        validate_path(str(named), base_dir=work)


def test_init_hint_runs_from_any_directory(
    dirs: tuple[Path, Path], monkeypatch
) -> None:
    """The command ``init`` prints works after a change of directory."""
    work, elsewhere = dirs
    runner = CliRunner()
    result = runner.invoke(
        cli, ["init", MTYPE, "-o", "starter file.csv"], terminal_width=40
    )
    assert result.exit_code == 0, result.output
    hint = result.output.split("then run:", 1)[1].strip()
    assert "\n" not in hint
    assert f"'{work.resolve() / 'starter file.csv'}'" in hint
    monkeypatch.chdir(elsewhere)
    args = hint.split(" ", 1)[1]
    rerun = runner.invoke(cli, ["validate", *shlex.split(args)[1:]])
    assert rerun.exit_code == 0, rerun.output


def test_bad_environment_value_names_the_variable(
    dirs: tuple[Path, Path], monkeypatch
) -> None:
    """A malformed environment value names its variable, exit 2."""
    _, elsewhere = dirs
    monkeypatch.setenv("PAIN001_CHUNK_SIZE", "abc")
    result = CliRunner().invoke(
        cli, ["generate", "-t", MTYPE, "-d", str(elsewhere / "payments.csv")]
    )
    assert result.exit_code == 2, result.output
    assert "PAIN001_CHUNK_SIZE" in result.output


def test_unknown_message_type_from_config(
    dirs: tuple[Path, Path], tmp_path: Path
) -> None:
    """A configuration file naming an unknown type exits 2, no traceback."""
    _, elsewhere = dirs
    config = tmp_path / "c.yaml"
    config.write_text("xml_message_type: pain.999\n", encoding="utf-8")
    result = CliRunner().invoke(
        cli,
        ["generate", "-c", str(config), "-d", str(elsewhere / "payments.csv")],
    )
    assert result.exit_code == 2, result.output
    assert "Invalid XML message type: pain.999" in result.output
