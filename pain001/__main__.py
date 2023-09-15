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
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=invalid-name
"""
Enables use of Python Pain001 as a "main" function (i.e.
"python3 -m pain001
<xml_message_type> <xml_template_file_path> <xsd_schema_file_path>
<data_file_path>").

This allows using Pain001 with third-party libraries without modifying
their code.
"""


import os
import sys
import click

from pain001.constants.constants import valid_xml_types
from pain001.context.context import Context
from pain001.core.core import process_files

# from pain001.xml.validate_via_xsd import validate_via_xsd

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

table = Table(
    box=box.ROUNDED, safe_box=True, show_header=False, title=title
)

table.add_column(justify="center", no_wrap=False, vertical="middle")
table.add_row(description)
table.width = 80
console.print(table)


@click.command(
    help=(
        "To use Pain001, you must specify the following options:\n\n"
    ),
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
def main(
    xml_message_type,
    xml_template_file_path,
    xsd_schema_file_path,
    data_file_path,
):
    """Initialize the context and log a message."""
    logger = Context.get_instance().get_logger()

    # print("Inside main function")

    def check_variable(variable, name):
        if variable is None:
            print(f"Error: {name} is required.")
            sys.exit(1)

    # Check that xml_message_type is provided
    check_variable(xml_message_type, "xml_message_type")

    # Check that xsd_schema_file_path is provided
    check_variable(xsd_schema_file_path, "xsd_schema_file_path")

    # Check that data_file_path is provided
    check_variable(data_file_path, "data_file_path")

    # Check that xml_template_file_path is not invalid
    if not os.path.isfile(xml_template_file_path):
        print(
            f"The XML template file '{xml_template_file_path}' does not exist."
        )
        sys.exit(1)

    # Check that xsd_schema_file_path is not invalid
    if not os.path.isfile(xsd_schema_file_path):
        print(
            f"The XSD template file '{xsd_schema_file_path}' does not exist."
        )
        sys.exit(1)

    # Check that data_file_path is not invalid
    if not os.path.isfile(data_file_path):
        print(f"The data file '{data_file_path}' does not exist.")
        sys.exit(1)

    # Check that other necessary arguments are provided
    if (
        xml_template_file_path is None
        or xsd_schema_file_path is None
        or data_file_path is None
    ):
        print(click.get_current_context().get_help())
        sys.exit(1)

    logger = Context.get_instance().get_logger()

    logger.info("Parsing command line arguments.")

    # Check that the XML message type is valid
    if xml_message_type not in valid_xml_types:
        logger.info(f"Invalid XML message type: {xml_message_type}.")
        print(f"Invalid XML message type: {xml_message_type}.")
        sys.exit(1)

    if not os.path.isfile(xml_template_file_path):
        logger.info(
            f"The XML template file '{xml_template_file_path}' does not exist."
        )
        print(
            f"The XML template file '{xml_template_file_path}' does not exist."
        )
        sys.exit(1)

    if not os.path.isfile(xsd_schema_file_path):
        logger.info(
            f"The XSD template file '{xsd_schema_file_path}' does not exist."
        )
        print(
            f"The XSD template file '{xsd_schema_file_path}' does not exist."
        )
        sys.exit(1)

    if not os.path.isfile(data_file_path):
        logger.info(f"The data file '{data_file_path}' does not exist.")
        print(f"The data file '{data_file_path}' does not exist.")
        sys.exit(1)

    process_files(
        xml_message_type,
        xml_template_file_path,
        xsd_schema_file_path,
        data_file_path,
    )


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
