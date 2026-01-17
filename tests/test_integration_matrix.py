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

"""Comprehensive 4×9 integration test matrix for all ISO 20022 versions.

This module implements Issue #143: Integration Tests covering:
- 4 input sources: CSV, SQLite, JSON/JSONL, Parquet
- 9 ISO versions: pain.001.001.03 through pain.001.001.11
- Full workflow: Load → Generate XML → Validate XSD

Total test matrix: 36 combinations (4 sources × 9 versions)

Note: CSV/SQLite tests use version-specific template files (different schemas),
while JSON/Parquet tests use v03-compatible data (most widely compatible).
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pain001 import process_files


class TestIntegrationMatrix(unittest.TestCase):
    """Test all input sources across all ISO 20022 versions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test fixtures once for all tests."""
        cls.temp_dir = Path(tempfile.mkdtemp())
        cls.all_versions = [
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

        # Template base directory
        cls.templates_dir = Path("pain001/templates")

        # Create test data files for each format
        cls._create_test_data_files()

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up temporary files after all tests."""

        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)

    @classmethod
    def _create_test_data_files(cls) -> None:
        """Create test data files for JSON, JSONL, and Parquet formats.

        Note: CSV and SQLite files already exist in template directories.
        This method creates the new format files needed for comprehensive testing.
        """
        # Sample payment data (compatible with all versions)
        sample_data = [
            {
                "id": "1",
                "date": "2023-03-10T15:30:47.000Z",
                "nb_of_txs": "2",
                "initiator_name": "John Doe",
                "initiator_street_name": "John's Street",
                "initiator_building_number": "1",
                "initiator_postal_code": "12345",
                "initiator_town_name": "John's Town",
                "initiator_country_code": "DE",
                "payment_information_id": "Payment-Info-12345",
                "payment_method": "TRF",
                "batch_booking": "true",
                "requested_execution_date": "2023-03-12",
                "debtor_name": "Acme Corp",
                "debtor_street_name": "Acme Street",
                "debtor_building_number": "2",
                "debtor_postal_code": "67890",
                "debtor_town_name": "Acme Town",
                "debtor_country_code": "DE",
                "debtor_account_IBAN": "DE75512108001245126162",
                "debtor_agent_BIC": "BANKDEFFXXX",
                "charge_bearer": "SLEV",
                "payment_id": "PaymentID6789",
                "payment_amount": "150",
                "currency": "EUR",
                "payment_currency": "EUR",
                "ctrl_sum": "15000",
                "creditor_agent_BIC": "SPUEDE2UXXX",
                "creditor_name": "Global Tech",
                "creditor_street_name": "Global Street",
                "creditor_building_number": "3",
                "creditor_postal_code": "11223",
                "creditor_town_name": "Global Town",
                "creditor_country_code": "DE",
                "creditor_account_IBAN": "DE68210501700024690959",
                "purpose_code": "OTHR",
                "reference_number": "Invoice-98765",
                "reference_date": "2023-03-09",
                "service_level_code": "SEPA",
                "forwarding_agent_BIC": "SPUEDE2UXXX",
                "remittance_information": "Invoice-12345",
                "charge_account_IBAN": "CHARGE-IBAN-12345",
            },
            {
                "id": "2",
                "date": "2023-03-11T10:20:18.000Z",
                "nb_of_txs": "3",
                "initiator_name": "Jane Smith",
                "initiator_street_name": "Jane's Street",
                "initiator_building_number": "10",
                "initiator_postal_code": "67890",
                "initiator_town_name": "Jane's Town",
                "initiator_country_code": "DE",
                "payment_information_id": "Payment-Info-67890",
                "payment_method": "TRF",
                "batch_booking": "true",
                "requested_execution_date": "2023-03-14",
                "debtor_name": "Brown Industries",
                "debtor_street_name": "Brown Street",
                "debtor_building_number": "20",
                "debtor_postal_code": "45678",
                "debtor_town_name": "Brown Town",
                "debtor_country_code": "DE",
                "debtor_account_IBAN": "DE44500105175407324931",
                "debtor_agent_BIC": "BANKDEFFXXX",
                "charge_bearer": "SHAR",
                "payment_id": "PaymentID4321",
                "payment_amount": "300",
                "currency": "EUR",
                "payment_currency": "EUR",
                "ctrl_sum": "30000",
                "creditor_agent_BIC": "SPUEDE2UXXX",
                "creditor_name": "Green Energy",
                "creditor_street_name": "Green Street",
                "creditor_building_number": "30",
                "creditor_postal_code": "78901",
                "creditor_town_name": "Green Town",
                "creditor_country_code": "DE",
                "creditor_account_IBAN": "DE89370400440532013008",
                "purpose_code": "OTHR",
                "reference_number": "Invoice-12345",
                "reference_date": "2023-03-13",
                "service_level_code": "SEPA",
                "forwarding_agent_BIC": "SPUEDE2UXXX",
                "remittance_information": "Invoice-67890",
                "charge_account_IBAN": "CHARGE-IBAN-67890",
            },
        ]

        # Create JSON file (array format)
        cls.json_file = cls.temp_dir / "test_data.json"
        with open(cls.json_file, "w", encoding="utf-8") as f:
            json.dump(sample_data, f, indent=2)

        # Create JSONL file (JSON Lines format)
        cls.jsonl_file = cls.temp_dir / "test_data.jsonl"
        with open(cls.jsonl_file, "w", encoding="utf-8") as f:
            for record in sample_data:
                f.write(json.dumps(record) + "\n")

        # Create Parquet file (if pyarrow available)
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            # Convert to PyArrow table
            table = pa.Table.from_pylist(sample_data)
            cls.parquet_file = cls.temp_dir / "test_data.parquet"
            pq.write_table(table, cls.parquet_file)
            cls.has_parquet = True
        except ImportError:
            cls.parquet_file = None
            cls.has_parquet = False

    def tearDown(self) -> None:
        """Clean up generated XML files after each test.

        Note: Individual test methods now clean up their own XML files,
        so this is a safety net for any remaining files.
        """
        for version in self.all_versions:
            version_dir = self.templates_dir / version
            xml_file = version_dir / f"{version}.xml"
            if xml_file.exists():
                xml_file.unlink()

    # ========================================================================
    # CSV INPUT TESTS (9 versions)
    # ========================================================================

    def test_01_csv_input_pain_001_001_03(self) -> None:
        """Test CSV input with pain.001.001.03."""
        self._test_version_with_csv("pain.001.001.03")

    def test_02_csv_input_pain_001_001_04(self) -> None:
        """Test CSV input with pain.001.001.04."""
        self._test_version_with_csv("pain.001.001.04")

    def test_03_csv_input_pain_001_001_05(self) -> None:
        """Test CSV input with pain.001.001.05."""
        self._test_version_with_csv("pain.001.001.05")

    def test_04_csv_input_pain_001_001_06(self) -> None:
        """Test CSV input with pain.001.001.06."""
        self._test_version_with_csv("pain.001.001.06")

    def test_05_csv_input_pain_001_001_07(self) -> None:
        """Test CSV input with pain.001.001.07."""
        self._test_version_with_csv("pain.001.001.07")

    def test_06_csv_input_pain_001_001_08(self) -> None:
        """Test CSV input with pain.001.001.08."""
        self._test_version_with_csv("pain.001.001.08")

    def test_07_csv_input_pain_001_001_09(self) -> None:
        """Test CSV input with pain.001.001.09."""
        self._test_version_with_csv("pain.001.001.09")

    def test_08_csv_input_pain_001_001_10(self) -> None:
        """Test CSV input with pain.001.001.10."""
        self._test_version_with_csv("pain.001.001.10")

    def test_09_csv_input_pain_001_001_11(self) -> None:
        """Test CSV input with pain.001.001.11."""
        self._test_version_with_csv("pain.001.001.11")

    # ========================================================================
    # SQLITE INPUT TESTS (9 versions)
    # ========================================================================

    def test_10_sqlite_input_pain_001_001_03(self) -> None:
        """Test SQLite input with pain.001.001.03."""
        self._test_version_with_sqlite("pain.001.001.03")

    def test_11_sqlite_input_pain_001_001_04(self) -> None:
        """Test SQLite input with pain.001.001.04."""
        self._test_version_with_sqlite("pain.001.001.04")

    def test_12_sqlite_input_pain_001_001_05(self) -> None:
        """Test SQLite input with pain.001.001.05."""
        self._test_version_with_sqlite("pain.001.001.05")

    def test_13_sqlite_input_pain_001_001_06(self) -> None:
        """Test SQLite input with pain.001.001.06."""
        self._test_version_with_sqlite("pain.001.001.06")

    def test_14_sqlite_input_pain_001_001_07(self) -> None:
        """Test SQLite input with pain.001.001.07."""
        self._test_version_with_sqlite("pain.001.001.07")

    def test_15_sqlite_input_pain_001_001_08(self) -> None:
        """Test SQLite input with pain.001.001.08."""
        self._test_version_with_sqlite("pain.001.001.08")

    def test_16_sqlite_input_pain_001_001_09(self) -> None:
        """Test SQLite input with pain.001.001.09."""
        self._test_version_with_sqlite("pain.001.001.09")

    def test_17_sqlite_input_pain_001_001_10(self) -> None:
        """Test SQLite input with pain.001.001.10."""
        self._test_version_with_sqlite("pain.001.001.10")

    def test_18_sqlite_input_pain_001_001_11(self) -> None:
        """Test SQLite input with pain.001.001.11."""
        self._test_version_with_sqlite("pain.001.001.11")

    # ========================================================================
    # JSON INPUT TESTS (9 versions)
    # ========================================================================
    # Note: JSON/JSONL tests use version-specific template CSV files
    # to ensure proper field alignment with each schema version

    def test_19_json_input_pain_001_001_03(self) -> None:
        """Test JSON input with pain.001.001.03."""
        self._test_version_with_json_from_csv("pain.001.001.03")

    def test_20_json_input_pain_001_001_04(self) -> None:
        """Test JSON input with pain.001.001.04."""
        self._test_version_with_json_from_csv("pain.001.001.04")

    def test_21_json_input_pain_001_001_05(self) -> None:
        """Test JSON input with pain.001.001.05."""
        self._test_version_with_json_from_csv("pain.001.001.05")

    def test_22_json_input_pain_001_001_06(self) -> None:
        """Test JSON input with pain.001.001.06."""
        self._test_version_with_json_from_csv("pain.001.001.06")

    def test_23_json_input_pain_001_001_07(self) -> None:
        """Test JSON input with pain.001.001.07."""
        self._test_version_with_json_from_csv("pain.001.001.07")

    def test_24_json_input_pain_001_001_08(self) -> None:
        """Test JSON input with pain.001.001.08."""
        self._test_version_with_json_from_csv("pain.001.001.08")

    def test_25_json_input_pain_001_001_09(self) -> None:
        """Test JSON input with pain.001.001.09."""
        self._test_version_with_json_from_csv("pain.001.001.09")

    def test_26_json_input_pain_001_001_10(self) -> None:
        """Test JSON input with pain.001.001.10."""
        self._test_version_with_json_from_csv("pain.001.001.10")

    def test_27_json_input_pain_001_001_11(self) -> None:
        """Test JSON input with pain.001.001.11."""
        self._test_version_with_json_from_csv("pain.001.001.11")

    # ========================================================================
    # PARQUET INPUT TESTS (9 versions)
    # ========================================================================
    # Note: Parquet tests use version-specific template CSV files
    # to ensure proper field alignment with each schema version

    def test_28_parquet_input_pain_001_001_03(self) -> None:
        """Test Parquet input with pain.001.001.03."""
        if not self.has_parquet:
            self.skipTest("pyarrow not available")
        self._test_version_with_parquet_from_csv("pain.001.001.03")

    def test_29_parquet_input_pain_001_001_04(self) -> None:
        """Test Parquet input with pain.001.001.04."""
        if not self.has_parquet:
            self.skipTest("pyarrow not available")
        self._test_version_with_parquet_from_csv("pain.001.001.04")

    def test_30_parquet_input_pain_001_001_05(self) -> None:
        """Test Parquet input with pain.001.001.05."""
        if not self.has_parquet:
            self.skipTest("pyarrow not available")
        self._test_version_with_parquet_from_csv("pain.001.001.05")

    def test_31_parquet_input_pain_001_001_06(self) -> None:
        """Test Parquet input with pain.001.001.06."""
        if not self.has_parquet:
            self.skipTest("pyarrow not available")
        self._test_version_with_parquet_from_csv("pain.001.001.06")

    def test_32_parquet_input_pain_001_001_07(self) -> None:
        """Test Parquet input with pain.001.001.07."""
        if not self.has_parquet:
            self.skipTest("pyarrow not available")
        self._test_version_with_parquet_from_csv("pain.001.001.07")

    def test_33_parquet_input_pain_001_001_08(self) -> None:
        """Test Parquet input with pain.001.001.08."""
        if not self.has_parquet:
            self.skipTest("pyarrow not available")
        self._test_version_with_parquet_from_csv("pain.001.001.08")

    def test_34_parquet_input_pain_001_001_09(self) -> None:
        """Test Parquet input with pain.001.001.09."""
        if not self.has_parquet:
            self.skipTest("pyarrow not available")
        self._test_version_with_parquet_from_csv("pain.001.001.09")

    def test_35_parquet_input_pain_001_001_10(self) -> None:
        """Test Parquet input with pain.001.001.10."""
        if not self.has_parquet:
            self.skipTest("pyarrow not available")
        self._test_version_with_parquet_from_csv("pain.001.001.10")

    def test_36_parquet_input_pain_001_001_11(self) -> None:
        """Test Parquet input with pain.001.001.11."""
        if not self.has_parquet:
            self.skipTest("pyarrow not available")
        self._test_version_with_parquet_from_csv("pain.001.001.11")

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _test_version_with_csv(self, version: str) -> None:
        """Test a specific ISO version with CSV input.

        Args:
            version: ISO 20022 version (e.g., 'pain.001.001.03')
        """
        version_dir = self.templates_dir / version
        source_template = version_dir / "template.xml"
        source_schema = version_dir / f"{version}.xsd"
        source_data = version_dir / "template.csv"

        # Verify all required files exist
        self.assertTrue(
            source_template.exists(), f"Template missing for {version}"
        )
        self.assertTrue(
            source_schema.exists(), f"Schema missing for {version}"
        )
        self.assertTrue(
            source_data.exists(), f"CSV data missing for {version}"
        )

        # Copy to temp dir to avoid polluting/deleting source files
        temp_version_dir = self.temp_dir / version
        temp_version_dir.mkdir(exist_ok=True)

        template_file = temp_version_dir / "template.xml"
        schema_file = temp_version_dir / f"{version}.xsd"
        data_file = temp_version_dir / "template.csv"

        shutil.copy2(source_template, template_file)
        shutil.copy2(source_schema, schema_file)
        shutil.copy2(source_data, data_file)

        # Generate XML
        process_files(
            xml_message_type=version,
            xml_template_file_path=str(template_file),
            xsd_schema_file_path=str(schema_file),
            data_file_path=str(data_file),
        )

        # Verify XML generated and valid
        # XML is created in the temp directory
        xml_file = temp_version_dir / f"{version}.xml"
        self.assertTrue(
            xml_file.exists(), f"XML not generated for {version} with CSV"
        )
        self.assertGreater(
            xml_file.stat().st_size,
            1000,
            f"XML file too small for {version} with CSV",
        )

        # Verify XML contains expected structure
        content = xml_file.read_text()
        self._assert_xml_structure(content, version)

        # Clean up generated XML (not strictly necessary as temp dir is nuked, but good hygiene)
        xml_file.unlink()

    def _test_version_with_sqlite(self, version: str) -> None:
        """Test a specific ISO version with SQLite input.

        Args:
            version: ISO 20022 version (e.g., 'pain.001.001.03')
        """
        version_dir = self.templates_dir / version
        source_template = version_dir / "template.xml"
        source_schema = version_dir / f"{version}.xsd"
        source_data = version_dir / "template.db"

        # Verify all required files exist
        self.assertTrue(
            source_template.exists(), f"Template missing for {version}"
        )
        self.assertTrue(
            source_schema.exists(), f"Schema missing for {version}"
        )
        self.assertTrue(
            source_data.exists(), f"SQLite DB missing for {version}"
        )

        # Copy to temp dir to avoid polluting/deleting source files
        temp_version_dir = self.temp_dir / version
        temp_version_dir.mkdir(exist_ok=True)

        template_file = temp_version_dir / "template.xml"
        schema_file = temp_version_dir / f"{version}.xsd"
        data_file = temp_version_dir / "template.db"

        shutil.copy2(source_template, template_file)
        shutil.copy2(source_schema, schema_file)
        shutil.copy2(source_data, data_file)

        # Generate XML
        process_files(
            xml_message_type=version,
            xml_template_file_path=str(template_file),
            xsd_schema_file_path=str(schema_file),
            data_file_path=str(data_file),
        )

        # Verify XML generated and valid
        # XML is created in the temp directory
        xml_file = temp_version_dir / f"{version}.xml"
        self.assertTrue(
            xml_file.exists(), f"XML not generated for {version} with SQLite"
        )
        self.assertGreater(
            xml_file.stat().st_size,
            1000,
            f"XML file too small for {version} with SQLite",
        )

        # Verify XML contains expected structure
        content = xml_file.read_text()
        self._assert_xml_structure(content, version)

        # Clean up generated XML
        xml_file.unlink()

    def _test_version_with_json(self, version: str) -> None:
        """Test a specific ISO version with JSON input.

        Args:
            version: ISO 20022 version (e.g., 'pain.001.001.03')
        """
        version_dir = self.templates_dir / version
        source_template = version_dir / "template.xml"
        source_schema = version_dir / f"{version}.xsd"

        # Verify required files exist
        self.assertTrue(
            source_template.exists(), f"Template missing for {version}"
        )
        self.assertTrue(
            source_schema.exists(), f"Schema missing for {version}"
        )

        # Copy to temp dir to avoid polluting/deleting source files
        temp_version_dir = self.temp_dir / version
        temp_version_dir.mkdir(exist_ok=True)

        template_file = temp_version_dir / "template.xml"
        schema_file = temp_version_dir / f"{version}.xsd"

        shutil.copy2(source_template, template_file)
        shutil.copy2(source_schema, schema_file)

        # Generate XML
        process_files(
            xml_message_type=version,
            xml_template_file_path=str(template_file),
            xsd_schema_file_path=str(schema_file),
            data_file_path=str(self.json_file),
        )

        # Verify XML generated and valid
        # XML is created in the temp directory
        xml_file = temp_version_dir / f"{version}.xml"
        self.assertTrue(
            xml_file.exists(), f"XML not generated for {version} with JSON"
        )
        self.assertGreater(
            xml_file.stat().st_size,
            1000,
            f"XML file too small for {version} with JSON",
        )

        # Verify XML contains expected structure
        content = xml_file.read_text()
        self._assert_xml_structure(content, version)

        # Clean up generated XML
        xml_file.unlink()

    def _test_version_with_json_from_csv(self, version: str) -> None:
        """Test a specific ISO version with JSON input created from version-specific CSV.

        This method reads the version-specific CSV file, converts it to JSON,
        and then tests XML generation. This ensures proper field alignment
        with each schema version.

        Args:
            version: ISO 20022 version (e.g., 'pain.001.001.03')
        """
        import csv

        version_dir = self.templates_dir / version
        source_template = version_dir / "template.xml"
        source_schema = version_dir / f"{version}.xsd"
        source_csv = version_dir / "template.csv"

        # Verify required files exist
        self.assertTrue(
            source_template.exists(), f"Template missing for {version}"
        )
        self.assertTrue(
            source_schema.exists(), f"Schema missing for {version}"
        )
        self.assertTrue(source_csv.exists(), f"CSV missing for {version}")

        # Convert CSV to JSON in temp directory
        with open(source_csv, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            data = list(reader)

        json_file = self.temp_dir / f"{version}_data.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Copy to temp dir to avoid polluting/deleting source files
        temp_version_dir = self.temp_dir / version
        temp_version_dir.mkdir(exist_ok=True)

        template_file = temp_version_dir / "template.xml"
        schema_file = temp_version_dir / f"{version}.xsd"

        shutil.copy2(source_template, template_file)
        shutil.copy2(source_schema, schema_file)

        # Generate XML
        process_files(
            xml_message_type=version,
            xml_template_file_path=str(template_file),
            xsd_schema_file_path=str(schema_file),
            data_file_path=str(json_file),
        )

        # Verify XML generated and valid
        xml_file = temp_version_dir / f"{version}.xml"
        self.assertTrue(
            xml_file.exists(),
            f"XML not generated for {version} with JSON-from-CSV",
        )
        self.assertGreater(
            xml_file.stat().st_size,
            1000,
            f"XML file too small for {version} with JSON-from-CSV",
        )

        # Verify XML contains expected structure
        content = xml_file.read_text()
        self._assert_xml_structure(content, version)

        # Clean up generated XML and temp JSON
        xml_file.unlink()
        json_file.unlink()

    def _test_version_with_parquet(self, version: str) -> None:
        """Test a specific ISO version with Parquet input (generic data).

        Args:
            version: ISO 20022 version (e.g., 'pain.001.001.03')
        """
        version_dir = self.templates_dir / version
        source_template = version_dir / "template.xml"
        source_schema = version_dir / f"{version}.xsd"

        # Verify required files exist
        self.assertTrue(
            source_template.exists(), f"Template missing for {version}"
        )
        self.assertTrue(
            source_schema.exists(), f"Schema missing for {version}"
        )

        # Copy to temp dir to avoid polluting/deleting source files
        temp_version_dir = self.temp_dir / version
        temp_version_dir.mkdir(exist_ok=True)

        template_file = temp_version_dir / "template.xml"
        schema_file = temp_version_dir / f"{version}.xsd"

        shutil.copy2(source_template, template_file)
        shutil.copy2(source_schema, schema_file)

        # Generate XML
        process_files(
            xml_message_type=version,
            xml_template_file_path=str(template_file),
            xsd_schema_file_path=str(schema_file),
            data_file_path=str(self.parquet_file),
        )

        # Verify XML generated and valid
        # XML is created in the temp directory
        xml_file = temp_version_dir / f"{version}.xml"
        self.assertTrue(
            xml_file.exists(), f"XML not generated for {version} with Parquet"
        )
        self.assertGreater(
            xml_file.stat().st_size,
            1000,
            f"XML file too small for {version} with Parquet",
        )

        # Verify XML contains expected structure
        content = xml_file.read_text()
        self._assert_xml_structure(content, version)

        # Clean up generated XML
        xml_file.unlink()

    def _test_version_with_parquet_from_csv(self, version: str) -> None:
        """Test a specific ISO version with Parquet input created from version-specific CSV.

        This method reads the version-specific CSV file, converts it to Parquet,
        and then tests XML generation. This ensures proper field alignment
        with each schema version.

        Args:
            version: ISO 20022 version (e.g., 'pain.001.001.03')
        """
        import csv

        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow not available")

        version_dir = self.templates_dir / version
        source_template = version_dir / "template.xml"
        source_schema = version_dir / f"{version}.xsd"
        source_csv = version_dir / "template.csv"

        # Verify required files exist
        self.assertTrue(
            source_template.exists(), f"Template missing for {version}"
        )
        self.assertTrue(
            source_schema.exists(), f"Schema missing for {version}"
        )
        self.assertTrue(source_csv.exists(), f"CSV missing for {version}")

        # Convert CSV to Parquet in temp directory
        with open(source_csv, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            data = list(reader)

        # Convert to PyArrow table
        table = pa.Table.from_pylist(data)

        parquet_file = self.temp_dir / f"{version}_data.parquet"
        pq.write_table(table, parquet_file)

        # Copy to temp dir to avoid polluting/deleting source files
        temp_version_dir = self.temp_dir / version
        temp_version_dir.mkdir(exist_ok=True)

        template_file = temp_version_dir / "template.xml"
        schema_file = temp_version_dir / f"{version}.xsd"

        shutil.copy2(source_template, template_file)
        shutil.copy2(source_schema, schema_file)

        # Generate XML
        process_files(
            xml_message_type=version,
            xml_template_file_path=str(template_file),
            xsd_schema_file_path=str(schema_file),
            data_file_path=str(parquet_file),
        )

        # Verify XML generated and valid
        # XML is created in the temp directory
        xml_file = temp_version_dir / f"{version}.xml"
        self.assertTrue(
            xml_file.exists(),
            f"XML not generated for {version} with Parquet-from-CSV",
        )
        self.assertGreater(
            xml_file.stat().st_size,
            1000,
            f"XML file too small for {version} with Parquet-from-CSV",
        )

        # Verify XML contains expected structure
        content = xml_file.read_text()
        self._assert_xml_structure(content, version)

        # Clean up generated XML and temp Parquet
        xml_file.unlink()
        parquet_file.unlink()

    def _assert_xml_structure(self, content: str, version: str) -> None:
        """Verify XML contains expected ISO 20022 structure.

        Args:
            content: XML file content
            version: ISO 20022 version for context
        """
        # All versions should have these basic elements
        required_elements = [
            "<?xml",
            "Document",
            "CstmrCdtTrfInitn",
            "GrpHdr",
            "MsgId",
            "CreDtTm",
            "NbOfTxs",
            "InitgPty",
            "PmtInf",
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
                f"{version} XML missing required element: {element}",
            )


if __name__ == "__main__":
    unittest.main()
