# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""A mistyped command names the command it was probably meant to be."""

from click.testing import CliRunner

from pain001.cli.cli import cli


def test_a_mistyped_command_gets_a_suggestion() -> None:
    """``genrate`` used to reach ``generate`` as an unexpected argument."""
    result = CliRunner().invoke(cli, ["genrate", "-t", "pain.001.001.03"])
    assert result.exit_code == 2
    assert "No such command 'genrate'" in result.output
    assert "Did you mean 'generate'?" in result.output


def test_a_mistyped_subcommand_gets_a_suggestion() -> None:
    """``plugins lst`` names ``list``."""
    result = CliRunner().invoke(cli, ["plugins", "lst"])
    assert result.exit_code == 2
    assert "Did you mean 'list'?" in result.output


def test_an_unknown_word_gets_no_guess() -> None:
    """Nothing close: the error names the command and points at --help."""
    result = CliRunner().invoke(cli, ["zzzz"])
    assert result.exit_code == 2
    assert "No such command 'zzzz'" in result.output
    assert "Did you mean" not in result.output


def test_options_alone_still_run_generate() -> None:
    """The bare ``pain001 -t ... -d ...`` form keeps routing to generate."""
    result = CliRunner().invoke(cli, ["--list-templates"])
    assert result.exit_code == 0, result.output
    assert "pain.001.001.03" in result.output
