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

import logging
import os
import sys
import traceback

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


def _validate_payment_data(
    logger: logging.Logger,
    data_file_path: str,
    xml_message_type: str,
) -> int:
    """Validate payment data and return record count.

    Args:
        logger: Logger instance for event recording.
        data_file_path: Path to payment data file.
        xml_message_type: ISO 20022 message type.

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
    if metadata.example_data_path:
        console.print(f"example data: {metadata.example_data_path}")
    if metadata.example_xml_path:
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
    if xml_message_type not in valid_xml_types:
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
            logger, data_file_path, xml_message_type
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


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
