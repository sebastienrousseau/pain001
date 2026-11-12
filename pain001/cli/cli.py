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

"""Click-based command-line interface for generating ISO 20022 payment files.

This module declares the ``pain001`` group and the ``generate`` and
``validate`` options; what they do lives in :mod:`pain001.cli._generate`
and the other commands in their own modules.
"""

import sys
from typing import Any

import click
from rich.console import Console

from pain001.cli._check import check_cmd
from pain001.cli._format import format_option, quiet_option
from pain001.cli._generate import run_generate
from pain001.cli._gpg import _workers_option
from pain001.cli._groups import DefaultGroup
from pain001.cli._hints import GENERATE_HELP
from pain001.cli._info import init_cmd, inspect_cmd, versions_cmd
from pain001.cli._logging import log_format_option
from pain001.cli._operations import add_operations
from pain001.cli._plugins import plugins_group
from pain001.cli._serve import serve_cmd
from pain001.cli._verify_signature import (
    verify_signature_cmd,
    xml_sign_options,
)
from pain001.constants import VERSION, valid_xml_types
from pain001.faces.cli import face_cmd

__all__ = ["cli", "main"]

_identifier_checks_option = click.option(
    "--identifier-checks/--no-identifier-checks",
    default=True,
    help="Check each IBAN, BIC and LEI (check digits); on by default.",
)


@click.command(
    help=GENERATE_HELP,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "-t",
    "--xml-message-type",
    "xml_message_type",
    required=False,
    type=click.Choice(valid_xml_types, case_sensitive=False),
    help="ISO 20022 message type (e.g., 'pain.001.001.03', 'pain.001.001.11')",
)
@click.option(
    "-m",
    "--template",
    "xml_template_file_path",
    required=False,
    type=click.Path(dir_okay=False, readable=True),
    help="Path to Jinja2 XML template file (auto-resolved when omitted)",
)
@click.option(
    "-s",
    "--schema",
    "xsd_schema_file_path",
    required=False,
    type=click.Path(dir_okay=False, readable=True),
    help="Path to XSD schema file for validation (auto-resolved when omitted)",
)
@click.option(
    "-d",
    "--data",
    "data_file_path",
    required=False,
    type=click.Path(dir_okay=False, readable=True),
    help="Path to payment data file (CSV, SQLite, JSON, JSONL, or Parquet)",
)
@click.option(
    "-c",
    "--config",
    "config_file",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to configuration YAML, TOML, or INI file (optional)",
)
@click.option(
    "-o",
    "--output-dir",
    "output_dir",
    type=click.Path(file_okay=False, writable=True),
    help="Output directory for generated XML files (default: current directory)",
)
@click.option(
    "--dry-run",
    "--validate-only",
    "dry_run",
    is_flag=True,
    default=False,
    help=(
        "Validate inputs without generating XML. "
        "Useful for CI/CD pre-flight checks. Exit code 0 = valid, 1 = invalid."
    ),
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Show the library's DEBUG and INFO log records on stderr.",
)
@click.option(
    "--streaming/--no-streaming",
    default=None,
    help="Process input in chunks and generate one XML file per chunk.",
)
@click.option(
    "--chunk-size",
    default=None,
    type=click.IntRange(min=1),
    help="Number of payment rows per streaming chunk (default: 1000).",
)
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    expose_value=False,
    callback=_workers_option,
    help="Processes building streamed chunks at once (with --streaming).",
)
@click.option(
    "--profile",
    type=str,
    help="Configuration profile or built-in preset to apply.",
)
@click.option(
    "--show-config",
    is_flag=True,
    default=False,
    help="Print the resolved configuration and exit.",
)
@click.option(
    "--list-templates",
    is_flag=True,
    default=False,
    help="List bundled templates and exit.",
)
@click.option(
    "--show-template",
    type=str,
    help="Show metadata for one bundled template and exit.",
)
@click.option(
    "--emit-metrics",
    is_flag=True,
    default=None,
    help="Write timing and lifecycle metrics to stdout as JSON lines.",
)
@click.option(
    "--scheme",
    type=str,
    default=None,
    help=(
        "Validate rows against a payment-scheme rulebook "
        "(e.g. sepa-sct, sepa-sdd, sepa-b2b, sepa-inst, xborder-ct, "
        "anti-duplicate) on top of XSD validation. Comma-separate names "
        "to run several: sepa-sct,anti-duplicate."
    ),
)
@click.option(
    "--explain",
    is_flag=True,
    default=False,
    help="With --scheme, print a remediation hint for each violation.",
)
@click.option(
    "--scheme-format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Deprecated: use --format json.",
)
@click.option(
    "--decrypt-key",
    "decrypt_key",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default=None,
    help=(
        "GPG private-key file to import before reading a .gpg/.asc "
        "data file (requires pain001[gpg]; sets PAIN001_GPG_KEYFILE)."
    ),
)
@click.option(
    "--decrypt-passphrase-env",
    "decrypt_passphrase_env",
    type=str,
    default=None,
    metavar="VAR",
    help=(
        "Name of the environment variable holding the GPG passphrase "
        "(sets PAIN001_GPG_PASSPHRASE_ENV; the passphrase itself never "
        "appears on the command line)."
    ),
)
@click.option(
    "--rules",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default=None,
    help="Private YAML CEL policy to enforce before generation (requires pain001[rules]).",
)
@click.option(
    "--envelop-bah",
    is_flag=True,
    default=False,
    help=(
        "Encapsulate generated payment in an ISO 20022 Business Application "
        "Header (head.001.001.03) envelope."
    ),
)
@click.option(
    "--bah-sender",
    type=str,
    default=None,
    help="Sender BIC or Org ID for the Business Application Header.",
)
@click.option(
    "--bah-receiver",
    type=str,
    default=None,
    help="Receiver BIC or Org ID for the Business Application Header.",
)
@click.option(
    "--bah-msg-id",
    type=str,
    default=None,
    help="Business Message Identifier for the Business Application Header.",
)
@xml_sign_options
@click.option(
    "--schematron",
    type=str,
    default=None,
    help="Schematron business rules preset ('sepa', 'fednow', 'cbpr') or path to .sch file.",
)
@_identifier_checks_option
@log_format_option
@format_option()
@quiet_option
def main(**options: Any) -> None:
    """CLI entry point for Pain001 ISO 20022 payment file generation.
    \f
    Args:
        **options: Every option above, by parameter name; see
            :func:`pain001.cli._generate.run_generate`.

    Exits:
        0 on success, 1 on validation/processing error, 2 on invalid arguments.
    """
    run_generate(options)


