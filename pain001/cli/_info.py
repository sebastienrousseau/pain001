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

"""``versions``, ``inspect`` and ``init``: what this build ships.

Results go to stdout (a table, or JSON with ``--format json``);
errors go to stderr.
"""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path
from typing import Any

import click
from rich import box
from rich.console import Console
from rich.table import Table

from pain001.cli._format import (
    Failure,
    Reporter,
    emit_json,
    format_option,
    quiet_option,
)
from pain001.cli._output import (
    esc,
    print_template_details,
    print_template_list,
)
from pain001.cli._paths import _file_not_directory
from pain001.constants import valid_xml_types
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY


def _out() -> Console:
    """A console on stdout, for a text result."""
    return Console()


def template_dict(message_type: str) -> dict[str, Any]:
    """The JSON form of one bundled template's metadata.

    Args:
        message_type: A bundled message type.

    Returns:
        Its type, category, template, schema, input formats and
        whether it is deprecated.
    """
    metadata = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    return {
        "message_type": metadata.message_type,
        "category": metadata.message_category,
        "template": str(metadata.template_path),
        "schema": str(metadata.xsd_path),
        "input_formats": list(metadata.supported_input_formats),
        "deprecated": metadata.deprecated,
    }


def show_template_list(output_format: str) -> None:
    """Print every bundled template (``generate --list-templates``).

    Args:
        output_format: ``text`` or ``json``.
    """
    if output_format == "json":
        emit_json(
            [
                template_dict(metadata.message_type)
                for metadata in DEFAULT_TEMPLATE_REGISTRY.list_templates()
            ]
        )
        return
    print_template_list(_out())


def _require_known(message_type: str) -> None:
    """Exit 2 on stderr unless ``message_type`` is bundled.

    Args:
        message_type: The type the user named.

    Raises:
        Failure: 2 for an unknown type.
    """
    if message_type not in valid_xml_types:
        Reporter().error(
            f"[bold red]✗ Error:[/bold red] Unknown message type: "
            f"[yellow]{esc(message_type)}[/yellow]",
        )
        raise Failure(2, f"Unknown message type: {message_type}")


def show_template_metadata(message_type: str, output_format: str) -> None:
    """Print one template's metadata (``inspect``, ``--show-template``).

    Args:
        message_type: A bundled message type.
        output_format: ``text`` or ``json``.
    """
    _require_known(message_type)
    if output_format == "json":
        emit_json(template_dict(message_type))
        return
    print_template_details(_out(), message_type)


@click.command("versions")
@format_option(legacy_json=True)
def versions_cmd(output_format: str) -> None:
    """List the ISO 20022 message types this build can generate.
    \f
    Args:
        output_format: ``text`` for a table, ``json`` for an array.
    """
    if output_format == "json":
        emit_json(list(valid_xml_types))
        return
    table = Table(box=box.SIMPLE_HEAVY, title="Supported message types")
    table.add_column("Message Type")
    for message_type in valid_xml_types:
        table.add_row(message_type)
    _out().print(table)


@click.command("inspect")
@click.argument("message_type")
@format_option(legacy_json=True)
def inspect_cmd(message_type: str, output_format: str) -> None:
    """Show the bundled template, schema, and accepted formats for a type.
    \f
    Args:
        message_type: ISO 20022 message type to inspect.
        output_format: ``text`` or ``json``.
    """
    show_template_metadata(message_type, output_format)


@click.command("init")
@click.argument("message_type")
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(dir_okay=False, writable=True),
    callback=_file_not_directory,
    default=None,
    help="Where to write the starter CSV (default: ./<message_type>.csv).",
)
@format_option()
@quiet_option
def init_cmd(
    message_type: str, output_path: str | None, output_format: str, quiet: bool
) -> None:
    """Scaffold a starter CSV for a message type from its bundled example.
    \f
    Args:
        message_type: ISO 20022 message type to scaffold data for.
        output_path: Optional destination path for the starter CSV.
        output_format: ``text`` or ``json``.
        quiet: Print nothing on success in text mode.

    Raises:
        Failure: 2 for an unknown message type.
    """
    _require_known(message_type)
    metadata = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    source = Path(metadata.template_path).parent / "template.csv"
    if not source.is_file():  # pragma: no cover - bundled assets always ship
        Reporter().error(
            f"No starter CSV bundled for {message_type}.", plain=True
        )
        raise Failure(1, f"No starter CSV bundled for {message_type}.")
    destination = Path(output_path or f"{message_type}.csv")
    shutil.copyfile(source, destination)
    # An absolute, quoted path, on one unwrapped line: the command runs
    # as printed from any directory.
    command = (
        f"pain001 generate -t {message_type} "
        f"-d {shlex.quote(str(destination.resolve()))}"
    )
    if output_format == "json":
        emit_json({"written": str(destination), "next": command})
        return
    rep = Reporter(quiet=quiet)
    rep.progress(
        f"[bold green]✓ Wrote starter CSV:[/bold green] {esc(destination)}"
    )
    rep.progress(
        f"[dim]Edit it, then run:[/dim] {esc(command)}", soft_wrap=True
    )
