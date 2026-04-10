from pathlib import Path

from pain001.csv.load_csv_data import load_csv_data
from pain001.xml.generate_xml import generate_xml_string


def _normalize_xml(xml_text: str) -> str:
    return "".join(xml_text.split())


def test_golden_xml_outputs_for_supported_versions() -> None:
    versions = [
        "pain.001.001.03",
        "pain.001.001.04",
        "pain.001.001.05",
        "pain.001.001.06",
        "pain.001.001.07",
        "pain.001.001.08",
        "pain.001.001.09",
        "pain.001.001.10",
        "pain.001.001.11",
        "pain.008.001.02",
    ]

    for version in versions:
        base = Path("pain001/templates") / version
        data = load_csv_data(str(base / "template.csv"))
        generated = generate_xml_string(
            data,
            version,
            str(base / "template.xml"),
            str(base / f"{version}.xsd"),
        )
        expected = (base / f"{version}.xml").read_text(encoding="utf-8")
        assert _normalize_xml(generated) == _normalize_xml(expected)

