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
<xml_message_type> <xml_file_path> <xsd_file_path> <csv_file_path>").

This allows using Pain001 with third-party libraries without modifying
their code.
"""

from pain001.core import process_files
from pain001.context import context
from pain001.constants.constants import valid_xml_types

import os
import sys
import argparse

from pain001.xml.validate_via_xsd import validate_via_xsd


cli_string = """
**Pain001** is a Python Library for Automating ISO 20022-Compliant Payment
Files Using CSV Data.

**Pain001** offers a streamlined solution for reducing complexity and costs
associated with payment processing. By providing a simple and efficient method
to create ISO 20022-compliant payment files, it eliminates the manual effort of
file creation and validation. This not only saves valuable time and resources
but also minimizes the risk of errors, ensuring accurate and seamless payment
processing.

If you are seeking to simplify and automate your payment processing, consider
leveraging the capabilities of **Pain001**.

## Installation

To install **Pain001**, run this command in your terminal:

```sh
pip install pain001
```

## Usage

To use **Pain001**, run this command in your terminal:

```sh
python3 -m pain001 \
    <xml_message_type> \
    <xml_file_path> \
    <xsd_file_path> \
    <csv_file_path>
```

## Arguments:

- `xml_message_type`: The type of XML message. The current valid values are:
    - pain.001.001.03 and
    - pain.001.001.09
- `xml_file_path`: The path to the XML template file.
- `xsd_file_path`: The path to the XSD template file.
- `csv_file_path`: The path to the CSV data file.

## Example:

To generate a pain.001.001.03 XML file from the CSV data file you can run the
following command in your terminal:

```sh
python3 -m pain001 \
    pain.001.001.03 \
    /path/to/your/pain.001.001.03.xml \
    /path/to/your/pain.001.001.03.xsd \
    /path/to/your/pain.001.001.03.csv
```

Note: The generated XML file will be validated against the XSD template
file before being saved. If the validation fails, the program will exit
with an error message.

For more information, please visit the project's GitHub page at:
<https://github.com/sebastienrousseau/pain001>.
"""


def main(
    xml_message_type=None,
    xml_file_path=None,
    xsd_file_path=None,
    data_file_path=None,
    output_file_path=None,
):
    """
    Entrypoint for pain001 when invoked as a module with
    python3 -m pain001 <xml_message_type> <xml_file_path>
    <xsd_file_path> <data_file_path> <output_file_path>.
    """

    """Initialize the context and log a message."""
    logger = context.Context.get_instance().get_logger()

    if (
        xml_file_path is None
        or xsd_file_path is None
        or data_file_path is None
        or output_file_path is None
    ):
        parser = argparse.ArgumentParser(
            description="Generate Pain.001 file from data"
        )
        parser.add_argument(
            "xml_message_type", help="Type of XML message"
        )
        parser.add_argument(
            "xml_file_path", help="Path to XML template file"
        )
        parser.add_argument(
            "xsd_file_path", help="Path to XSD template file"
        )
        parser.add_argument(
            "data_file_path", help="Path to data file (CSV or SQLite)"
        )
        parser.add_argument(
            "output_file_path", help="Path to output XML file"
        )
        args = parser.parse_args()

        logger.info("Parsing command line arguments.")
        xml_message_type = args.xml_message_type
        xml_file_path = args.xml_file_path
        xsd_file_path = args.xsd_file_path
        data_file_path = args.data_file_path
        output_file_path = args.output_file_path

    """Check that the files or values passed as arguments exist."""
    if not xml_message_type:
        logger.info("The XML message type is not specified.")
        print("The XML message type is not specified.")
        sys.exit(1)

    # Check that the XML message type is valid
    if xml_message_type not in valid_xml_types:
        logger.info(f"Invalid XML message type: {xml_message_type}.")
        print(f"Invalid XML message type: {xml_message_type}.")
        sys.exit(1)

    if not os.path.isfile(xml_file_path):
        logger.info(
            "The XML template file '{xml_file_path}' does not exist."
        )
        print("The XML template file '{xml_file_path}' does not exist.")
        sys.exit(1)

    if not os.path.isfile(xsd_file_path):
        logger.info(
            "The XSD template file '{xsd_file_path}' does not exist."
        )
        print("The XSD template file '{xsd_file_path}' does not exist.")
        sys.exit(1)

    if not os.path.isfile(data_file_path):
        logger.info(f"The data file '{data_file_path}' does not exist.")
        print(f"The data file '{data_file_path}' does not exist.")
        sys.exit(1)

    # Validate the XML file and raise a SystemExit exception if invalid
    if not validate_via_xsd(xml_file_path, xsd_file_path):
        logger.info(
            f"Error: XML located at {xml_file_path} is invalid."
        )
        sys.exit(1)

    process_files(
        xml_message_type,
        xml_file_path,
        xsd_file_path,
        data_file_path,
        output_file_path,
    )


if __name__ == "__main__":
    main()
