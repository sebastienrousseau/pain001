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

"""Show the library's log records while ``generate`` or ``validate`` runs.

The package installs a ``NullHandler``, as a library should, so nothing
is shown until a handler is attached. The command line attaches one to
stderr for the length of the run (and a file handler when
``PAIN001_LOG_FILE`` is set) and removes them when the command ends, so
a program that calls the CLI in-process keeps its own logging.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import click
from rich.console import Console

from pain001.context.context import Context
from pain001.logging_schema.formatter import JSONFormatter

#: Level names ``PAIN001_LOG_LEVEL`` accepts, in either case.
LEVELS = ("debug", "info", "warning", "error", "critical")
#: Formats ``--log-format`` and ``PAIN001_LOG_FORMAT`` accept.
FORMATS = ("text", "json")

_TEXT = "%(levelname)s %(name)s: %(message)s"


class _StderrHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Write to whatever ``sys.stderr`` is when a record is emitted.

    A handler bound to the stream at creation keeps writing to a stream
    that a test runner (or a caller) has since replaced and closed.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Emit ``record`` to the current ``sys.stderr``.

        Args:
            record: The record to write.
        """
        self.stream = sys.stderr
        super().emit(record)


def _env_choice(name: str, choices: tuple[str, ...], default: str) -> str:
    """Return the lower-cased value of ``name``, or ``default`` if unset.

    Args:
        name: The environment variable.
        choices: The values it may take.
        default: The value when it is unset or empty.

    Returns:
        One of ``choices``.

    Raises:
        click.UsageError: Naming the variable, for any other value.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    if value.lower() not in choices:
        raise click.UsageError(
            f"Environment variable {name}={value!r} is not valid; use one "
            f"of: {', '.join(choices)}."
        )
    return value.lower()


def resolve_log_format(log_format: str | None) -> str:
    """The log format: ``--log-format``, else ``PAIN001_LOG_FORMAT``, else text.

    Args:
        log_format: The ``--log-format`` value, if given.

    Returns:
        ``"text"`` or ``"json"``.

    A ``click.UsageError`` naming the variable propagates when the
    environment value is not valid.
    """
    return log_format or _env_choice("PAIN001_LOG_FORMAT", FORMATS, "text")


def _handlers(level: int, log_format: str) -> list[logging.Handler]:
    """Build the stderr handler, and a file handler if one is asked for.

    Args:
        level: The lowest level the handlers write.
        log_format: ``"text"`` or ``"json"``.

    Returns:
        The configured handlers.
    """
    handlers: list[logging.Handler] = [_StderrHandler()]
    log_file = os.environ.get("PAIN001_LOG_FILE", "").strip()
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    formatter = (
        JSONFormatter() if log_format == "json" else logging.Formatter(_TEXT)
    )
    for handler in handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)
    return handlers


def attach_cli_logging(
    logger: logging.Logger, verbose: bool, log_format: str | None
) -> None:
    """Show ``logger``'s records on stderr until the command ends.

    The level is DEBUG with ``--verbose``, else ``PAIN001_LOG_LEVEL``,
    else WARNING. The format is ``--log-format``, else
    ``PAIN001_LOG_FORMAT``, else plain text; JSON uses the package's
    :class:`~pain001.logging_schema.formatter.JSONFormatter`.
    ``PAIN001_LOG_FILE`` adds a file with the same records. Library
    records never carry a payment row's values.

    Args:
        logger: The package logger.
        verbose: Whether ``--verbose`` was given.
        log_format: The ``--log-format`` value, if given.

    A ``click.UsageError`` naming the variable propagates when an
    environment value is not valid.
    """
    name = "debug" if verbose else None
    name = name or _env_choice("PAIN001_LOG_LEVEL", LEVELS, "warning")
    log_format = resolve_log_format(log_format)
    level = getattr(logging, name.upper())
    handlers = _handlers(level, log_format)
    previous = logger.level
    for handler in handlers:
        logger.addHandler(handler)
    logger.setLevel(min(level, logging.INFO))

    def _detach() -> None:
        """Remove the handlers and restore the level, when the run ends."""
        for handler in handlers:
            logger.removeHandler(handler)
            handler.close()
        logger.setLevel(previous)

    click.get_current_context().call_on_close(_detach)


#: The ``--log-format`` option ``generate`` and ``validate`` share.
log_format_option = click.option(
    "--log-format",
    type=click.Choice(FORMATS),
    default=None,
    help="Log record format on stderr: text or json (PAIN001_LOG_FORMAT).",
)


def configure_logging(
    console: Console, verbose: bool, log_format: str | None = None
) -> logging.Logger:
    """Show the library's log records on stderr for this run.

    Args:
        console: The console the command writes to.
        verbose: If True, show DEBUG records and up; otherwise the
            level ``PAIN001_LOG_LEVEL`` names, or WARNING.
        log_format: ``"text"`` or ``"json"``; ``PAIN001_LOG_FORMAT``
            or text when omitted.

    Returns:
        The package logger.
    """
    logger = Context.get_instance().get_logger()
    attach_cli_logging(logger, verbose, log_format)
    if verbose:
        console.print("[bold cyan]ℹ Verbose logging enabled[/bold cyan]")
    return logger
