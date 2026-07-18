# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Click-based command-line interface for generating ISO 20022 payment files."""

import json
import logging
import os
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

from pain001.config import ConfigManager
from pain001.constants import (
    APP_DESCRIPTION as description,
)
from pain001.constants import (
    APP_NAME as title,
)
from pain001.constants import (
    VERSION,
    valid_xml_types,
)
from pain001.context.context import Context
from pain001.core.core import process_files, process_files_streaming
from pain001.data.loader import load_payment_data
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
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.validation import validate_scheme
from pain001.xml.validate_via_xsd import validate_via_xsd

console = Console()


def _configure_logging(verbose: bool) -> logging.Logger:
    """Configure logging level based on verbosity flag.

    Args:
        verbose: If True, enable DEBUG logging; otherwise INFO.

    Returns:
        Configured logger instance.
    """
    logger = Context.get_instance().get_logger()
    if verbose:
        logger.setLevel(logging.DEBUG)
        console.print("[bold cyan]ℹ Verbose logging enabled[/bold cyan]")
    else:
        logger.setLevel(logging.INFO)
    return logger


def _validate_schema(
    logger: logging.Logger,
    xml_template_file_path: str,
    xsd_schema_file_path: str,
    xml_message_type: str,
) -> None:
    """Validate XML template against XSD schema.

    Args:
        logger: Logger instance for event recording.
        xml_template_file_path: Path to XML template.
        xsd_schema_file_path: Path to XSD schema.
        xml_message_type: ISO 20022 message type.

    Raises:
        SystemExit: If validation fails (exit code 1).
    """
    console.print(
        "[cyan]→ Validating XML template against XSD schema...[/cyan]"
    )
    try:
        validate_via_xsd(xml_template_file_path, xsd_schema_file_path)
        log_validation_event(
            logger, "xsd_schema", True, message_type=xml_message_type
        )
        console.print("[bold green]✓ Schema validation passed[/bold green]")
    except Exception as e:
        log_validation_event(
            logger, "xsd_schema", False, e, message_type=xml_message_type
        )
        console.print(
            f"[bold red]✗ Schema validation failed:[/bold red] {e}",
            style="red",
        )
        console.print(
            f"\n[yellow]Tip:[/yellow] Ensure template and schema versions match. "
            f"Expected: {xml_message_type}"
        )
        raise SystemExit(1) from e


def _run_scheme_check(
    data: list[dict[str, Any]],
    scheme: str,
    explain: bool = False,
    output_format: str = "text",
) -> None:
    """Validate loaded rows against a payment-scheme rulebook.

    Args:
        data: Loaded payment rows (the normalised internal form).
        scheme: Scheme profile name (e.g. ``'sepa-sct'``).
        explain: If True, print a remediation hint under each violation.
        output_format: ``'text'`` for human output or ``'json'`` for a
            machine-readable result object.

    Raises:
        SystemExit: 2 if the scheme name is unknown, 1 if rows violate it.
    """
    try:
        result = validate_scheme(data, scheme)
    except ValueError as exc:
        if output_format == "json":
            print(json.dumps({"error": str(exc)}))
        else:
            console.print(f"[bold red]✗ {exc}[/bold red]", style="red")
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

    console.print(f"[cyan]→ Validating against scheme '{scheme}'...[/cyan]")
    for violation in result.violations:
        colour = "red" if violation.severity == "error" else "yellow"
        console.print(
            f"[{colour}]  row {violation.index} [{violation.rule}] "
            f"{violation.field or ''}: {violation.message}[/{colour}]"
        )
        if explain and violation.remediation:
            console.print(f"[dim]    fix: {violation.remediation}[/dim]")
    if result.is_valid:
        console.print(f"[bold green]✓ Scheme '{scheme}' passed[/bold green]")
    else:
        console.print(
            f"[bold red]✗ Scheme '{scheme}' validation failed[/bold red]",
            style="red",
        )
        raise SystemExit(1)


