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

"""Generate ISO 20022 XML in memory, without touching the filesystem.

``generate_xml_string`` returns the validated XML as a string, which
suits REST APIs, serverless functions, and message queues where the
payload is sent onward rather than written to disk.

Run from the repository root::

    python examples/02_generate_xml_string.py
"""

from pathlib import Path

from pain001 import generate_xml_string
from pain001.constants import TEMPLATES_DIR
from pain001.csv.load_csv_data import load_csv_data

MESSAGE_TYPE = "pain.001.001.03"
DATA_FILE = Path(__file__).resolve().parent / "data" / "payments.csv"


def main() -> None:
    """Render payment rows to an XML string and show a preview."""
    template_dir = TEMPLATES_DIR / MESSAGE_TYPE
    data = load_csv_data(str(DATA_FILE))

    xml_content = generate_xml_string(
        data,
        MESSAGE_TYPE,
        str(template_dir / "template.xml"),
        str(template_dir / f"{MESSAGE_TYPE}.xsd"),
    )

    assert xml_content.startswith("<?xml")
    print(f"Generated {len(xml_content)} characters of validated XML")
    print("First lines:")
    for line in xml_content.splitlines()[:4]:
        print(f"  {line}")


if __name__ == "__main__":
    main()
