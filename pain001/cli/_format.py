# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Output formats every command shares: ``--format``, ``--quiet``.

Standard output carries a command's result and nothing else; progress,
the banner, warnings and errors go to standard error. With
``--format json`` the result is one JSON document, so
``pain001 <command> --format json | jq .`` works for every command
that returns a result (``serve`` and ``mcp`` run servers and have
none). The ``--json`` flag that ``versions``, ``inspect`` and
``plugins list`` had was removed in 0.0.89; use ``--format json``.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import click
from rich.console import Console

from pain001.cli._output import print_banner

Command = Callable[..., Any]


class Failure(SystemExit):
    """Exit with ``code`` after printing ``message`` for a human.

    A ``SystemExit`` so callers that expect one keep working; the
    message is kept so ``--format json`` can report it too.

    Args:
        code: Process exit status.
        message: What went wrong, without markup.
    """

    def __init__(self, code: int, message: str) -> None:
        super().__init__(code)
        self.message = message


def emit_json(value: Any, indent: int | None = 2) -> None:
    """Write ``value`` to stdout as one JSON document.

    Args:
        value: Anything ``json.dumps`` accepts; other objects become
            strings.
        indent: Pretty-print indent, or ``None`` for one line.
    """
    click.echo(json.dumps(value, indent=indent, default=str))


def format_option(*choices: str) -> Callable[[Command], Command]:
    """Add ``--format`` (default ``text``) to a command.

    Args:
        *choices: The formats beyond ``text`` and ``json``, if any.

    Returns:
        A decorator, applied below ``@click.command``.
    """
    names = ["text", "json", *choices]

    def decorate(command: Command) -> Command:
        """Attach the option to ``command``."""
        return click.option(
            "--format",
            "output_format",
            type=click.Choice(names),
            default="text",
            show_default=True,
            help="Result format on stdout: " + ", ".join(names) + ".",
        )(command)

    return decorate


#: ``-q/--quiet``: no banner and no progress lines, errors still shown.
quiet_option = click.option(
    "-q",
    "--quiet",
    is_flag=True,
    default=False,
    help="Print no banner or progress on stderr; errors still show.",
)


@dataclass
class Reporter:
    """Where one command run writes for a human: stderr.

    Attributes:
        output_format: ``text`` or ``json``.
        quiet: Whether ``--quiet`` was given.
        console: The stderr console; errors and findings always print.
    """

    output_format: str = "text"
    quiet: bool = False
    console: Console = field(default_factory=lambda: Console(stderr=True))

    @property
    def as_json(self) -> bool:
        """Whether the result goes to stdout as JSON."""
        return self.output_format == "json"

    @property
    def chatter(self) -> Console:
        """A stderr console that prints nothing under ``--quiet``."""
        return Console(stderr=True, quiet=self.quiet)

    def progress(self, *objects: Any, **kwargs: Any) -> None:
        """Print a progress line unless ``--quiet``.

        Args:
            *objects: What to print.
            **kwargs: Passed to :meth:`rich.console.Console.print`.
        """
        if not self.quiet:
            self.console.print(*objects, **kwargs)

    def banner(self) -> None:
        """Print the banner, only for a person at a terminal."""
        if not (self.quiet or self.as_json) and sys.stdout.isatty():
            print_banner(self.console)

    def error(self, text: str, plain: bool = False) -> None:
        """Print an error on stderr, whatever ``--quiet`` says.

        Args:
            text: Rich markup, or plain text when ``plain``.
            plain: Print ``text`` literally, as a red ``✗`` line.
        """
        if plain:
            self.console.print(f"✗ {text}", style="bold red", markup=False)
        else:
            self.console.print(text)
