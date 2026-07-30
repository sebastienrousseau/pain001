# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

from pathlib import Path

from click.testing import CliRunner

from pain001.cli.cli import main as cli_main
from pain001.core.core import process_files


def test_cli_and_library_generate_identical_xml(tmp_path: Path) -> None:
    base = Path("pain001/templates/pain.001.001.03")
    template = str((base / "template.xml").resolve())
    schema = str((base / "pain.001.001.03.xsd").resolve())
    data = str((base / "template.csv").resolve())

    library_dir = tmp_path / "library"
    cli_dir = tmp_path / "cli"
    library_dir.mkdir()
    cli_dir.mkdir()

    process_files(
        "pain.001.001.03",
        template,
        schema,
        data,
        output_path=str(library_dir / "pain.001.001.03.xml"),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "-t",
            "pain.001.001.03",
            "-m",
            template,
            "-s",
            schema,
            "-d",
            data,
            "-o",
            str(cli_dir),
        ],
    )
    assert result.exit_code == 0

    library_xml = (library_dir / "pain.001.001.03.xml").read_text(
        encoding="utf-8"
    )
    cli_xml = (cli_dir / "pain.001.001.03.xml").read_text(encoding="utf-8")
    assert "".join(library_xml.split()) == "".join(cli_xml.split())


def test_cli_dry_run_does_not_generate_output(tmp_path: Path) -> None:
    base = Path("pain001/templates/pain.001.001.03")
    template = str((base / "template.xml").resolve())
    schema = str((base / "pain.001.001.03.xsd").resolve())
    data = str((base / "template.csv").resolve())
    output_dir = tmp_path / "dry-run"
    output_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "-t",
            "pain.001.001.03",
            "-m",
            template,
            "-s",
            schema,
            "-d",
            data,
            "--dry-run",
            "-o",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert list(output_dir.iterdir()) == []
