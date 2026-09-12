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

"""Regenerate the bundled example XML for every registered message type.

Each ``pain001/templates/<type>/<type>.xml`` is the rendering of that
bundle's ``template.csv`` (every row) through its Jinja template,
validated against its XSD. The result is what ``metadata.yaml`` points
at as ``files.example_xml`` and what ``pain001 inspect`` prints.

``tests/test_bundled_examples.py`` asserts the committed files equal this
rendering byte for byte, so run this after changing a template, a
preparer or a sample CSV, then commit the result alongside the golden
files from ``scripts/generate_golden_files.py``.

Usage:
    poetry run python scripts/generate_xml_examples.py [--check]

``--check`` writes nothing and exits 1 if any example is stale.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.xml.generate_xml import generate_xml_string

REPO_ROOT = Path(__file__).resolve().parent.parent


def render_example(message_type: str) -> tuple[Path, str]:
    """Render the example for ``message_type`` from its bundle.

    Args:
        message_type: A registered message type, e.g. ``pain.001.001.09``.

    Returns:
        The path the example lives at and the rendered, XSD-valid XML.
    """
    meta = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    data_path = meta.example_data_path or meta.template_path.parent / (
        "template.csv"
    )
    with open(data_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    xml = generate_xml_string(
        rows, message_type, str(meta.template_path), str(meta.xsd_path)
    )
    out = meta.example_xml_path or meta.template_path.parent / (
        f"{message_type}.xml"
    )
    return out, xml


def main(argv: list[str] | None = None) -> int:
    """Regenerate (or with ``--check`` verify) every bundled example.

    Args:
        argv: Command-line arguments; ``--check`` verifies only.

    Returns:
        Process exit code: 0 when up to date or regenerated, 1 when
        ``--check`` found a stale example.
    """
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    stale = 0
    for meta in DEFAULT_TEMPLATE_REGISTRY.list_templates():
        out, xml = render_example(meta.message_type)
        current = out.read_text(encoding="utf-8") if out.exists() else None
        if current == xml:
            print(f"up to date  {out.relative_to(REPO_ROOT)}")
            continue
        stale += 1
        if check:
            print(f"STALE       {out.relative_to(REPO_ROOT)}")
        else:
            out.write_text(xml, encoding="utf-8")
            print(
                f"regenerated {out.relative_to(REPO_ROOT)} ({len(xml)} bytes)"
            )
    if check and stale:
        print(
            f"{stale} stale example(s); run scripts/generate_xml_examples.py"
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