def _validate_payment_data(
    logger: logging.Logger,
    data_file_path: str,
    xml_message_type: str,
    scheme: str | None = None,
    explain: bool = False,
    scheme_format: str = "text",
) -> int:
    """Validate payment data and return record count.

    Args:
        logger: Logger instance for event recording.
        data_file_path: Path to payment data file.
        xml_message_type: ISO 20022 message type.
        scheme: Optional payment-scheme rulebook to validate against.
        explain: If True, print remediation hints for scheme violations.
        scheme_format: Output format for scheme results ('text' or 'json').

    Returns:
        Number of valid payment records.

    Raises:
        SystemExit: If validation fails (exit code 1).
    """
    console.print("[cyan]→ Validating payment data...[/cyan]")
    try:
        data = load_payment_data(data_file_path)
        record_count = len(data)
        log_validation_event(
            logger, "payment_data", True, message_type=xml_message_type
        )
        console.print(
            f"[bold green]✓ Data validation passed[/bold green] "
            f"({record_count} payment records)"
        )
        if scheme:
            _run_scheme_check(data, scheme, explain, scheme_format)
        return record_count
    except (FileNotFoundError, ValueError, Exception) as e:
        log_validation_event(
            logger, "payment_data", False, e, message_type=xml_message_type
        )
        console.print(
            f"[bold red]✗ Data validation failed:[/bold red] {e}",
            style="red",
        )
        # Provide helpful error messages based on file extension
        file_ext = os.path.splitext(data_file_path)[1].lower()
        if file_ext == ".parquet":
            console.print(
                "\n[yellow]Tip:[/yellow] Parquet files require pyarrow. "
                "Install with: [cyan]pip install pyarrow[/cyan]"
            )
        elif file_ext in [".json", ".jsonl"]:
            console.print(
                "\n[yellow]Tip:[/yellow] Ensure JSON is valid. "
                "Check for syntax errors or invalid structure."
            )
        raise SystemExit(1) from e


def _console_metrics_callback(event: MetricEvent) -> None:
    """Render lightweight metrics to the terminal when requested."""
    console.print(
        f"[dim]metric[/dim] {event.name} {event.attributes}",
        highlight=False,
    )


def _print_template_list() -> None:
    """Print all discovered bundled templates."""
    table = Table(box=box.SIMPLE_HEAVY)
    table.add_column("Message Type")
    table.add_column("Category")
    table.add_column("Deprecated")
    for metadata in DEFAULT_TEMPLATE_REGISTRY.list_templates():
        table.add_row(
            metadata.message_type,
            metadata.message_category,
            "yes" if metadata.deprecated else "no",
        )
    console.print(table)


