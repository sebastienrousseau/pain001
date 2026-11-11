# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Path handling shared by the CLI commands."""

import os

import click
from rich.console import Console

from pain001.cli._output import esc
from pain001.constants import valid_xml_types
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY


def _resolve_template_assets(
    xml_message_type: str,
    xml_template_file_path: str | None,
    xsd_schema_file_path: str | None,
) -> tuple[str, str]:
    """Resolve template/schema from registry when paths are omitted."""
    if xml_template_file_path and xsd_schema_file_path:
        return xml_template_file_path, xsd_schema_file_path
    template_path, schema_path = DEFAULT_TEMPLATE_REGISTRY.resolve_paths(
        xml_message_type
    )
    return (
        xml_template_file_path or template_path,
        xsd_schema_file_path or schema_path,
    )


def _file_not_directory(
    ctx: click.Context, param: click.Parameter, value: str | None
) -> str | None:
    """Refuse a path ending in a separator: it names a directory.

    Click's ``dir_okay=False`` only catches directories that exist, so
    ``-o work/`` used to write a file named ``work``.

    Args:
        ctx: The Click context (unused).
        param: The option being checked (unused).
        value: The path given, if any.

    Returns:
        The path unchanged.

    Raises:
        click.BadParameter: If the path ends with a path separator.
    """
    if value is not None and value.endswith(("/", os.sep)):
        raise click.BadParameter(
            f"{value!r} is a directory path; give a file name, "
            "for example -o payments.csv."
        )
    return value


def _require_inputs(console: Console, paths: tuple[str, ...]) -> None:
    """Exit 2 unless every input file exists, before any progress.

    Args:
        console: The console the command writes to.
        paths: The data, template and schema paths.

    Raises:
        SystemExit: 2 when one is missing or is not a file.
    """
    for path in paths:
        if not os.path.isfile(path):
            console.print(
                f"[bold red]✗ Error:[/bold red] Input file not found: "
                f"{esc(path)}"
            )
            raise SystemExit(2)


def _require_message_type(console: Console, message_type: str) -> None:
    """Exit 2 unless ``message_type`` is one this build generates.

    Click checks ``-t``; a configuration file or profile is not checked
    by Click, and an unknown type there ended in a traceback.

    Args:
        console: The console the command writes to.
        message_type: The resolved message type.

    Raises:
        SystemExit: 2 when the type is unknown.
    """
    if message_type not in valid_xml_types:
        console.print(
            f"[bold red]✗ Error:[/bold red] Invalid XML message type: "
            f"{esc(message_type)}\n"
            f"[cyan]Valid types:[/cyan] {', '.join(valid_xml_types)}"
        )
        raise SystemExit(2)
