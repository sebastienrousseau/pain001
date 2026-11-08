# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Terminal output helpers shared by the CLI commands.

The CLI prints through a Rich console with markup enabled, so any text
that did not come from pain001 itself (a file name, a data value, an
exception message, a third-party plugin's metadata) must pass through
:func:`esc` before it is interpolated into a markup string. Unescaped,
``[/x]`` raises ``rich.errors.MarkupError`` and ``[link=...]`` becomes
a live terminal hyperlink.
"""

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.validation import SchemeValidationResult


def esc(value: object) -> str:
    """Return ``str(value)`` with Rich markup escaped, for interpolation.

    Args:
        value: Any object; it is converted with :func:`str` first.

    Returns:
        The text with every ``[`` that could open a tag escaped.
    """
    return escape(str(value))


def print_template_list(console: Console) -> None:
    """Print all discovered bundled templates.

    Args:
        console: Rich console to print to.
    """
    table = Table(box=box.SIMPLE_HEAVY)
    table.add_column("Message Type")
    table.add_column("Category")
    table.add_column("Deprecated")
    for metadata in DEFAULT_TEMPLATE_REGISTRY.list_templates():
        table.add_row(
            esc(metadata.message_type),
            esc(metadata.message_category),
            "yes" if metadata.deprecated else "no",
        )
    console.print(table)


def print_template_details(console: Console, message_type: str) -> None:
    """Print metadata for a single template.

    Args:
        console: Rich console to print to.
        message_type: ISO 20022 message type whose template to show.
    """
    metadata = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    console.print(f"[bold]{esc(metadata.message_type)}[/bold]")
    console.print(f"category: {esc(metadata.message_category)}")
    console.print(f"template: {esc(metadata.template_path)}")
    console.print(f"schema: {esc(metadata.xsd_path)}")
    if metadata.example_data_path:
        console.print(f"example data: {esc(metadata.example_data_path)}")
    if metadata.example_xml_path:
        console.print(f"example xml: {esc(metadata.example_xml_path)}")
    console.print(
        f"input formats: {esc(', '.join(metadata.supported_input_formats))}"
    )


def print_scheme_result(
    console: Console,
    result: SchemeValidationResult,
    scheme: str,
    explain: bool,
) -> None:
    """Print a scheme result as human-readable text.

    Violation text is printed with markup off: rule names, field names
    and messages can quote the payment data being checked.

    Args:
        console: Rich console to print to.
        result: Outcome of the scheme or policy check.
        scheme: Profile name the rows were checked against.
        explain: If True, print the remediation hint under each violation.
    """
    console.print(
        f"[cyan]→ Validating against scheme '{esc(scheme)}'...[/cyan]"
    )
    for violation in result.violations:
        colour = "red" if violation.severity == "error" else "yellow"
        console.print(
            f"  row {violation.index} [{violation.rule}] "
            f"{violation.field or ''}: {violation.message}",
            style=colour,
            markup=False,
        )
        if explain and violation.remediation:
            console.print(f"[dim]    fix: {esc(violation.remediation)}[/dim]")
    if result.is_valid:
        console.print(
            f"[bold green]✓ Scheme '{esc(scheme)}' passed[/bold green]"
        )
    else:
        console.print(
            f"[bold red]✗ Scheme '{esc(scheme)}' validation failed[/bold red]",
            style="red",
        )
