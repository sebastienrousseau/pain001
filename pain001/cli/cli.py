# Copyright (C) 2023 Sebastien Rousseau.
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

import configparser
import contextlib
import logging
import os
import sys
import traceback
from typing import Optional

import click
from rich import box

# pylint: disable=duplicate-code
from rich.console import Console
from rich.table import Table

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
from pain001.core.core import process_files
from pain001.data.loader import load_payment_data
from pain001.logging_schema import (
    Events,
    Fields,
    log_event,
    log_validation_event,
)
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


def _load_configuration(
    config_file: Optional[str],
    xml_template_file_path: str,
    xsd_schema_file_path: str,
    data_file_path: str,
) -> tuple[str, str, str]:
    """Load paths from configuration file if provided.

    Args:
        config_file: Path to INI configuration file (optional).
        xml_template_file_path: Default template path.
        xsd_schema_file_path: Default schema path.
        data_file_path: Default data file path.

    Returns:
        Tuple of (template_path, schema_path, data_path) with config overrides applied.
    """
    if not config_file:
        return xml_template_file_path, xsd_schema_file_path, data_file_path

    config = configparser.ConfigParser()
    config.read(config_file)

    if "Paths" in config:
        xml_template_file_path = config["Paths"].get(
            "xml_template_file_path", xml_template_file_path
        )
        xsd_schema_file_path = config["Paths"].get(
            "xsd_schema_file_path", xsd_schema_file_path
        )
        data_file_path = config["Paths"].get("data_file_path", data_file_path)

    return xml_template_file_path, xsd_schema_file_path, data_file_path


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


@contextlib.contextmanager
def _working_directory(path):
    """Context manager that temporarily changes the working directory."""
    original = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original)


def _generate_xml_files(
    _logger: logging.Logger,
    xml_message_type: str,
    xml_template_file_path: str,
    xsd_schema_file_path: str,
    data_file_path: str,
    output_dir: Optional[str],
    verbose: bool,
) -> None:
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    """Generate XML payment files.

    Args:
        logger: Logger instance for event recording.
        xml_message_type: ISO 20022 message type.
        xml_template_file_path: Path to XML template.
        xsd_schema_file_path: Path to XSD schema.
        data_file_path: Path to payment data.
        output_dir: Optional output directory.
        verbose: If True, show detailed error traceback.

    Raises:
        SystemExit: If generation fails (exit code 1).
    """
    console.print("[cyan]→ Generating XML payment files...[/cyan]")

    try:
        if output_dir:
            with _working_directory(output_dir):
                process_files(
                    xml_message_type,
                    xml_template_file_path,
                    xsd_schema_file_path,
                    data_file_path,
                )
        else:
            process_files(
                xml_message_type,
                xml_template_file_path,
                xsd_schema_file_path,
                data_file_path,
            )

        console.print(
            f"\n[bold green]✓ Success![/bold green] XML files generated successfully.\n"
            f"[cyan]Message Type:[/cyan] {xml_message_type}\n"
            f"[cyan]Output Location:[/cyan] {output_dir or os.getcwd()}"
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
    required=True,
    type=click.Choice(valid_xml_types, case_sensitive=False),
    help="ISO 20022 message type (e.g., 'pain.001.001.03', 'pain.001.001.11')",
)
@click.option(
    "-m",
    "--template",
    "xml_template_file_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to Jinja2 XML template file",
)
@click.option(
    "-s",
    "--schema",
    "xsd_schema_file_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to XSD schema file for validation",
)
@click.option(
    "-d",
    "--data",
    "data_file_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to payment data file (CSV, SQLite, JSON, JSONL, or Parquet)",
)
@click.option(
    "-c",
    "--config",
    "config_file",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to configuration INI file (optional)",
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
def main(
    xml_message_type: str,
    xml_template_file_path: str,
    xsd_schema_file_path: str,
    data_file_path: str,
    config_file: Optional[str],
    output_dir: Optional[str],
    dry_run: bool,
    verbose: bool,
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

    # Step 1: Configure logging
    logger = _configure_logging(verbose)

    # Step 2: Expand user-friendly paths
    xml_template_file_path = os.path.expanduser(xml_template_file_path)
    xsd_schema_file_path = os.path.expanduser(xsd_schema_file_path)
    data_file_path = os.path.expanduser(data_file_path)

    # Step 3: Load configuration file if provided
    (
        xml_template_file_path,
        xsd_schema_file_path,
        data_file_path,
    ) = _load_configuration(
        config_file,
        xml_template_file_path,
        xsd_schema_file_path,
        data_file_path,
    )

    # Step 4: Create output directory if specified
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        console.print(f"[cyan]ℹ Output directory: {output_dir}[/cyan]")

    # Step 5: Log CLI invocation
    log_event(
        logger,
        logging.INFO,
        Events.CLI_ARGS_PARSED,
        **{Fields.MESSAGE_TYPE: xml_message_type, "dry_run": dry_run},
    )

    # Step 6: Validate message type (redundant with Click validation, kept for logging)
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

    # Step 7: Validate XML template against XSD schema
    _validate_schema(
        logger, xml_template_file_path, xsd_schema_file_path, xml_message_type
    )

    # Step 8: Handle dry-run mode (validation only)
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

    # Step 9: Generate XML files
    _generate_xml_files(
        logger,
        xml_message_type,
        xml_template_file_path,
        xsd_schema_file_path,
        data_file_path,
        output_dir,
        verbose,
    )


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