def _print_template_details(message_type: str) -> None:
    """Print metadata for a single template."""
    metadata = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    console.print(f"[bold]{metadata.message_type}[/bold]")
    console.print(f"category: {metadata.message_category}")
    console.print(f"template: {metadata.template_path}")
    console.print(f"schema: {metadata.xsd_path}")
    if metadata.example_data_path:  # pragma: no cover
        console.print(f"example data: {metadata.example_data_path}")
    if metadata.example_xml_path:  # pragma: no cover
        console.print(f"example xml: {metadata.example_xml_path}")
    console.print(
        f"input formats: {', '.join(metadata.supported_input_formats)}"
    )


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
    """
    console.print("[cyan]→ Generating XML payment files...[/cyan]")

    # Resolve the output location explicitly instead of chdir-ing into
    # it: changing the working directory re-anchored relative data and
    # template paths, and the old template-relative default broke with
    # bundled templates living outside the working tree.
    resolved_output_dir = (
        os.path.realpath(output_dir) if output_dir else os.getcwd()
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
            )

        console.print(
            f"\n[bold green]✓ Success![/bold green] XML files generated successfully.\n"
            f"[cyan]Message Type:[/cyan] {xml_message_type}\n"
            f"[cyan]Output Location:[/cyan] {resolved_output_dir}"
        )
    except Exception as e:
        console.print(
            f"[bold red]✗ Generation failed:[/bold red] {e}",
            style="red",
        )
        if verbose:
            console.print("\n[yellow]Traceback:[/yellow]")
            console.print(traceback.format_exc())
        sys.exit(1)


@click.command(
    help=(
        "Generate ISO 20022-compliant payment XML files from CSV, SQLite, JSON, or Parquet data.\n\n"
        "EXAMPLES:\n\n"
        "  Basic usage (CSV input):\n"
        "    pain001 -t pain.001.001.03 -m template.xml -s schema.xsd -d payments.csv\n\n"
        "  Validation only (dry-run):\n"
        "    pain001 -t pain.001.001.03 -m template.xml -s schema.xsd -d payments.csv --dry-run\n\n"
        "  Custom output directory:\n"
        "    pain001 -t pain.001.001.03 -m template.xml -s schema.xsd -d payments.csv -o /output\n\n"
        "  Verbose logging:\n"
        "    pain001 -t pain.001.001.03 -m template.xml -s schema.xsd -d payments.csv --verbose\n\n"
        "  JSON input:\n"
        "    pain001 -t pain.001.001.03 -m template.xml -s schema.xsd -d payments.json\n\n"
        "EXIT CODES:\n"
        "  0 = Success\n"
        "  1 = Validation or processing error\n"
        "  2 = Invalid arguments or configuration"
    ),
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
    help="Enable detailed logging output (INFO and DEBUG messages)",
)
@click.option(
    "--streaming/--no-streaming",
    default=False,
    help="Process input in chunks and generate one XML file per chunk.",
)
@click.option(
    "--chunk-size",
    default=1000,
    show_default=True,
    type=click.IntRange(min=1),
    help="Number of payment rows per streaming chunk.",
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
    default=False,
    help="Emit lightweight timing and lifecycle metrics to stdout.",
)
@click.option(
    "--scheme",
    type=str,
    default=None,
    help=(
        "Validate rows against a payment-scheme rulebook "
        "(e.g. sepa-sct, sepa-sdd, sepa-b2b, sepa-inst, xborder-ct) on top of XSD validation."
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
def main(
    xml_message_type: str | None,
    xml_template_file_path: str | None,
    xsd_schema_file_path: str | None,
    data_file_path: str | None,
    config_file: str | None,
    output_dir: str | None,
    dry_run: bool,
    verbose: bool,
    streaming: bool,
    chunk_size: int,
    profile: str | None,
    show_config: bool,
    list_templates: bool,
    show_template: str | None,
    emit_metrics: bool,
    scheme: str | None,
    explain: bool,
    scheme_format: str,
) -> None:
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    """CLI entry point for Pain001 ISO 20022 payment file generation.

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

    Exits:
        0 on success, 1 on validation/processing error, 2 on invalid arguments.
    """
    # Display banner
    table = Table(
        box=box.ROUNDED, safe_box=True, show_header=False, title=title
    )
    table.add_column(justify="center", no_wrap=False, vertical="middle")
    table.add_row(description)
    table.width = 80
    console.print(table)

    logger = _configure_logging(verbose)

    if list_templates:
        _print_template_list()
        return

    if show_template:
        _print_template_details(show_template)
        return

    config_manager = ConfigManager()
    resolved_config = config_manager.resolve(
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
        }
    )

    xml_message_type = resolved_config.get("xml_message_type")
    data_file_path = resolved_config.get("data_file_path")
    if not xml_message_type:
        console.print("[bold red]✗ Error:[/bold red] Missing XML message type")
        sys.exit(2)
    if not data_file_path:
        console.print("[bold red]✗ Error:[/bold red] Missing data file path")
        sys.exit(2)

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

    if resolved_config.get("emit_metrics"):
        register_metrics_callback(_console_metrics_callback)

    output_dir = resolved_config.get("output_dir")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        console.print(f"[cyan]ℹ Output directory: {output_dir}[/cyan]")

    log_event(
        logger,
        logging.INFO,
        Events.CLI_ARGS_PARSED,
        **{Fields.MESSAGE_TYPE: xml_message_type, "dry_run": dry_run},
    )

    # Redundant with Click validation; kept so the failure is logged.
    if xml_message_type not in valid_xml_types:  # pragma: no cover
        log_validation_event(
            logger,
            "message_type",
            False,
            ValueError(f"Invalid XML message type: {xml_message_type}"),
            message_type=xml_message_type,
        )
        console.print(
            f"[bold red]✗ Error:[/bold red] Invalid XML message type: [yellow]{xml_message_type}[/yellow]\n"
            f"[cyan]Valid types:[/cyan] {', '.join(valid_xml_types)}",
            style="red",
        )
        sys.exit(2)

    _validate_schema(
        logger, xml_template_file_path, xsd_schema_file_path, xml_message_type
    )

    if dry_run:
        record_count = _validate_payment_data(
            logger,
            data_file_path,
            xml_message_type,
            scheme=scheme,
            explain=explain,
            scheme_format=scheme_format,
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

    if scheme:
        _validate_payment_data(
            logger,
            data_file_path,
            xml_message_type,
            scheme=scheme,
            explain=explain,
            scheme_format=scheme_format,
        )

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
@click.option("-v", "--verbose", is_flag=True, default=False)
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
    verbose: bool,
) -> None:
    """Validate inputs without generating XML (exit 0 = valid, 1 = invalid).

    A named alias for ``generate --dry-run`` that reuses the same template
    resolution and validation pipeline, so CI pre-flight checks read as a
    first-class command.

    Args:
        ctx: The active Click context, used to invoke ``generate``.
        xml_message_type: ISO 20022 message type to validate against.
        xml_template_file_path: Optional template path (auto-resolved).
        xsd_schema_file_path: Optional XSD schema path (auto-resolved).
        data_file_path: Path to the payment data to validate.
        scheme: Optional scheme rulebook to enforce on top of XSD.
        explain: If True, print a remediation hint per scheme violation.
        scheme_format: Output format for scheme results ('text' or 'json').
        verbose: If True, enable detailed logging output.
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
        verbose=verbose,
        dry_run=True,
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

    Args:
        message_type: ISO 20022 message type to inspect.
        as_json: If True, print a JSON object instead of formatted text.
    """
    if message_type not in valid_xml_types:
        console.print(
            f"[bold red]✗ Error:[/bold red] Unknown message type: "
            f"[yellow]{message_type}[/yellow]"
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
    _print_template_details(message_type)


@cli.command("init")
@click.argument("message_type")
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Where to write the starter CSV (default: ./<message_type>.csv).",
)
def init_cmd(message_type: str, output_path: str | None) -> None:
    """Scaffold a starter CSV for a message type from its bundled example.

    Args:
        message_type: ISO 20022 message type to scaffold data for.
        output_path: Optional destination path for the starter CSV.
    """
    if message_type not in valid_xml_types:
        console.print(
            f"[bold red]✗ Error:[/bold red] Unknown message type: "
            f"[yellow]{message_type}[/yellow]"
        )
        sys.exit(2)
    metadata = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    source = Path(metadata.template_path).parent / "template.csv"
    if not source.is_file():  # pragma: no cover - bundled assets always ship
        console.print(
            f"[bold red]✗ Error:[/bold red] No starter CSV bundled for "
            f"{message_type}."
        )
        sys.exit(1)
    destination = Path(output_path or f"{message_type}.csv")
    shutil.copyfile(source, destination)
    console.print(
        f"[bold green]✓ Wrote starter CSV:[/bold green] {destination}\n"
        f"[dim]Edit it, then run:[/dim] pain001 generate -t {message_type} "
        f"-d {destination}"
    )


@cli.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option(
    "--reload",
    is_flag=True,
    default=False,
    help="Enable auto-reload for local development.",
)
def serve_cmd(host: str, port: int, reload: bool) -> None:
    """Launch the REST API with uvicorn (requires pain001[api]).

    Args:
        host: Interface address to bind.
        port: TCP port to listen on.
        reload: If True, enable uvicorn auto-reload.
    """
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[bold red]✗ Error:[/bold red] The REST API requires the 'api' "
            "extra. Install it with: [cyan]pip install pain001[api][/cyan]"
        )
        sys.exit(2)
    console.print(
        f"[cyan]→ Serving pain001 REST API on http://{host}:{port}[/cyan]"
    )
    uvicorn.run(  # pragma: no cover - long-running server process
        "pain001.api.app:app", host=host, port=port, reload=reload
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
            info.meta.name,
            info.meta.source,
            info.meta.description,
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
            f"[yellow]{name}[/yellow]"
            + (f" of kind [yellow]{kind}[/yellow]" if kind else "")
            + "."
        )
        sys.exit(1)
    for info in matches:
        console.print(
            f"[bold cyan]{info.kind}[/bold cyan] "
            f"[bold]{info.meta.name}[/bold] "
            f"[dim]v{info.meta.version}[/dim]\n"
            f"  source:      {info.meta.source}\n"
            f"  api version: "
            f"{info.meta.api_version[0]}.{info.meta.api_version[1]}\n"
            f"  description: {info.meta.description}"
        )


@plugins_group.command("disable")
def plugins_disable_cmd() -> None:
    """Show how to disable plugins via ``PAIN001_DISABLE_PLUGINS``.

    Documentation-only command: the environment variable is the
    canonical disable mechanism because it persists for the lifetime
    of a process and survives CLI flag bypass.
    """
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
