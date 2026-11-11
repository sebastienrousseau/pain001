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

"""Click-based command-line interface for generating ISO 20022 payment files."""

import functools
import json
import logging
import os
import shlex
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any

import click
from rich import box

# pylint: disable=duplicate-code
from rich.console import Console
from rich.table import Table

from pain001.cli._check import check_cmd
from pain001.cli._config import _resolve_config
from pain001.cli._gpg import _apply_gpg_options, _workers_option
from pain001.cli._hints import GENERATE_HELP, print_data_tip, read_text
from pain001.cli._logging import configure_logging, log_format_option
from pain001.cli._operations import add_operations
from pain001.cli._output import (
    esc,
    print_banner,
    print_scheme_result,
    print_template_details,
    print_template_list,
)
from pain001.cli._paths import (
    _file_not_directory,
    _require_inputs,
    _require_message_type,
    _resolve_template_assets,
)
from pain001.cli._serve import serve_cmd
from pain001.cli._verify_signature import (
    verify_signature_cmd,
    xml_sign_options,
)
from pain001.constants import VERSION, valid_xml_types
from pain001.core.core import process_files, process_files_streaming
from pain001.faces.cli import face_cmd
from pain001.logging_schema import (
    Events,
    Fields,
    log_event,
    log_validation_event,
)
from pain001.observability import (
    MetricEvent,
    clear_metrics_callbacks,
    register_metrics_callback,
)
from pain001.security.path_validator import trusted_paths
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.validation import validate_scheme
from pain001.validation._one_batch import load_batch
from pain001.xml.envelope import BusinessApplicationHeader

console = Console()


def _run_scheme_check(
    data: list[dict[str, Any]],
    scheme: str,
    explain: bool = False,
    output_format: str = "text",
    rules: str | None = None,
    message_type: str = "pain.001.001.03",
) -> None:
    """Validate loaded rows against a payment-scheme rulebook.

    Args:
        data: Loaded payment rows (the normalised internal form).
        scheme: Scheme profile name (e.g. ``'sepa-sct'``).
        explain: If True, print a remediation hint under each violation.
        output_format: ``'text'`` for human output or ``'json'`` for a
            machine-readable result object.
        rules: Optional path to a private YAML policy file.
        message_type: Schema used for policy numeric types.

    Raises:
        SystemExit: 2 if the scheme name is unknown, 1 if rows violate it.
        ValueError: Raised internally for missing policy dependencies and
            converted to SystemExit before returning to the caller.
    """
    try:
        if rules is not None:
            try:
                from pain001.validation.policy import (
                    MAX_POLICY_BYTES,
                    validate_policy,
                )
            except ImportError as exc:
                raise ValueError(
                    "Custom rules require 'pain001[rules]'."
                ) from exc
            with Path(rules).open(encoding="utf-8") as policy_file:
                source = policy_file.read(MAX_POLICY_BYTES + 1)
            result = validate_policy(data, source, scheme, message_type)
        else:
            result = validate_scheme(data, scheme, message_type=message_type)
    except ValueError as exc:
        if output_format == "json":
            print(json.dumps({"error": str(exc)}))
        else:
            console.print(f"✗ {exc}", style="bold red", markup=False)
        raise SystemExit(2) from exc

    if output_format == "json":
        print(
            json.dumps(
                {
                    "profile": result.profile,
                    "is_valid": result.is_valid,
                    "violations": [v.as_dict() for v in result.violations],
                }
            )
        )
        if not result.is_valid:
            raise SystemExit(1)
        return

    print_scheme_result(console, result, scheme, explain)
    if not result.is_valid:
        raise SystemExit(1)


