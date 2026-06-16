# pylint: disable=duplicate-code

"""Module entry point for ``python -m pain001``."""

import sys

from rich.console import Console

from pain001.cli.cli import cli
from pain001.core.core import process_files
from pain001.validation import ValidationConfig, ValidationService

console = Console()


def main(
    xml_message_type: str | None,
    xml_template_file_path: str | None,
    xsd_schema_file_path: str | None,
    data_file_path: str | None,
    dry_run: bool = False,
) -> None:
    """Main entry point for python -m pain001.

    Args:
        xml_message_type: ISO 20022 message type (e.g., 'pain.001.001.03').
        xml_template_file_path: Path to Jinja2 XML template file.
        xsd_schema_file_path: Path to XSD schema for validation.
        data_file_path: Path to CSV or SQLite data file.
        dry_run: If True, validate inputs without generating XML.

    Exits:
        0 on success, 1 on validation or processing error.
    """
    try:
        # Check that the required arguments are provided
        if not xml_message_type:
            console.print(
                "The XML message type is required. Use -h for help.\n"
            )
            sys.exit(1)

        if not xml_template_file_path:
            console.print("The XML template file path is required.\n")
            sys.exit(1)

        if not xsd_schema_file_path:
            console.print("The XSD schema file path is required.\n")
            sys.exit(1)

        if not data_file_path:
            console.print("The data file path is required.\n")
            sys.exit(1)

        # Use ValidationService for comprehensive validation
        validation_service = ValidationService()
        validation_config = ValidationConfig(
            xml_message_type=xml_message_type,
            xml_template_file_path=xml_template_file_path,
            xsd_schema_file_path=xsd_schema_file_path,
            data_file_path=data_file_path,
        )

        report = validation_service.validate_all(validation_config)

        if not report.is_valid:
            console.print("\n[red]Validation Failed:[/red]")
            for error in report.errors:
                console.print(f"  • {error}")
            sys.exit(1)

        if dry_run:  # pragma: no cover
            console.print(  # pragma: no cover
                "[green]✓ Validation succeeded. No XML generated (--dry-run).[/green]"
            )
            return  # pragma: no cover

        process_files(
            xml_message_type,
            xml_template_file_path,
            xsd_schema_file_path,
            data_file_path,
        )
    except Exception as e:
        console.print(f"[red]An error occurred: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    cli()
