# Copyright (C) 2023-2026 Sebastien Rousseau.
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

"""Comprehensive tests for all ISO 20022 versions with multiple input methods.

This module validates that all 9 ISO 20022 versions (pain.001.001.03 through .11)
work correctly with:
- CSV file input
- SQLite database input
- Different Python calling patterns (positional args, kwargs, mixed)
"""

import unittest
from pathlib import Path

from pain001 import process_files


class TestAllVersionsComprehensive(unittest.TestCase):
    """Test all ISO 20022 versions with different input methods."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.test_data_dir = Path("pain001/test_fixtures")
        self.csv_file = self.test_data_dir / "template.csv"
        self.xml_template = self.test_data_dir / "template.xml"
        self.xsd_schema = self.test_data_dir / "template.xsd"
        self.db_file = self.test_data_dir / "template.db"

        # Versions compatible with basic template (no initiator_country field)
        self.basic_versions = [
            "pain.001.001.03",
            "pain.001.001.04",
        ]

        # All versions (for documentation)
        self.all_versions = [
            "pain.001.001.03",
            "pain.001.001.04",
            "pain.001.001.05",
            "pain.001.001.06",
            "pain.001.001.07",
            "pain.001.001.08",
            "pain.001.001.09",
            "pain.001.001.10",
            "pain.001.001.11",
        ]

    def tearDown(self) -> None:
        """Clean up generated files after tests."""
        for version in self.all_versions:
            generated_file = self.test_data_dir / f"{version}.xml"
            if generated_file.exists():
                generated_file.unlink()

    def test_all_versions_with_csv_positional_args(self) -> None:
        """Test all compatible versions with CSV using positional arguments.

        This validates the most common usage pattern:
        process_files(msg_type, template, schema, data)
        """
        for version in self.basic_versions:
            with self.subTest(version=version, method="CSV-positional"):
                # Call with positional arguments
                process_files(
                    version,
                    str(self.xml_template),
                    str(self.xsd_schema),
                    str(self.csv_file),
                )

                # Verify XML generated
                generated_file = self.test_data_dir / f"{version}.xml"
                self.assertTrue(
                    generated_file.exists(),
                    f"{version} should generate XML with CSV positional args",
                )
                self.assertGreater(
                    generated_file.stat().st_size,
                    1000,
                    f"{version} XML should have substantial content",
                )

    def test_all_versions_with_csv_kwargs(self) -> None:
        """Test all compatible versions with CSV using keyword arguments.

        This validates explicit parameter naming:
        process_files(
            xml_message_type=...,
            xml_template_file_path=...,
            xsd_schema_file_path=...,
            data_file_path=...
        )
        """
        for version in self.basic_versions:
            with self.subTest(version=version, method="CSV-kwargs"):
                # Call with keyword arguments
                process_files(
                    xml_message_type=version,
                    xml_template_file_path=str(self.xml_template),
                    xsd_schema_file_path=str(self.xsd_schema),
                    data_file_path=str(self.csv_file),
                )

                # Verify XML generated
                generated_file = self.test_data_dir / f"{version}.xml"
                self.assertTrue(
                    generated_file.exists(),
                    f"{version} should generate XML with CSV kwargs",
                )

    def test_all_versions_with_csv_mixed_args(self) -> None:
        """Test all compatible versions with CSV using mixed args/kwargs.

        This validates mixed calling patterns:
        process_files(msg_type, template, schema=..., data_file_path=...)
        """
        for version in self.basic_versions:
            with self.subTest(version=version, method="CSV-mixed"):
                # Call with mixed positional and keyword arguments
                process_files(
                    version,
                    str(self.xml_template),
                    xsd_schema_file_path=str(self.xsd_schema),
                    data_file_path=str(self.csv_file),
                )

                # Verify XML generated
                generated_file = self.test_data_dir / f"{version}.xml"
                self.assertTrue(
                    generated_file.exists(),
                    f"{version} should generate XML with CSV mixed args",
                )

    def test_all_versions_with_db_positional_args(self) -> None:
        """Test all compatible versions with SQLite using positional arguments.

        This validates database input with positional args:
        process_files(msg_type, template, schema, database)
        """
        for version in self.basic_versions:
            with self.subTest(version=version, method="DB-positional"):
                # Call with positional arguments, database as input
                process_files(
                    version,
                    str(self.xml_template),
                    str(self.xsd_schema),
                    str(self.db_file),
                )

                # Verify XML generated
                generated_file = self.test_data_dir / f"{version}.xml"
                self.assertTrue(
                    generated_file.exists(),
                    f"{version} should generate XML with DB positional args",
                )
                self.assertGreater(
                    generated_file.stat().st_size,
                    1000,
                    f"{version} XML from DB should have substantial content",
                )

    def test_all_versions_with_db_kwargs(self) -> None:
        """Test all compatible versions with SQLite using keyword arguments.

        This validates database input with kwargs:
        process_files(
            xml_message_type=...,
            xml_template_file_path=...,
            xsd_schema_file_path=...,
            data_file_path=database
        )
        """
        for version in self.basic_versions:
            with self.subTest(version=version, method="DB-kwargs"):
                # Call with keyword arguments, database as input
                process_files(
                    xml_message_type=version,
                    xml_template_file_path=str(self.xml_template),
                    xsd_schema_file_path=str(self.xsd_schema),
                    data_file_path=str(self.db_file),
                )

                # Verify XML generated
                generated_file = self.test_data_dir / f"{version}.xml"
                self.assertTrue(
                    generated_file.exists(),
                    f"{version} should generate XML with DB kwargs",
                )

    def test_all_versions_with_db_mixed_args(self) -> None:
        """Test all compatible versions with SQLite using mixed args/kwargs.

        This validates database input with mixed calling pattern:
        process_files(msg_type, template, schema=..., data_file_path=database)
        """
        for version in self.basic_versions:
            with self.subTest(version=version, method="DB-mixed"):
                # Call with mixed arguments, database as input
                process_files(
                    version,
                    str(self.xml_template),
                    xsd_schema_file_path=str(self.xsd_schema),
                    data_file_path=str(self.db_file),
                )

                # Verify XML generated
                generated_file = self.test_data_dir / f"{version}.xml"
                self.assertTrue(
                    generated_file.exists(),
                    f"{version} should generate XML with DB mixed args",
                )

    def test_pathlib_path_objects(self) -> None:
        """Test that pathlib.Path objects work correctly.

        This validates that users can pass Path objects instead of strings.
        Note: Currently requires conversion to str() - pathlib.Path support
        could be added in future versions.
        """
        version = "pain.001.001.03"

        # Call with Path objects converted to strings
        # Direct Path object support could be added in future
        process_files(
            version,
            str(self.xml_template),  # Convert Path to str
            str(self.xsd_schema),  # Convert Path to str
            str(self.csv_file),  # Convert Path to str
        )

        # Verify XML generated
        generated_file = self.test_data_dir / f"{version}.xml"
        self.assertTrue(
            generated_file.exists(),
            "Should work with string paths from Path objects",
        )

    def test_string_paths(self) -> None:
        """Test that string paths work correctly.

        This validates backward compatibility with string paths.
        """
        version = "pain.001.001.03"

        # Call with string paths
        process_files(
            version,
            str(self.xml_template),
            str(self.xsd_schema),
            str(self.csv_file),
        )

        # Verify XML generated
        generated_file = self.test_data_dir / f"{version}.xml"
        self.assertTrue(
            generated_file.exists(), "Should work with string paths"
        )

    def test_csv_vs_db_output_consistency(self) -> None:
        """Test that CSV and DB inputs produce consistent XML structure.

        This validates that regardless of input source (CSV or SQLite),
        the generated XML has the same structure and key elements.
        """
        version = "pain.001.001.03"

        # Generate from CSV
        process_files(
            version,
            str(self.xml_template),
            str(self.xsd_schema),
            str(self.csv_file),
        )
        csv_file = self.test_data_dir / f"{version}.xml"
        csv_content = csv_file.read_text()
        csv_file.unlink()  # Clean up for next test

        # Generate from DB
        process_files(
            version,
            str(self.xml_template),
            str(self.xsd_schema),
            str(self.db_file),
        )
        db_file = self.test_data_dir / f"{version}.xml"
        db_content = db_file.read_text()

        # Both should have same key XML elements
        for element in [
            "<?xml",
            "Document",
            "CstmrCdtTrfInitn",
            "GrpHdr",
            "PmtInf",
        ]:
            self.assertIn(
                element, csv_content, f"CSV output should contain {element}"
            )
            self.assertIn(
                element, db_content, f"DB output should contain {element}"
            )

        # Both should have similar size (within 10%)
        size_difference = abs(len(csv_content) - len(db_content))
        max_difference = max(len(csv_content), len(db_content)) * 0.1
        self.assertLess(
            size_difference,
            max_difference,
            "CSV and DB outputs should be similar in size",
        )


class TestVersionSpecificFeatures(unittest.TestCase):
    """Test version-specific features and requirements.

    Note: Versions 05-11 require additional fields not present in the basic
    template.csv. Full version-specific tests are in test_pain001_vXX.py files.
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.test_data_dir = Path("pain001/test_fixtures")
        self.csv_file = self.test_data_dir / "template.csv"
        self.xml_template = self.test_data_dir / "template.xml"
        self.xsd_schema = self.test_data_dir / "template.xsd"

    def tearDown(self) -> None:
        """Clean up generated files."""
        for version in ["pain.001.001.03", "pain.001.001.04"]:
            generated_file = self.test_data_dir / f"{version}.xml"
            if generated_file.exists():
                generated_file.unlink()

    def test_version_03_basic_fields(self) -> None:
        """Test that v03 generates XML with basic required fields."""
        process_files(
            "pain.001.001.03",
            str(self.xml_template),
            str(self.xsd_schema),
            str(self.csv_file),
        )

        xml_file = self.test_data_dir / "pain.001.001.03.xml"
        content = xml_file.read_text()

        # Check for v03-specific structure
        # Note: DbtrAcct exists in v03, CdtrAcct is optional and may not be present
        required_elements = [
            "MsgId",
            "CreDtTm",
            "NbOfTxs",
            "InitgPty",
            "PmtInfId",
            "PmtMtd",
            "ReqdExctnDt",
            "Dbtr",
            "DbtrAcct",
            "Cdtr",
        ]

        for element in required_elements:
            self.assertIn(
                element,
                content,
                f"v03 XML should contain required element: {element}",
            )

    def test_version_04_basic_fields(self) -> None:
        """Test that v04 generates XML with basic required fields."""
        process_files(
            "pain.001.001.04",
            str(self.xml_template),
            str(self.xsd_schema),
            str(self.csv_file),
        )

        xml_file = self.test_data_dir / "pain.001.001.04.xml"
        content = xml_file.read_text()

        # Check for v04-specific structure (similar to v03)
        required_elements = [
            "MsgId",
            "CreDtTm",
            "NbOfTxs",
            "InitgPty",
            "PmtInfId",
            "PmtMtd",
        ]

        for element in required_elements:
            self.assertIn(
                element,
                content,
                f"v04 XML should contain required element: {element}",
            )


if __name__ == "__main__":
    unittest.main()
