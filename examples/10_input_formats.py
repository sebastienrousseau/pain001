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

"""Load payment data from every supported input format.

CSV, SQLite, JSON, and JSON Lines all normalise into the same rows, so
the rest of the pipeline is identical regardless of source. (Parquet
works the same way when the ``pain001[parquet]`` extra is installed.)

Run from the repository root::

    python examples/10_input_formats.py
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

from pain001.constants import TEMPLATES_DIR
from pain001.csv.load_csv_data import load_csv_data
from pain001.data.loader import load_payment_data
from pain001.db.load_db_data import load_db_data

TEMPLATE_DIR = TEMPLATES_DIR / "pain.001.001.03"


def main() -> None:
    """Load the bundled sample through CSV, SQLite, JSON, and JSONL."""
    csv_rows = load_payment_data(str(TEMPLATE_DIR / "template.csv"))
    print(f"CSV:    {len(csv_rows)} rows")

    db_rows = load_db_data(str(TEMPLATE_DIR / "template.db"), "pain001")
    print(f"SQLite: {len(db_rows)} rows")

    rows = load_csv_data(str(TEMPLATE_DIR / "template.csv"))
    # The loader restricts paths to the working directory, so derive the
    # JSON/JSONL files there rather than in the system temp dir.
    work = tempfile.mkdtemp(dir=os.getcwd())
    try:
        json_file = Path(work) / "data.json"
        json_file.write_text(json.dumps(rows))
        json_rows = load_payment_data(str(json_file))
        print(f"JSON:   {len(json_rows)} rows")

        jsonl_file = Path(work) / "data.jsonl"
        jsonl_file.write_text("\n".join(json.dumps(r) for r in rows))
        jsonl_rows = load_payment_data(str(jsonl_file))
        print(f"JSONL:  {len(jsonl_rows)} rows")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    # Every format yields the same number of payment rows.
    assert len({len(csv_rows), len(json_rows), len(jsonl_rows)}) == 1
    assert db_rows

    print("Input-formats example completed.")


if __name__ == "__main__":
    main()