def _validate_payment_data(
    logger: logging.Logger,
    data_file_path: str,
    xml_message_type: str,
    scheme: str | None = None,
    explain: bool = False,
    scheme_format: str = "text",
    rules: str | None = None,
    identifier_checks: bool = True,
) -> int:
    """Validate payment data and return record count.

    Args:
        logger: Logger instance for event recording.
        data_file_path: Path to payment data file.
        xml_message_type: ISO 20022 message type.
        scheme: Optional payment-scheme rulebook to validate against.
        explain: If True, print remediation hints for scheme violations.
        scheme_format: Output format for scheme results ('text' or 'json').
        rules: Optional private YAML policy file.
        identifier_checks: If False, skip the IBAN, BIC and LEI checks.

    Returns:
        Number of valid payment records.

    Raises:
        SystemExit: If validation fails (exit code 1).
    """
    console.print("[cyan]→ Validating payment data...[/cyan]")
    try:
        data = load_batch(data_file_path, xml_message_type, identifier_checks)
        record_count = len(data)
        log_validation_event(
            logger, "payment_data", True, message_type=xml_message_type
        )
        console.print(
            f"[bold green]✓ Data validation passed[/bold green] "
            f"({record_count} payment records)"
        )
        if scheme or rules is not None:
            _run_scheme_check(
                data,
                scheme or "custom",
                explain,
                scheme_format,
                rules,
                xml_message_type,
            )
        return record_count
    except (FileNotFoundError, ValueError, Exception) as e:
        log_validation_event(
            logger, "payment_data", False, e, message_type=xml_message_type
        )
        console.print(
            f"[bold red]✗ Data validation failed:[/bold red] {esc(e)}",
            style="red",
        )
        print_data_tip(console, data_file_path)
        raise SystemExit(1) from e


def _console_metrics_callback(event: MetricEvent) -> None:
    """Render lightweight metrics to the terminal when requested."""
    console.print(
        f"[dim]metric[/dim] {esc(event.name)} {esc(event.attributes)}",
        highlight=False,
    )


