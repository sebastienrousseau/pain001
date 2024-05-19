# Other imports remain the same
import click
import os
import sys
from pain001.constants.constants import valid_xml_types
from pain001.context.context import Context
from pain001.core.core import process_files
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

description = """
A powerful Python library that enables you to create
ISO 20022-compliant payment files directly from CSV or SQLite Data files.\n
https://pain001.com
"""
title = "Pain001"

table = Table(box=box.ROUNDED, safe_box=True, show_header=False, title=title)
table.add_column(justify="center", no_wrap=False, vertical="middle")
table.add_row(description)
table.width = 80
console.print(table)


@click.command(
    help=("To use Pain001, you must specify the following options:\n\n"),
    context_settings=dict(help_option_names=["-h", "--help"]),
)
@click.option(
    "-t",
    "--xml_message_type",
    default=None,
    help="Type of XML message (required)",
)
@click.option(
    "-m",
    "--xml_template_file_path",
    default=None,
    type=click.Path(),
    help="Path to XML template file (required)",
)
@click.option(
    "-s",
    "--xsd_schema_file_path",
    default=None,
    type=click.Path(),
    help="Path to XSD template file (required)",
)
@click.option(
    "-d",
    "--data_file_path",
    default=None,
    type=click.Path(),
    help="Path to data file (CSV or SQLite) (required)",
)
def cli(
    xml_message_type,
    xml_template_file_path,
    xsd_schema_file_path,
    data_file_path,
):
    main(
        xml_message_type,
        xml_template_file_path,
        xsd_schema_file_path,
        data_file_path,
    )


def main(
    xml_message_type,
    xml_template_file_path,
    xsd_schema_file_path,
    data_file_path,
):
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

        logger = Context.get_instance().get_logger()

        logger.info("Parsing command line arguments.\n")

        # Check that the XML message type is valid
        if xml_message_type not in valid_xml_types:
            logger.info(f"Invalid XML message type: {xml_message_type}.")
            console.print(f"Invalid XML message type: {xml_message_type}.")
            sys.exit(1)

        if not os.path.isfile(xml_template_file_path):
            logger.info(
                f"""
            The XML template file '{xml_template_file_path}' does not exist.
            """
            )
            console.print(
                f"""
            The XML template file '{xml_template_file_path}' does not exist.
            """
            )
            sys.exit(1)

        if not os.path.isfile(xsd_schema_file_path):
            logger.info(
                f"""
            The XSD template file '{xsd_schema_file_path}' does not exist.
            """
            )
            console.print(
                f"""
            The XSD template file '{xsd_schema_file_path}' does not exist.
            """
            )
            sys.exit(1)

        if not os.path.isfile(data_file_path):
            logger.info(f"The data file '{data_file_path}' does not exist.")
            console.print(f"The data file '{data_file_path}' does not exist.")
            sys.exit(1)

        process_files(
            xml_message_type,
            xml_template_file_path,
            xsd_schema_file_path,
            data_file_path,
        )
    except Exception as e:
        console.print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    cli()
