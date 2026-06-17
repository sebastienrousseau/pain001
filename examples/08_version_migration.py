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

"""Migrate payment data between pain.001 versions.

Banks adopt newer pain.001 versions on their own timelines. The version
mapper maps your existing data from one version to another (via YAML
mappings, with a generic fallback), so you don't re-key it by hand.

Run from the repository root::

    python examples/08_version_migration.py
"""

import tempfile
from pathlib import Path

from pain001.constants import TEMPLATES_DIR
from pain001.migration import VersionMapper

SOURCE = TEMPLATES_DIR / "pain.001.001.03" / "template.csv"


def main() -> None:
    """Migrate bundled v03 payment data to v09 and write the result."""
    mapper = VersionMapper()
    rows = mapper.migrate_file(
        str(SOURCE), "pain.001.001.03", "pain.001.001.09"
    )
    mapper.validate_migrated_rows(rows, "pain.001.001.09")
    assert rows and all(isinstance(r, dict) for r in rows)
    print(f"Migrated {len(rows)} rows from v03 to v09")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "migrated_v09.csv"
        mapper.write_csv(rows, str(out))
        assert out.exists() and out.read_text().strip()
        print(f"Wrote migrated CSV ({out.stat().st_size} bytes)")

    print("Version-migration example completed.")


if __name__ == "__main__":
    main()
