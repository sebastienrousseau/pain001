# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Keep docstring sections out of every command's ``--help`` text."""

import re

import click
import pytest
from click.testing import CliRunner

from pain001.cli.cli import cli

_SECTION = re.compile(r"^\s*(Args|Raises|Returns|Yields):", re.MULTILINE)


def _command_paths() -> list[tuple[str, ...]]:
    """Return every command and subcommand as its path of names."""
    paths: list[tuple[str, ...]] = [()]
    for name, command in cli.commands.items():
        paths.append((name,))
        if isinstance(command, click.Group):
            paths.extend((name, sub) for sub in command.commands)
    return paths


@pytest.mark.parametrize("path", _command_paths(), ids=" ".join)
def test_help_shows_no_docstring_sections(path: tuple[str, ...]) -> None:
    """Google-style sections stay in the code, not the user's terminal.

    Click prints a command's whole docstring unless a form feed marks
    where the help ends; nine commands printed their Args/Raises.
    """
    result = CliRunner().invoke(cli, [*path, "--help"])
    assert result.exit_code == 0, result.output
    assert not _SECTION.search(result.output), result.output
