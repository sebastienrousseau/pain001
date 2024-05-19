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

import os
import sys
import click
import configparser

from pain001.constants.constants import valid_xml_types
from pain001.context.context import Context
from pain001.core.core import process_files
from pain001.xml.validate_via_xsd import validate_via_xsd

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
@click.option(
    "-c",
    "--config_file",
    default=None,
    type=click.Path(),
    help="Path to configuration file (optional)",
)
def main(
    xml_message_type,
    xml_template_file_path,
    xsd_schema_file_path,
    data_file_path,
    config_file,
):
    # Expand user-friendly paths
    xml_template_file_path = os.path.expanduser(xml_template_file_path)
    xsd_schema_file_path = os.path.expanduser(xsd_schema_file_path)
    data_file_path = os.path.expanduser(data_file_path)

    # Load configuration file if provided
    if config_file:
        config = configparser.ConfigParser()
        config.read(config_file)
        if "Paths" in config:
            xml_template_file_path = config["Paths"].get(
                "xml_template_file_path", xml_template_file_path
            )
            xsd_schema_file_path = config["Paths"].get(
                "xsd_schema_file_path", xsd_schema_file_path
            )
            data_file_path = config["Paths"].get(
                "data_file_path", data_file_path
            )

    # Check that the required arguments are provided
    if not xml_message_type:
        print("The XML message type is required.")
        sys.exit(1)

    # Check file existence
    for file_path in [
        xml_template_file_path,
        xsd_schema_file_path,
        data_file_path,
    ]:
        if not os.path.isfile(file_path):
            print(f"The file '{file_path}' does not exist.")
            sys.exit(1)

    logger = Context.get_instance().get_logger()

    logger.info("Parsing command line arguments.")

    # Check that the XML message type is valid
    if xml_message_type not in valid_xml_types:
        logger.info(f"Invalid XML message type: {xml_message_type}.")
        print(
            f"""
                Invalid XML message type: {xml_message_type}.
                Valid types are: {', '.join(valid_xml_types)}.
            """
        )
        sys.exit(1)

    # Validate XML and XSD schemas
    try:
        validate_via_xsd(xml_template_file_path, xsd_schema_file_path)
    except Exception as e:
        logger.error(f"Schema validation failed: {e}")
        print(f"Schema validation failed: {e}")
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
