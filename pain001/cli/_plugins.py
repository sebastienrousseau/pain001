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

"""``pain001 plugins``: inspect the plugin substrate."""

from __future__ import annotations

import re
from typing import Any

import click
from rich import box
from rich.console import Console
from rich.table import Table

from pain001.cli._format import Failure, Reporter, emit_json, format_option
from pain001.cli._output import esc

_KINDS = click.Choice(["loader", "validator", "scheme", "writer"])
_DISABLE_VAR = "PAIN001_DISABLE_PLUGINS"
_DISABLE_EXAMPLES = (
    f"{_DISABLE_VAR}=parquet pain001 plugins list",
    f"{_DISABLE_VAR}='parquet,sqlite' pain001 plugins list",
)


def _plugin_dict(info: Any) -> dict[str, Any]:
    """The JSON form of one registered plugin.

    Args:
        info: A registry ``PluginInfo``.

    Returns:
        Its kind, name, version, API version, description and source.
    """
    return {
        "kind": info.kind,
        "name": info.meta.name,
        "version": info.meta.version,
        "api_version": list(info.meta.api_version),
        "description": info.meta.description,
        "source": info.meta.source,
    }


def _plugins(kind: str | None) -> list[Any]:
    """Every registered plugin, optionally of one kind.

    Args:
        kind: ``loader``, ``validator``, ``scheme``, ``writer`` or None.

    Returns:
        The registry's ``PluginInfo`` records.
    """
    from pain001.plugins.registry import registry  # noqa: PLC0415

    return list(registry.list_plugins(kind=kind))


@click.group("plugins")
def plugins_group() -> None:
    """Inspect the plugin substrate (loaders, validators, schemes, writers)."""


@plugins_group.command("list")
@click.option(
    "--kind", type=_KINDS, default=None, help="Filter to one plugin kind."
)
@format_option(legacy_json=True)
def plugins_list_cmd(kind: str | None, output_format: str) -> None:
    """List every registered plugin (built-in + entry-point discovered).
    \f
    Args:
        kind: Optional kind filter (loader / validator / scheme / writer).
        output_format: ``text`` for a table, ``json`` for an array.
    """
    infos = _plugins(kind)
    if output_format == "json":
        emit_json([_plugin_dict(info) for info in infos])
        return
    table = Table(box=box.SIMPLE_HEAVY, title="Registered plugins")
    for column in ("Kind", "Name", "Source", "Description"):
        table.add_column(column)
    for info in infos:
        table.add_row(
            info.kind,
            esc(info.meta.name),
            esc(info.meta.source),
            esc(info.meta.description),
        )
    Console().print(table)


def _show_text(info: Any) -> None:
    """Print one plugin's metadata as text on stdout.

    Args:
        info: A registry ``PluginInfo``.
    """
    meta = info.meta
    Console().print(
        f"[bold cyan]{info.kind}[/bold cyan] "
        f"[bold]{esc(meta.name)}[/bold] "
        f"[dim]v{esc(meta.version)}[/dim]\n"
        f"  source:      {esc(meta.source)}\n"
        f"  api version: {meta.api_version[0]}.{meta.api_version[1]}\n"
        f"  description: {esc(meta.description)}"
    )


@plugins_group.command("show")
@click.argument("name")
@click.option(
    "--kind",
    type=_KINDS,
    default=None,
    help="Narrow the search to one kind when the same name exists across kinds.",
)
@format_option()
def plugins_show_cmd(name: str, kind: str | None, output_format: str) -> None:
    """Print the metadata for a single plugin by name.
    \f
    Args:
        name: Plugin's declared name (e.g. ``csv``, ``sepa-sct``).
        kind: Optional kind filter to disambiguate.
        output_format: ``text`` or ``json`` (an array of matches).

    Raises:
        Failure: 1 when no plugin has that name.
    """
    matches = [info for info in _plugins(kind) if info.meta.name == name]
    if not matches:
        of_kind = f" of kind {kind}" if kind else ""
        Reporter().error(
            f"[bold red]✗ Error:[/bold red] No plugin named "
            f"[yellow]{esc(name)}[/yellow]"
            + (f" of kind [yellow]{kind}[/yellow]" if kind else "")
            + ".",
        )
        raise Failure(1, f"No plugin named {name}{of_kind}.")
    if output_format == "json":
        emit_json([_plugin_dict(info) for info in matches])
        return
    for info in matches:
        _show_text(info)


@plugins_group.command("disable")
@click.argument("name", required=False)
@format_option()
def plugins_disable_cmd(name: str | None, output_format: str) -> None:
    """Show how to disable plugins via ``PAIN001_DISABLE_PLUGINS``.

    Documentation-only command: the environment variable is the
    canonical disable mechanism because it persists for the lifetime
    of a process and survives CLI flag bypass.
    \f
    Args:
        name: Optional plugin name to build the export line for.
        output_format: ``text`` or ``json``.

    Raises:
        click.BadParameter: When ``name`` is not a plugin name.
    """
    if name is not None and (
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) is None
    ):
        raise click.BadParameter("Use a plugin name, not a shell expression.")
    if output_format == "json":
        emit_json(_disable_dict(name))
    elif name is not None:
        click.echo(f"export {_DISABLE_VAR}={name}")
        click.echo(
            "Run this in your shell before starting pain001; "
            "no settings were changed."
        )
    else:
        _disable_help()


def _disable_dict(name: str | None) -> dict[str, Any]:
    """The JSON form of ``plugins disable``.

    Args:
        name: The plugin name, if one was given.

    Returns:
        The variable, the export line for ``name`` and examples.
    """
    return {
        "variable": _DISABLE_VAR,
        "export": f"export {_DISABLE_VAR}={name}" if name else None,
        "examples": list(_DISABLE_EXAMPLES),
    }


def _disable_help() -> None:
    """Print how ``PAIN001_DISABLE_PLUGINS`` works, on stdout."""
    Console().print(
        "[bold]Disable plugins via the [cyan]PAIN001_DISABLE_PLUGINS[/cyan] "
        "environment variable.[/bold]\n\n"
        "  [dim]# disable a single plugin[/dim]\n"
        f"  {_DISABLE_EXAMPLES[0]}\n\n"
        "  [dim]# disable several (comma-separated, whitespace ignored)[/dim]\n"
        f"  {_DISABLE_EXAMPLES[1]}\n\n"
        "The disabled set is read once per process at registry init; "
        "exporting the variable in your shell profile makes the override "
        "persistent across runs."
    )
