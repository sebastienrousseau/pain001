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
"python3 -m pain001 <xml_file_path> <xsd_file_path> <csv_file_path>").

This allows using Pain001 with third-party libraries without modifying
their code.
"""

from .core import process_files

import os
import sys
import argparse

cli_string = """

usage:
python3 -m pain001 <xml_file_path> <xsd_file_path> <csv_file_path>

Python Pain001 is a Python package that generates a Customer-to-Bank
Credit Transfer payload in the pain.001.001.03 format from a CSV file.
The package is named after the standard file format for SEPA and
non-SEPA Credit Transfer, which is the Pain (payment initiation)
format 001.001.03. The Pain001 library provides a convenient way for
developers to create payment files in this format and to validate
the generated files against the XSD schema.

Usage:
python3 -m pain001 <xml_file_path> <xsd_file_path> <csv_file_path>

The first argument is the path of the XML template file. The second
argument is the path of the XSD template file. The third argument is
the path of the CSV file containing the payment data."""


def main(xml_file_path=None, xsd_file_path=None, csv_file_path=None):
    """
    Entrypoint for pain001 when invoked as a module with
    python3 -m pain001 <xml_file_path> <xsd_file_path> <csv_file_path>.
    """

    if xml_file_path is None or xsd_file_path is None or csv_file_path is None:
        parser = argparse.ArgumentParser(
            description="Generate Pain.001 file from CSV data"
        )
        parser.add_argument("xml_file_path", help="Path to XML template file")
        parser.add_argument("xsd_file_path", help="Path to XSD template file")
        parser.add_argument("csv_file_path", help="Path to CSV data file")
        args = parser.parse_args()

        xml_file_path = args.xml_file_path
        xsd_file_path = args.xsd_file_path
        csv_file_path = args.csv_file_path

    if not os.path.isfile(xml_file_path):
        print("The XML template file does not exist.")
        sys.exit(1)

    if not os.path.isfile(xsd_file_path):
        print("The XSD template file does not exist.")
        sys.exit(1)

    if not os.path.isfile(csv_file_path):
        print(f"The CSV file '{csv_file_path}' does not exist.")
        sys.exit(1)

    process_files(xml_file_path, xsd_file_path, csv_file_path)


if __name__ == "__main__":
    main()