def _generate_xml_files(
    _logger: logging.Logger,
    xml_message_type: str,
    xml_template_file_path: str,
    xsd_schema_file_path: str,
    data_file_path: str,
    output_dir: str | None,
    streaming: bool,
    chunk_size: int,
    verbose: bool,
    envelop_bah: bool = False,
    bah_sender: str | None = None,
    bah_receiver: str | None = None,
    bah_msg_id: str | None = None,
    xml_sign_key: str | None = None,
    xml_sign_cert: str | None = None,
    xml_sign_passphrase_env: str | None = None,
    schematron: str | None = None,
    identifier_checks: bool = True,
) -> None:
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    """Generate XML payment files, exiting with code 1 on failure.

    Args:
        _logger: Logger instance for event recording (unused).
        xml_message_type: ISO 20022 message type.
        xml_template_file_path: Path to XML template.
        xsd_schema_file_path: Path to XSD schema.
        data_file_path: Path to payment data.
        output_dir: Optional output directory. Defaults to the current
            working directory.
        streaming: If True, process the input in chunks and write one
            XML file per chunk.
        chunk_size: Rows per chunk in streaming mode.
        verbose: If True, show detailed error traceback.
        envelop_bah: If True, wrap generated XML in an ISO 20022 BAH envelope.
        bah_sender: Sender BIC or Org ID for the Business Application Header.
        bah_receiver: Receiver BIC or Org ID for the Business Application Header.
        bah_msg_id: Business Message Identifier for the Business Application Header.
        xml_sign_key: Path to RSA private key PEM file to sign generated XML.
        xml_sign_cert: Path to X.509 certificate PEM file for KeyInfo.
        xml_sign_passphrase_env: Env var holding passphrase for xml_sign_key.
        schematron: Optional Schematron rulebook preset or path.
        identifier_checks: If False, skip the IBAN, BIC and LEI checks.
    """
    console.print("[cyan]→ Generating XML payment files...[/cyan]")

    # Resolve the output location explicitly instead of chdir-ing into
    # it: changing the working directory re-anchored relative data and
    # template paths, and the old template-relative default broke with
    # bundled templates living outside the working tree.
    resolved_output_dir = (
        os.path.realpath(output_dir) if output_dir else os.getcwd()
    )

    bah_header = None
    if envelop_bah or bah_sender or bah_receiver or bah_msg_id:
        bah_header = BusinessApplicationHeader(
            from_bic=bah_sender,
            to_bic=bah_receiver,
            biz_msg_idr=bah_msg_id,
        )

    sign_key_bytes = read_text(xml_sign_key)
    sign_cert_bytes = read_text(xml_sign_cert)

    sign_passphrase = (
        os.environ.get(xml_sign_passphrase_env)
        if xml_sign_passphrase_env
        else None
    )

    try:
        if streaming:
            process_files_streaming(
                xml_message_type,
                xml_template_file_path,
                xsd_schema_file_path,
                data_file_path,
                chunk_size=chunk_size,
                output_dir=resolved_output_dir,
                envelop_bah=envelop_bah,
                bah_header=bah_header,
                xml_sign_key=sign_key_bytes,
                xml_sign_cert=sign_cert_bytes,
                xml_sign_passphrase=sign_passphrase,
                schematron=schematron,
                identifier_checks=identifier_checks,
            )
        else:
            process_files(
                xml_message_type,
                xml_template_file_path,
                xsd_schema_file_path,
                data_file_path,
                output_path=os.path.join(
                    resolved_output_dir, f"{xml_message_type}.xml"
                ),
                envelop_bah=envelop_bah,
                bah_header=bah_header,
                xml_sign_key=sign_key_bytes,
                xml_sign_cert=sign_cert_bytes,
                xml_sign_passphrase=sign_passphrase,
                schematron=schematron,
                identifier_checks=identifier_checks,
            )

        console.print(
            f"\n[bold green]✓ Success![/bold green] XML files generated successfully.\n"
            f"[cyan]Message Type:[/cyan] {esc(xml_message_type)}\n"
            f"[cyan]Output Location:[/cyan] {esc(resolved_output_dir)}"
        )
    except Exception as e:
        console.print(
            f"[bold red]✗ Generation failed:[/bold red] {esc(e)}",
            style="red",
        )
        if verbose:
            console.print("\n[yellow]Traceback:[/yellow]")
            console.print(traceback.format_exc(), markup=False)
        sys.exit(1)


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
    help="Emit lightweight timing and lifecycle metrics to stdout.",
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
    help="Output format for --scheme results (text or json).",
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
def main(
    xml_message_type: str | None,
    xml_template_file_path: str | None,
    xsd_schema_file_path: str | None,
    data_file_path: str | None,
    config_file: str | None,
    output_dir: str | None,
    dry_run: bool,
    verbose: bool,
    streaming: bool | None,
    chunk_size: int | None,
    profile: str | None,
    show_config: bool,
    list_templates: bool,
    show_template: str | None,
    emit_metrics: bool | None,
    scheme: str | None,
    explain: bool,
    scheme_format: str,
    decrypt_key: str | None = None,
    decrypt_passphrase_env: str | None = None,
    rules: str | None = None,
    envelop_bah: bool = False,
    bah_sender: str | None = None,
    bah_receiver: str | None = None,
    bah_msg_id: str | None = None,
    xml_sign_key: str | None = None,
    xml_sign_cert: str | None = None,
    xml_sign_passphrase_env: str | None = None,
    schematron: str | None = None,
    identifier_checks: bool = True,
    log_format: str | None = None,
) -> None:
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    """CLI entry point for Pain001 ISO 20022 payment file generation.
    \f
    Args:
        xml_message_type: ISO 20022 message type (e.g., 'pain.001.001.03').
        xml_template_file_path: Path to Jinja2 XML template file.
        xsd_schema_file_path: Path to XSD schema for validation.
        data_file_path: Path to CSV, SQLite, JSON, JSONL, or Parquet data file.
        config_file: Optional configuration file path.
        output_dir: Optional output directory for generated XML files.
        dry_run: If True, validate inputs without generating XML.
        verbose: If True, enable detailed logging output.
        streaming: If True, process the input in chunks and write one
            XML file per chunk.
        chunk_size: Rows per chunk in streaming mode.
        profile: Configuration profile or built-in preset name.
        show_config: If True, print the resolved configuration and exit.
        list_templates: If True, list bundled templates and exit.
        show_template: Message type whose bundled template metadata
            should be printed before exiting.
        emit_metrics: If True, emit timing and lifecycle metrics to
            stdout.
        scheme: Optional payment-scheme rulebook (e.g. 'sepa-sct',
            'sepa-sdd') to validate rows against, in addition to XSD.
        explain: If True, print a remediation hint per scheme violation.
        scheme_format: Output format for scheme results ('text' or 'json').
        decrypt_key: Optional GPG private-key file to import before a
            ``.gpg`` / ``.asc`` data file is decrypted.
        decrypt_passphrase_env: Name of the environment variable that
            holds the passphrase for that key.
        rules: Optional path to private YAML CEL policy rules.
        envelop_bah: If True, wrap generated XML in an ISO 20022 BAH envelope.
        bah_sender: Sender BIC or Org ID for the Business Application Header.
        bah_receiver: Receiver BIC or Org ID for the Business Application Header.
        bah_msg_id: Business Message Identifier for the Business Application Header.
        xml_sign_key: Path to RSA private key PEM file to sign generated XML.
        xml_sign_cert: Path to X.509 certificate PEM file for KeyInfo.
        xml_sign_passphrase_env: Env var holding passphrase for xml_sign_key.
        schematron: Optional Schematron rulebook name ('sepa', 'fednow', 'cbpr')
            or filesystem path to a .sch rulebook file.
        identifier_checks: If False, skip the IBAN, BIC and LEI checks.
        log_format: Log record format on stderr ('text' or 'json').

    Exits:
        0 on success, 1 on validation/processing error, 2 on invalid arguments.
    """
    print_banner(console)

    logger = configure_logging(console, verbose, log_format)

    if list_templates:
        print_template_list(console)
        return

    if show_template:
        print_template_details(console, show_template)
        return

    resolved_config = _resolve_config(
        {
            "xml_message_type": xml_message_type,
            "xml_template_file_path": (
                os.path.expanduser(xml_template_file_path)
                if xml_template_file_path
                else None
            ),
            "xsd_schema_file_path": (
                os.path.expanduser(xsd_schema_file_path)
                if xsd_schema_file_path
                else None
            ),
            "data_file_path": (
                os.path.expanduser(data_file_path) if data_file_path else None
            ),
            "config_file": config_file,
            "output_dir": output_dir,
            "streaming": streaming,
            "chunk_size": chunk_size,
            "profile": profile,
            "emit_metrics": emit_metrics,
        },
    )

    xml_message_type = resolved_config.get("xml_message_type")
    data_file_path = resolved_config.get("data_file_path")
    if not xml_message_type:
        console.print("[bold red]✗ Error:[/bold red] Missing XML message type")
        sys.exit(2)
    if not data_file_path:
        console.print("[bold red]✗ Error:[/bold red] Missing data file path")
        sys.exit(2)

    _require_message_type(console, xml_message_type)
    (
        xml_template_file_path,
        xsd_schema_file_path,
    ) = _resolve_template_assets(
        xml_message_type,
        resolved_config.get("xml_template_file_path"),
        resolved_config.get("xsd_schema_file_path"),
    )

    if show_config:
        console.print(resolved_config)
        console.print(
            {
                "template": xml_template_file_path,
                "schema": xsd_schema_file_path,
            }
        )
        return

    inputs = (data_file_path, xml_template_file_path, xsd_schema_file_path)
    _require_inputs(console, inputs)
    # The user named these files; they are read wherever they live.
    click.get_current_context().with_resource(trusted_paths(*inputs))
    if resolved_config.get("emit_metrics"):
        register_metrics_callback(_console_metrics_callback)
    _apply_gpg_options(decrypt_key, decrypt_passphrase_env)

    output_dir = resolved_config.get("output_dir")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        console.print(f"[cyan]ℹ Output directory: {esc(output_dir)}[/cyan]")

    log_event(
        logger,
        logging.INFO,
        Events.CLI_ARGS_PARSED,
        **{Fields.MESSAGE_TYPE: xml_message_type, "dry_run": dry_run},
    )

    validate_data = functools.partial(
        _validate_payment_data,
        logger,
        data_file_path,
        xml_message_type,
        scheme=scheme,
        explain=explain,
        scheme_format=scheme_format,
        rules=rules,
        identifier_checks=identifier_checks,
    )

    if dry_run:
        record_count = validate_data()
        if schematron:
            from pain001.data.loader import load_payment_data
            from pain001.schematron import validate_schematron
            from pain001.xml.generate_xml import generate_xml_string

            payment_data = load_payment_data(data_file_path, identifier_checks)
            xml_str = generate_xml_string(
                payment_data,
                xml_message_type,
                xml_template_file_path,
                xsd_schema_file_path,
            )
            sch_result = validate_schematron(xml_str, rulebook=schematron)
            if not sch_result.is_valid:
                console.print(
                    f"\n[bold red]✗ Schematron rulebook '{esc(schematron)}' failed:[/bold red]\n"
                    f"{esc(sch_result.format_report())}"
                )
                sys.exit(1)
            console.print(
                f"[bold green]✓ Schematron rulebook '{esc(schematron)}' passed[/bold green] "
                f"({sch_result.rules_passed}/{sch_result.rules_evaluated} rules)"
            )

        log_event(
            logger,
            logging.INFO,
            Events.CLI_DRY_RUN,
            **{
                Fields.MESSAGE_TYPE: xml_message_type,
                "validation_passed": True,
                "record_count": record_count,
            },
        )
        console.print(
            "\n[bold green]✓ All validations passed[/bold green] "
            "[dim](--dry-run: no XML generated)[/dim]"
        )
        return

    if scheme or rules is not None:
        validate_data()

    _generate_xml_files(
        logger,
        xml_message_type,
        xml_template_file_path,
        xsd_schema_file_path,
        data_file_path,
        output_dir,
        resolved_config["streaming"],
        resolved_config["chunk_size"],
        verbose,
        envelop_bah=envelop_bah,
        bah_sender=bah_sender,
        bah_receiver=bah_receiver,
        bah_msg_id=bah_msg_id,
        xml_sign_key=xml_sign_key,
        xml_sign_cert=xml_sign_cert,
        xml_sign_passphrase_env=xml_sign_passphrase_env,
        schematron=schematron,
        identifier_checks=identifier_checks,
    )

    clear_metrics_callbacks()


