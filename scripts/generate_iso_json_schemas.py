# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""Write (or with ``--check`` verify) the ISO JSON twin schemas.

One JSON Schema 2020-12 per bundled pain.001 edition under
``pain001/schemas/iso-json/``, generated from the schema inventory by
the ISO 20022 RA rules (:mod:`pain001.twins.schema`).

Usage:
    poetry run python scripts/generate_iso_json_schemas.py [--check]
"""

from __future__ import annotations

import sys

from pain001.constants import valid_xml_types
from pain001.twins.iso_json import SUPPORTED_PREFIX
from pain001.twins.schema import SCHEMA_DIR, schema_text


def main(argv: list[str] | None = None) -> int:
    """Write or verify every schema.

    Args:
        argv: Command-line arguments; ``--check`` verifies only.

    Returns:
        0 when every schema is written or up to date, 1 when ``--check``
        found a stale one.
    """
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    stale = 0
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for version in valid_xml_types:
        if not version.startswith(SUPPORTED_PREFIX):
            continue
        path = SCHEMA_DIR / f"{version}.schema.json"
        text = schema_text(version)
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            print(f"up to date  {path.name}")
            continue
        stale += 1
        if check:
            print(f"STALE       {path.name}")
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote       {path.name} ({len(text)} bytes)")
    if check and stale:
        print(
            f"{stale} stale schema(s); run scripts/generate_iso_json_schemas.py"
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
