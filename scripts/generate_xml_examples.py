#!/usr/bin/env python3
"""
Generate all 9 XML example files for XSD validation tests.

This script generates pain.001.001.03 through pain.001.001.11 XML example files
by loading the respective template.csv files and rendering them through the
Jinja2 templates with XSD validation.

Usage:
    poetry run python scripts/generate_xml_examples.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pain001.csv.load_csv_data import load_csv_data  # noqa: E402
from pain001.xml.generate_xml import generate_xml_string  # noqa: E402


def main():
    """Generate all XML example files."""
    versions = ["03", "04", "05", "06", "07", "08", "09", "10", "11"]

    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    print("Generating XML example files for XSD validation tests...")
    print("=" * 60)

    for ver in versions:
        version_str = f"pain.001.001.{ver}"
        template_dir = project_root / "pain001" / "templates" / version_str
        csv_path = template_dir / "template.csv"
        output_file = template_dir / f"{version_str}.xml"
        xsd_path = template_dir / f"{version_str}.xsd"

        print(f"\n[{version_str}]")
        print(f"  CSV: {csv_path.relative_to(project_root)}")
        print(f"  XSD: {xsd_path.relative_to(project_root)}")
        print(f"  Output: {output_file.relative_to(project_root)}")

        try:
            # Load CSV data
            payment_data = load_csv_data(str(csv_path))
            print(f"  ✓ Loaded {len(payment_data)} payment(s) from CSV")

            # Change to template directory for Jinja2
            orig_dir = os.getcwd()
            os.chdir(str(template_dir))

            # Generate XML
            xml_content = generate_xml_string(
                payment_data,
                version_str,
                xml_template_path="template.xml",
                xsd_schema_path=str(xsd_path.resolve()),
            )

            # Change back and write
            os.chdir(orig_dir)
            output_file.write_text(xml_content, encoding="utf-8")

            print(f"  ✓ Generated XML: {len(xml_content)} bytes")
            print(f"  ✓ Saved to: {output_file}")

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            os.chdir(orig_dir)
            return 1

    print("\n" + "=" * 60)
    print(f"✅ Successfully generated all {len(versions)} XML example files")
    print(
        "\nThese files enable XSD validation tests for all ISO 20022 versions."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
