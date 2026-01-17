#!/usr/bin/env python3
"""Generate XML example files for all pain001 versions."""

import csv
from pathlib import Path
from xml.etree.ElementTree import (  # nosec B405 - Safe: element creation only
    Element,
    ElementTree,
)

from pain001.xml.create_xml_v3 import create_xml_v3
from pain001.xml.create_xml_v4 import create_xml_v4
from pain001.xml.create_xml_v5 import create_xml_v5
from pain001.xml.create_xml_v6 import create_xml_v6
from pain001.xml.create_xml_v7 import create_xml_v7
from pain001.xml.create_xml_v8 import create_xml_v8
from pain001.xml.create_xml_v9 import create_xml_v9
from pain001.xml.create_xml_v10 import create_xml_v10
from pain001.xml.create_xml_v11 import create_xml_v11

versions = {
    "03": (create_xml_v3, "pain.001.001.03"),
    "04": (create_xml_v4, "pain.001.001.04"),
    "05": (create_xml_v5, "pain.001.001.05"),
    "06": (create_xml_v6, "pain.001.001.06"),
    "07": (create_xml_v7, "pain.001.001.07"),
    "08": (create_xml_v8, "pain.001.001.08"),
    "09": (create_xml_v9, "pain.001.001.09"),
    "10": (create_xml_v10, "pain.001.001.10"),
    "11": (create_xml_v11, "pain.001.001.11"),
}

for version, (create_func, _ns) in versions.items():
    try:
        template_dir = Path(f"pain001/templates/pain.001.001.{version}")
        csv_path = template_dir / "template.csv"
        output_path = template_dir / f"pain.001.001.{version}.xml"

        # Read CSV data
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            data = list(reader)[:2]  # Use first 2 rows

        # Create XML
        root = Element("Document")
        result = create_func(root, data)

        # Write to file
        tree = ElementTree(result)
        tree.write(str(output_path), encoding="utf-8", xml_declaration=True)
        print(f"✓ Created {output_path}")
    except Exception as e:
        print(f"✗ Failed to create version {version}: {e}")

print("\nAll XML example file generation attempts completed")