class _DefaultGroup(click.Group):
    """Click group that falls back to a default subcommand.

    Preserves backwards compatibility: an invocation that does not name a
    subcommand — e.g. the long-documented ``pain001 -t ... -d ...`` — is
    routed to ``generate`` so existing scripts and one-liners keep working
    alongside the new subcommand suite (``validate``, ``versions``,
    ``inspect``, ``serve``, ``mcp``, ``init``).
    """

    #: Subcommand invoked when the first token is not itself a subcommand.
    default_command = "generate"

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Inject the default command when no subcommand is named.

        Args:
            ctx: The active Click context.
            args: Raw command-line arguments passed to the group.

        Returns:
            The residual arguments after the group has parsed its own.
        """
        if (
            args
            and args[0] not in self.commands
            and args[0] not in ("-h", "--help", "-V", "--version")
        ):
            args = [self.default_command, *args]
        return super().parse_args(ctx, args)


@click.group(
    cls=_DefaultGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    help=(
        "ISO 20022 payment tooling — one binary for the whole workflow.\n\n"
        "Run a bare invocation (or `generate`) to produce XML; the other "
        "subcommands validate data, introspect templates, and launch the "
        "REST API and MCP servers."
    ),
)
@click.version_option(VERSION, "-V", "--version", prog_name="pain001")
def cli() -> None:
    """Top-level command group for the Pain001 CLI suite."""


cli.add_command(main, name="generate")

# This adapter imports Paramiko only when the user requests an upload.
add_operations(cli)
cli.add_command(face_cmd)
cli.add_command(serve_cmd)
cli.add_command(check_cmd)
cli.add_command(verify_signature_cmd)


@cli.command("validate")
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
    help="Output format for --scheme results (text or json).",
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
@click.pass_context
def validate_cmd(
    ctx: click.Context,
    xml_message_type: str | None,
    xml_template_file_path: str | None,
    xsd_schema_file_path: str | None,
    data_file_path: str | None,
    scheme: str | None,
    explain: bool,
    scheme_format: str,
    decrypt_key: str | None,
    decrypt_passphrase_env: str | None,
    verbose: bool,
    rules: str | None,
    schematron: str | None = None,
    identifier_checks: bool = True,
    log_format: str | None = None,
) -> None:
    """Validate inputs without generating XML (exit 0 = valid, 1 = invalid).

    A named alias for ``generate --dry-run`` that reuses the same template
    resolution and validation pipeline, so CI pre-flight checks read as a
    first-class command.
    \f
    Args:
        ctx: The active Click context, used to invoke ``generate``.
        xml_message_type: ISO 20022 message type to validate against.
        xml_template_file_path: Optional template path (auto-resolved).
        xsd_schema_file_path: Optional XSD schema path (auto-resolved).
        data_file_path: Path to the payment data to validate.
        scheme: Optional scheme rulebook to enforce on top of XSD.
        explain: If True, print a remediation hint per scheme violation.
        scheme_format: Output format for scheme results ('text' or 'json').
        decrypt_key: Optional GPG private-key file for ``.gpg`` inputs.
        decrypt_passphrase_env: Environment variable holding its passphrase.
        verbose: If True, enable detailed logging output.
        rules: Optional path to private YAML CEL policy rules.
        schematron: Optional Schematron rulebook preset or path.
        identifier_checks: If False, skip the IBAN, BIC and LEI checks.
        log_format: Log record format on stderr ('text' or 'json').
    """
    ctx.invoke(
        main,
        xml_message_type=xml_message_type,
        xml_template_file_path=xml_template_file_path,
        xsd_schema_file_path=xsd_schema_file_path,
        data_file_path=data_file_path,
        scheme=scheme,
        explain=explain,
        scheme_format=scheme_format,
        decrypt_key=decrypt_key,
        decrypt_passphrase_env=decrypt_passphrase_env,
        verbose=verbose,
        dry_run=True,
        rules=rules,
        schematron=schematron,
        identifier_checks=identifier_checks,
        log_format=log_format,
    )


@cli.command("versions")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit the supported message types as a JSON array.",
)
def versions_cmd(as_json: bool) -> None:
    """List the ISO 20022 message types this build can generate.
    \f
    Args:
        as_json: If True, print a JSON array instead of a table.
    """
    if as_json:
        console.print_json(json.dumps(valid_xml_types))
        return
    table = Table(box=box.SIMPLE_HEAVY, title="Supported message types")
    table.add_column("Message Type")
    for message_type in valid_xml_types:
        table.add_row(message_type)
    console.print(table)


@cli.command("inspect")
@click.argument("message_type")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit the template metadata as a JSON object.",
)
def inspect_cmd(message_type: str, as_json: bool) -> None:
    """Show the bundled template, schema, and accepted formats for a type.
    \f
    Args:
        message_type: ISO 20022 message type to inspect.
        as_json: If True, print a JSON object instead of formatted text.
    """
    if message_type not in valid_xml_types:
        console.print(
            f"[bold red]✗ Error:[/bold red] Unknown message type: "
            f"[yellow]{esc(message_type)}[/yellow]"
        )
        sys.exit(2)
    if as_json:
        metadata = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
        console.print_json(
            json.dumps(
                {
                    "message_type": metadata.message_type,
                    "category": metadata.message_category,
                    "template": str(metadata.template_path),
                    "schema": str(metadata.xsd_path),
                    "input_formats": list(metadata.supported_input_formats),
                    "deprecated": metadata.deprecated,
                }
            )
        )
        return
    print_template_details(console, message_type)


@cli.command("init")
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
def init_cmd(message_type: str, output_path: str | None) -> None:
    """Scaffold a starter CSV for a message type from its bundled example.
    \f
    Args:
        message_type: ISO 20022 message type to scaffold data for.
        output_path: Optional destination path for the starter CSV.
    """
    if message_type not in valid_xml_types:
        console.print(
            f"[bold red]✗ Error:[/bold red] Unknown message type: "
            f"[yellow]{esc(message_type)}[/yellow]"
        )
        sys.exit(2)
    metadata = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    source = Path(metadata.template_path).parent / "template.csv"
    if not source.is_file():  # pragma: no cover - bundled assets always ship
        console.print(
            f"[bold red]✗ Error:[/bold red] No starter CSV bundled for "
            f"{esc(message_type)}."
        )
        sys.exit(1)
    destination = Path(output_path or f"{message_type}.csv")
    shutil.copyfile(source, destination)
    console.print(
        f"[bold green]✓ Wrote starter CSV:[/bold green] {esc(destination)}"
    )
    # An absolute, quoted path, on one unwrapped line: the command runs
    # as printed from any directory.
    console.print(
        f"[dim]Edit it, then run:[/dim] pain001 generate -t {message_type} "
        f"-d {esc(shlex.quote(str(destination.resolve())))}",
        soft_wrap=True,
    )


@cli.command(
    "mcp",
    context_settings={"ignore_unknown_options": True},
)
def mcp_cmd() -> None:
    """Launch the MCP server over stdio (requires pain001[mcp])."""
    try:
        from pain001.mcp.server import main as mcp_main
    except ImportError:
        console.print(
            "[bold red]✗ Error:[/bold red] The MCP server requires the 'mcp' "
            "extra. Install it with: [cyan]pip install pain001[mcp][/cyan]"
        )
        sys.exit(2)
    mcp_main()  # pragma: no cover - long-running server process


@cli.group("plugins")
def plugins_group() -> None:
    """Inspect the plugin substrate (loaders, validators, schemes, writers)."""


@plugins_group.command("list")
@click.option(
    "--kind",
    type=click.Choice(["loader", "validator", "scheme", "writer"]),
    default=None,
    help="Filter to one plugin kind.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit the plugin list as a JSON array.",
)
def plugins_list_cmd(kind: str | None, as_json: bool) -> None:
    """List every registered plugin (built-in + entry-point discovered).
    \f
    Args:
        kind: Optional kind filter (loader / validator / scheme / writer).
        as_json: If True, print a JSON array instead of a table.
    """
    from pain001.plugins.registry import registry as plugin_registry

    infos = plugin_registry.list_plugins(kind=kind)
    if as_json:
        console.print_json(
            json.dumps(
                [
                    {
                        "kind": info.kind,
                        "name": info.meta.name,
                        "version": info.meta.version,
                        "api_version": list(info.meta.api_version),
                        "description": info.meta.description,
                        "source": info.meta.source,
                    }
                    for info in infos
                ]
            )
        )
        return
    table = Table(box=box.SIMPLE_HEAVY, title="Registered plugins")
    table.add_column("Kind")
    table.add_column("Name")
    table.add_column("Source")
    table.add_column("Description")
    for info in infos:
        table.add_row(
            info.kind,
            esc(info.meta.name),
            esc(info.meta.source),
            esc(info.meta.description),
        )
    console.print(table)


@plugins_group.command("show")
@click.argument("name")
@click.option(
    "--kind",
    type=click.Choice(["loader", "validator", "scheme", "writer"]),
    default=None,
    help="Narrow the search to one kind when the same name exists across kinds.",
)
def plugins_show_cmd(name: str, kind: str | None) -> None:
    """Print the metadata for a single plugin by name.
    \f
    Args:
        name: Plugin's declared name (e.g. ``csv``, ``sepa-sct``).
        kind: Optional kind filter to disambiguate.
    """
    from pain001.plugins.registry import registry as plugin_registry

    matches = [
        info
        for info in plugin_registry.list_plugins(kind=kind)
        if info.meta.name == name
    ]
    if not matches:
        console.print(
            f"[bold red]✗ Error:[/bold red] No plugin named "
            f"[yellow]{esc(name)}[/yellow]"
            + (f" of kind [yellow]{kind}[/yellow]" if kind else "")
            + "."
        )
        sys.exit(1)
    for info in matches:
        console.print(
            f"[bold cyan]{info.kind}[/bold cyan] "
            f"[bold]{esc(info.meta.name)}[/bold] "
            f"[dim]v{esc(info.meta.version)}[/dim]\n"
            f"  source:      {esc(info.meta.source)}\n"
            f"  api version: "
            f"{info.meta.api_version[0]}.{info.meta.api_version[1]}\n"
            f"  description: {esc(info.meta.description)}"
        )


@plugins_group.command("disable")
@click.argument("name", required=False)
def plugins_disable_cmd(name: str | None = None) -> None:
    """Show how to disable plugins via ``PAIN001_DISABLE_PLUGINS``.

    Documentation-only command: the environment variable is the
    canonical disable mechanism because it persists for the lifetime
    of a process and survives CLI flag bypass.
    """
    if name is not None:
        import re

        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) is None:
            raise click.BadParameter(
                "Use a plugin name, not a shell expression."
            )
        click.echo(f"export PAIN001_DISABLE_PLUGINS={name}")
        click.echo(
            "Run this in your shell before starting pain001; no settings were changed."
        )
        return
    console.print(
        "[bold]Disable plugins via the [cyan]PAIN001_DISABLE_PLUGINS[/cyan] "
        "environment variable.[/bold]\n\n"
        "  [dim]# disable a single plugin[/dim]\n"
        "  PAIN001_DISABLE_PLUGINS=parquet pain001 plugins list\n\n"
        "  [dim]# disable several (comma-separated, whitespace ignored)[/dim]\n"
        "  PAIN001_DISABLE_PLUGINS='parquet,sqlite' pain001 plugins list\n\n"
        "The disabled set is read once per process at registry init; "
        "exporting the variable in your shell profile makes the override "
        "persistent across runs."
    )


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    cli()
