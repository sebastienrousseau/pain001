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

"""Test cases for README.md code examples.

This module validates that all code examples shown in README.md
work correctly and produce expected results.
"""

import unittest
from pathlib import Path

import pain001


class TestReadmeExamples(unittest.TestCase):
    """Test all code examples from README.md."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.test_data_dir = Path("pain001/test_fixtures")
        self.csv_file = self.test_data_dir / "template.csv"
        self.xml_template = self.test_data_dir / "template.xml"
        self.xsd_schema = self.test_data_dir / "template.xsd"
        self.db_file = self.test_data_dir / "template.db"

    def tearDown(self) -> None:
        """Clean up generated files after tests."""
        # Generated files are created in pain001/test_fixtures directory
        # alongside the template
        generated_files = [
            self.test_data_dir / "pain.001.001.03.xml",
            self.test_data_dir / "pain.001.001.04.xml",
            self.test_data_dir / "pain.001.001.05.xml",
            self.test_data_dir / "pain.001.001.06.xml",
            self.test_data_dir / "pain.001.001.07.xml",
            self.test_data_dir / "pain.001.001.08.xml",
            self.test_data_dir / "pain.001.001.09.xml",
            self.test_data_dir / "pain.001.001.10.xml",
            self.test_data_dir / "pain.001.001.11.xml",
        ]
        for file in generated_files:
            if file.exists():
                file.unlink()

    def test_basic_import(self) -> None:
        """Test basic import example from README.

        Example:
        ```python
        import pain001
        ```
        """
        # Verify module imports correctly
        self.assertTrue(hasattr(pain001, "__version__"))
        self.assertIsInstance(pain001.__version__, str)

        # Verify key functions are available
        self.assertTrue(hasattr(pain001, "process_files"))

    def test_embedded_application_example(self) -> None:
        """Test embedded application example from README.

        Example shows using pain001 as a library within an application
        with programmatic API.
        """
        # Test using the process_files function directly
        pain001.process_files(
            "pain.001.001.03",
            str(self.xml_template),
            str(self.xsd_schema),
            str(self.csv_file),
        )

        # Verify XML file was generated
        generated_file = self.test_data_dir / "pain.001.001.03.xml"
        self.assertTrue(generated_file.exists())
        self.assertGreater(generated_file.stat().st_size, 0)

    def test_advanced_integration_example(self) -> None:
        """Test advanced integration example from README.

        Example shows programmatic usage with error handling and validation.
        """
        # Import required modules

        try:
            # Generate XML for pain.001.001.03
            pain001.process_files(
                "pain.001.001.03",
                str(self.xml_template),
                str(self.xsd_schema),
                str(self.csv_file),
            )

            # Verify the generated XML file
            generated_xml = self.test_data_dir / "pain.001.001.03.xml"
            self.assertTrue(
                generated_xml.exists(), "Generated XML file should exist"
            )

            # Verify file has content
            xml_size = generated_xml.stat().st_size
            self.assertGreater(
                xml_size, 0, "Generated XML file should not be empty"
            )

            # Validate against XSD schema
            from pain001.xml.validate_via_xsd import validate_via_xsd

            is_valid = validate_via_xsd(
                str(generated_xml), str(self.xsd_schema)
            )
            self.assertTrue(
                is_valid, "Generated XML should validate against XSD schema"
            )

        except Exception as e:
            self.fail(f"Advanced integration example failed: {e}")

    def test_validation_example(self) -> None:
        """Test validation example from README.

        Example shows using the XSD validator directly.
        """
        from pain001.xml.validate_via_xsd import validate_via_xsd

        # First generate an XML file
        pain001.process_files(
            "pain.001.001.03",
            str(self.xml_template),
            str(self.xsd_schema),
            str(self.csv_file),
        )

        # Now validate the generated XML (not the template)
        generated_xml = self.test_data_dir / "pain.001.001.03.xml"
        self.assertTrue(generated_xml.exists())

        is_valid = validate_via_xsd(str(generated_xml), str(self.xsd_schema))
        self.assertTrue(
            is_valid, "Generated XML should validate against schema"
        )

    def test_csv_processing_example(self) -> None:
        """Test CSV processing example from README.

        Example shows processing CSV data files.
        """

        # Process CSV file
        pain001.process_files(
            "pain.001.001.03",
            str(self.xml_template),
            str(self.xsd_schema),
            str(self.csv_file),
        )

        # Verify XML generation from CSV
        generated_file = self.test_data_dir / "pain.001.001.03.xml"
        self.assertTrue(
            generated_file.exists(), "CSV should generate XML file"
        )

        # Verify file content
        xml_content = generated_file.read_text()
        self.assertIn("<?xml", xml_content)
        self.assertIn("Document", xml_content)

    def test_sqlite_processing_example(self) -> None:
        """Test SQLite processing example from README.

        Example shows processing SQLite database files.
        """

        # Process SQLite database file
        pain001.process_files(
            "pain.001.001.03",
            str(self.xml_template),
            str(self.xsd_schema),
            str(self.db_file),
        )

        # Verify XML generation from database
        generated_file = self.test_data_dir / "pain.001.001.03.xml"
        self.assertTrue(
            generated_file.exists(), "Database should generate XML file"
        )

        # Verify file content
        xml_content = generated_file.read_text()
        self.assertIn("<?xml", xml_content)
        self.assertIn("Document", xml_content)

    def test_all_iso_versions_example(self) -> None:
        """Test that all 9 ISO 20022 versions can generate XML files.

        This validates the version comparison table from README.md.

        Note: This test only validates versions 03-04 with the default template.csv
        since later versions require additional fields (like initiator_country) that
        are not present in the basic test template. The full version tests are in
        test_pain001_vXX.py files which use appropriate test data for each version.
        """

        # Test versions that are compatible with the basic template.csv
        versions = [
            "pain.001.001.03",
            "pain.001.001.04",
        ]

        for version in versions:
            with self.subTest(version=version):
                pain001.process_files(
                    version,
                    str(self.xml_template),
                    str(self.xsd_schema),
                    str(self.csv_file),
                )

                # Verify XML file was created
                generated_file = self.test_data_dir / f"{version}.xml"
                self.assertTrue(
                    generated_file.exists(),
                    f"Version {version} should create XML file",
                )

                # Verify file has content
                self.assertGreater(
                    generated_file.stat().st_size,
                    0,
                    f"Version {version} XML should not be empty",
                )

        # Note: Comprehensive tests for all 9 versions exist in dedicated test files:
        # tests/test_pain001_v03.py through tests/test_pain001_v11.py


if __name__ == "__main__":
    unittest.main()