@click.group(
    cls=DefaultGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    help=(
        "ISO 20022 payment tooling: one binary for the whole workflow.\n\n"
        "Run a bare invocation (or `generate`) to produce XML; the other "
        "subcommands validate data, introspect templates, and launch the "
        "REST API and MCP servers."
    ),
)
@click.version_option(VERSION, "-V", "--version", prog_name="pain001")
def cli() -> None:
    """Top-level command group for the Pain001 CLI suite."""


@click.command("validate")
@click.option(
    "-t",
    "--xml-message-type",
    "xml_message_type",
    type=click.Choice(valid_xml_types, case_sensitive=False),
    help="ISO 20022 message type (e.g., 'pain.001.001.03').",
)
@click.option(
    "-m",
    "--template",
    "xml_template_file_path",
    type=click.Path(dir_okay=False, readable=True),
    help="Path to Jinja2 XML template (auto-resolved when omitted).",
)
@click.option(
    "-s",
    "--schema",
    "xsd_schema_file_path",
    type=click.Path(dir_okay=False, readable=True),
    help="Path to XSD schema (auto-resolved when omitted).",
)
@click.option(
    "-d",
    "--data",
    "data_file_path",
    type=click.Path(dir_okay=False, readable=True),
    help="Path to payment data (CSV, SQLite, JSON, JSONL, or Parquet).",
)
@click.option(
    "--scheme",
    type=str,
    default=None,
    help="Also validate rows against a scheme rulebook (e.g. sepa-sct).",
)
@click.option(
    "--explain",
    is_flag=True,
    default=False,
    help="With --scheme, print a remediation hint for each violation.",
)
@click.option(
    "--scheme-format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Deprecated: use --format json.",
)
@click.option(
    "--decrypt-key",
    "decrypt_key",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default=None,
    help="GPG private-key file to import before reading a .gpg/.asc file.",
)
@click.option(
    "--decrypt-passphrase-env",
    "decrypt_passphrase_env",
    type=str,
    default=None,
    metavar="VAR",
    help="Environment variable holding the GPG passphrase.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Show the library's DEBUG and INFO log records on stderr.",
)
@click.option(
    "--rules",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default=None,
    help="Private YAML CEL policy (requires pain001[rules]).",
)
@click.option(
    "--schematron",
    type=str,
    default=None,
    help="Schematron business rules preset ('sepa', 'fednow', 'cbpr') or path to .sch file.",
)
@_identifier_checks_option
@log_format_option
@format_option()
@quiet_option
@click.pass_context
def validate_cmd(ctx: click.Context, /, **options: Any) -> None:
    """Validate inputs without generating XML (exit 0 = valid, 1 = invalid).

    A named alias for ``generate --dry-run`` that reuses the same template
    resolution and validation pipeline, so CI pre-flight checks read as a
    first-class command.
    \f
    Args:
        ctx: The active Click context, used to invoke ``generate``.
        **options: The options above, passed on to ``generate``.
    """
    ctx.invoke(main, dry_run=True, **options)


@click.command(
    "mcp",
    context_settings={"ignore_unknown_options": True},
)
def mcp_cmd() -> None:
    """Launch the MCP server over stdio (requires pain001[mcp])."""
    try:
        from pain001.mcp.server import main as mcp_main
    except ImportError:
        Console(stderr=True).print(
            "[bold red]✗ Error:[/bold red] The MCP server requires the 'mcp' "
            "extra. Install it with: [cyan]pip install pain001[mcp][/cyan]"
        )
        sys.exit(2)
    mcp_main()  # pragma: no cover - long-running server process


cli.add_command(main, name="generate")
# This adapter imports Paramiko only when the user requests an upload.
add_operations(cli)
for _command in (
    face_cmd,
    serve_cmd,
    check_cmd,
    verify_signature_cmd,
    validate_cmd,
    versions_cmd,
    inspect_cmd,
    init_cmd,
    mcp_cmd,
    plugins_group,
):
    cli.add_command(_command)


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    cli()
