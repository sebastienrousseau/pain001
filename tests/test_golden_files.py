"""Golden-file regression tests: byte-exact XML output per message version.

Regenerate fixtures after an intentional output change with:
    poetry run python scripts/generate_golden_files.py
"""

import csv
from pathlib import Path

import pytest

from pain001.constants import valid_xml_types
from pain001.xml.generate_xml import generate_xml_string

TEMPLATES_DIR = Path("pain001/templates")
GOLDEN_DIR = Path(__file__).parent / "golden"


def _load_template_rows(version: str) -> list[dict[str, str]]:
    csv_path = TEMPLATES_DIR / version / "template.csv"
    with open(csv_path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))[:2]


@pytest.mark.version_compat
@pytest.mark.parametrize("version", valid_xml_types)
def test_generated_xml_matches_golden(version: str) -> None:
    """Generated XML must match the committed golden fixture byte-for-byte."""
    base = TEMPLATES_DIR / version
    data = _load_template_rows(version)

    generated = generate_xml_string(
        data,
        version,
        str(base / "template.xml"),
        str(base / f"{version}.xsd"),
    )

    golden = (GOLDEN_DIR / f"{version}.xml").read_text(encoding="utf-8")
    assert generated == golden, (
        f"Output for {version} diverged from golden fixture. "
        "If the change is intentional, regenerate via "
        "scripts/generate_golden_files.py"
    )
