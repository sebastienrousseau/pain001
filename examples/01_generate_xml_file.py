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
# See the License for the specific language governing permissions and
# limitations under the License.

"""Validate a CSV file, then generate a pain.001.001.03 XML file from it.

``pain001.validate`` runs the checks ``pain001 validate`` and the REST
API run, and returns a ``ValidationReport``; ``pain001.generate`` runs
them again, renders the rows through the bundled template, validates
the XML against the bundled XSD and returns a ``GenerationResult``.
Neither needs a template or schema path.

Run from the repository root::

    python examples/01_generate_xml_file.py
"""

import csv
import tempfile
from pathlib import Path

import pain001

MESSAGE_TYPE = "pain.001.001.03"
DATA_FILE = Path(__file__).resolve().parent / "data" / "payments.csv"


def main() -> None:
    """Validate the CSV data and write a pain.001 XML file."""
    report: pain001.ValidationReport = pain001.validate(
        DATA_FILE, MESSAGE_TYPE
    )
    assert report.is_valid, report.errors
    print(f"Validated {report.total_rows} payment rows from {DATA_FILE.name}")

    with tempfile.TemporaryDirectory() as output_dir:
        result: pain001.GenerationResult = pain001.generate(
            DATA_FILE, MESSAGE_TYPE, output_dir=output_dir
        )
        size = result.path.stat().st_size
        print(f"Generated and XSD-validated {result.path} ({size} bytes)")

        # A value that breaks the message type's JSON Schema is refused
        # before any XML is written, with the line and column of each
        # problem. Every pain001 exception derives from Pain001Error.
        # Rows can be passed as dictionaries instead of a file.
        with DATA_FILE.open(encoding="utf-8", newline="") as handle:
            rows = [
                dict(row, currency="EURO") for row in csv.DictReader(handle)
            ]
        try:
            pain001.generate(rows, MESSAGE_TYPE, output_dir=output_dir)
        except pain001.Pain001Error as exc:
            assert isinstance(exc, pain001.PaymentValidationError)
            issue = exc.errors[0]
            assert issue.column == "currency", issue
            print(f"Refused as expected: {issue}")
        else:
            raise AssertionError("currency=EURO was accepted")


if __name__ == "__main__":
    main()
