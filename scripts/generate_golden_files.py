"""Regenerate the golden XML fixtures in tests/golden/.

Run from the repository root:
    poetry run python scripts/generate_golden_files.py
"""

import csv
from pathlib import Path

from pain001.constants import valid_xml_types
from pain001.xml.generate_xml import generate_xml_string

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "pain001" / "templates"
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for version in valid_xml_types:
        base = TEMPLATES_DIR / version
        with open(
            base / "template.csv", newline="", encoding="utf-8"
        ) as handle:
            data = list(csv.DictReader(handle))[:2]
        xml = generate_xml_string(
            data,
            version,
            str(base / "template.xml"),
            str(base / f"{version}.xsd"),
        )
        out_path = GOLDEN_DIR / f"{version}.xml"
        out_path.write_text(xml, encoding="utf-8")
        print(f"wrote {out_path.relative_to(REPO_ROOT)} ({len(xml)} bytes)")


if __name__ == "__main__":
    main()
