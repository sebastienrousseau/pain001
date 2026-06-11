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

"""Generate a pain.001.001.03 XML file from CSV with the library API.

Loads payment rows from ``examples/data/payments.csv``, renders them
through the bundled template, validates the result against the bundled
XSD schema, and writes the XML file to a temporary directory.

Run from the repository root::

    python examples/01_generate_xml_file.py
"""

import tempfile
from pathlib import Path

from pain001.constants import TEMPLATES_DIR
from pain001.csv.load_csv_data import load_csv_data
from pain001.xml.generate_xml import generate_xml

MESSAGE_TYPE = "pain.001.001.03"
DATA_FILE = Path(__file__).resolve().parent / "data" / "payments.csv"


def main() -> None:
    """Load CSV data and write a validated pain.001 XML file."""
    template_dir = TEMPLATES_DIR / MESSAGE_TYPE
    data = load_csv_data(str(DATA_FILE))
    print(f"Loaded {len(data)} payment rows from {DATA_FILE.name}")

    with tempfile.TemporaryDirectory() as output_dir:
        output_path = generate_xml(
            data,
            MESSAGE_TYPE,
            str(template_dir / "template.xml"),
            str(template_dir / f"{MESSAGE_TYPE}.xsd"),
            output_path=str(Path(output_dir) / f"{MESSAGE_TYPE}.xml"),
        )
        size = Path(output_path).stat().st_size
        print(f"Generated and XSD-validated {output_path} ({size} bytes)")


if __name__ == "__main__":
    main()
