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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Unit tests for XML string generation functionality.
Tests generate_xml_string() and validate_xml_string_via_xsd() for serverless/API use cases.
"""

import pytest

from pain001.xml.generate_xml import generate_xml_string
from pain001.xml.validate_via_xsd import validate_xml_string_via_xsd


class TestGenerateXmlString:
    """Test suite for generate_xml_string function."""

    @pytest.fixture
    def sample_payment_data_v03(self):
        """Sample payment data for pain.001.001.03."""
        return [
            {
                "id": "MSG001",
                "date": "2026-01-15T10:30:00",
                "nb_of_txs": "1",
                "initiator_name": "Test Corp",
                "initiator_street_name": "Main Street",
                "initiator_building_number": "123",
                "initiator_postal_code": "12345",
                "initiator_town_name": "TestCity",
                "initiator_country_code": "US",
                "payment_id": "PMT001",
                "payment_method": "TRF",
                "batch_booking": "false",
                "requested_execution_date": "2026-01-20",
                "debtor_name": "John Doe",
                "debtor_street_name": "Oak Avenue",
                "debtor_building_number": "456",
                "debtor_postal_code": "54321",
                "debtor_town_name": "DebtorCity",
                "debtor_country_code": "US",
                "debtor_account_IBAN": "GB33BUKB20201555555555",
                "debtor_agent_BIC": "BUKBGB22",
                "charge_bearer": "SLEV",
                "payment_amount": "100.00",
                "payment_currency": "EUR",
                "creditor_agent_BIC": "ABCDUS33",
                "creditor_name": "Jane Smith",
                "creditor_street_name": "Elm Street",
                "creditor_building_number": "789",
                "creditor_postal_code": "67890",
                "creditor_town_name": "CreditorCity",
                "creditor_country_code": "US",
                "creditor_account_IBAN": "FR1420041010050500013M02606",
                "purpose_code": "SALA",
                "reference_number": "REF12345",
                "reference_date": "2026-01-15",
            }
        ]

    def test_generate_xml_string_v03(self, sample_payment_data_v03, tmp_path):
        """Test generating XML string for pain.001.001.03."""
        template_path = "pain001/templates/pain.001.001.03/template.xml"
        xsd_path = "pain001/templates/pain.001.001.03/pain.001.001.03.xsd"

        xml_content = generate_xml_string(
            sample_payment_data_v03,
            "pain.001.001.03",
            template_path,
            xsd_path,
        )

        # Verify XML structure
        assert xml_content is not None
        assert isinstance(xml_content, str)
        assert len(xml_content) > 100
        assert "<Document" in xml_content
        assert "pain.001.001.03" in xml_content
        assert "MSG001" in xml_content
        assert "John Doe" in xml_content
        assert "Jane Smith" in xml_content

    def test_generate_xml_string_invalid_message_type(
        self, sample_payment_data_v03
    ):
        """Test generate_xml_string with invalid message type."""
        with pytest.raises(ValueError, match="Invalid XML message type"):
            generate_xml_string(
                sample_payment_data_v03,
                "pain.invalid.version",
                "template.xml",
                "schema.xsd",
            )

    def test_generate_xml_string_empty_data(self):
        """Test generate_xml_string with empty data list."""
        with pytest.raises(ValueError, match="No data to process"):
            generate_xml_string(
                [],
                "pain.001.001.03",
                "template.xml",
                "schema.xsd",
            )

    def test_generate_xml_string_all_versions(self):
        """Test generate_xml_string for all supported versions."""
        from pain001.csv.load_csv_data import load_csv_data

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
        ]

        for version in versions:
            template_path = f"pain001/templates/{version}/template.xml"
            xsd_path = f"pain001/templates/{version}/{version}.xsd"
            csv_path = f"pain001/templates/{version}/template.csv"

            # Load version-specific CSV data instead of using v03 fixture
            payment_data = load_csv_data(csv_path)

            xml_content = generate_xml_string(
                payment_data,
                version,
                template_path,
                xsd_path,
            )

            assert xml_content is not None
            assert version in xml_content


class TestValidateXmlStringViaXsd:
    """Test suite for validate_xml_string_via_xsd function."""

    def test_validate_simple_valid_xml(self, tmp_path):
        """Test validating a simple valid XML string."""
        # Create a minimal XSD schema
        xsd_content = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
    <xs:element name="Document">
        <xs:complexType>
            <xs:sequence>
                <xs:element name="Message" type="xs:string"/>
            </xs:sequence>
        </xs:complexType>
    </xs:element>
</xs:schema>"""

        xsd_file = tmp_path / "simple.xsd"
        xsd_file.write_text(xsd_content)

        # Valid XML
        valid_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Document>
    <Message>Test</Message>
</Document>"""

        result = validate_xml_string_via_xsd(valid_xml, str(xsd_file))
        assert result is True

    def test_validate_invalid_xml_structure(self, tmp_path):
        """Test validating XML with invalid structure."""
        # Create a minimal XSD schema
        xsd_content = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
    <xs:element name="Document">
        <xs:complexType>
            <xs:sequence>
                <xs:element name="Required" type="xs:string"/>
            </xs:sequence>
        </xs:complexType>
    </xs:element>
</xs:schema>"""

        xsd_file = tmp_path / "simple.xsd"
        xsd_file.write_text(xsd_content)

        # Invalid XML (missing required element)
        invalid_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Document>
    <Wrong>Test</Wrong>
</Document>"""

        result = validate_xml_string_via_xsd(invalid_xml, str(xsd_file))
        assert result is False

    def test_validate_malformed_xml(self, tmp_path):
        """Test validating malformed XML string."""
        xsd_file = tmp_path / "dummy.xsd"
        xsd_file.write_text(
            '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"/>'
        )

        malformed_xml = "This is not XML"

        result = validate_xml_string_via_xsd(malformed_xml, str(xsd_file))
        assert result is False

    def test_validate_xml_nonexistent_xsd(self):
        """Test validation with nonexistent XSD file."""
        xml_content = '<?xml version="1.0"?><Document/>'

        result = validate_xml_string_via_xsd(
            xml_content, "/nonexistent/schema.xsd"
        )
        assert result is False


class TestIntegrationXmlString:
    """Integration tests for XML string generation workflow."""

    def test_end_to_end_xml_string_generation(self, tmp_path):
        """Test complete workflow from data to validated XML string."""
        data = [
            {
                "id": "INTEG001",
                "date": "2026-01-15T10:30:00",
                "nb_of_txs": "1",
                "initiator_name": "Integration Test Corp",
                "initiator_street_name": "Test Street",
                "initiator_building_number": "1",
                "initiator_postal_code": "00000",
                "initiator_town_name": "TestTown",
                "initiator_country_code": "US",
                "payment_id": "PMT-INTEG-001",
                "payment_method": "TRF",
                "batch_booking": "false",
                "requested_execution_date": "2026-01-20",
                "debtor_name": "Integration Debtor",
                "debtor_street_name": "Debtor St",
                "debtor_building_number": "2",
                "debtor_postal_code": "11111",
                "debtor_town_name": "DebtorTown",
                "debtor_country_code": "US",
                "debtor_account_IBAN": "GB33BUKB20201555555555",
                "debtor_agent_BIC": "BUKBGB22",
                "charge_bearer": "SLEV",
                "payment_amount": "500.00",
                "payment_currency": "EUR",
                "creditor_agent_BIC": "ABCDUS33",
                "creditor_name": "Integration Creditor",
                "creditor_street_name": "Creditor Ave",
                "creditor_building_number": "3",
                "creditor_postal_code": "22222",
                "creditor_town_name": "CreditorTown",
                "creditor_country_code": "US",
                "creditor_account_IBAN": "FR1420041010050500013M02606",
                "purpose_code": "SALA",
                "reference_number": "REF-INTEG-12345",
                "reference_date": "2026-01-15",
            }
        ]

        template_path = "pain001/templates/pain.001.001.03/template.xml"
        xsd_path = "pain001/templates/pain.001.001.03/pain.001.001.03.xsd"

        # Generate XML string
        xml_content = generate_xml_string(
            data, "pain.001.001.03", template_path, xsd_path
        )

        # Verify content
        assert "INTEG001" in xml_content
        assert "Integration Test Corp" in xml_content
        assert "Integration Debtor" in xml_content
        assert "Integration Creditor" in xml_content
        assert "PMT-INTEG-001" in xml_content
        assert "500.00" in xml_content

        # Verify it can be re-validated
        is_valid = validate_xml_string_via_xsd(xml_content, xsd_path)
        assert is_valid is True

    def test_xml_string_consistency_with_file_generation(self, tmp_path):
        """Test that string generation produces same structure as file generation."""
        from pain001.xml.generate_xml import generate_xml

        data = [
            {
                "id": "CONSIST001",
                "date": "2026-01-15T10:30:00",
                "nb_of_txs": "1",
                "initiator_name": "Consistency Test",
                "initiator_street_name": "Main St",
                "initiator_building_number": "100",
                "initiator_postal_code": "10000",
                "initiator_town_name": "City",
                "initiator_country_code": "US",
                "payment_id": "PMT-CONSIST",
                "payment_method": "TRF",
                "batch_booking": "false",
                "requested_execution_date": "2026-01-20",
                "debtor_name": "Debtor Name",
                "debtor_street_name": "D St",
                "debtor_building_number": "200",
                "debtor_postal_code": "20000",
                "debtor_town_name": "D City",
                "debtor_country_code": "US",
                "debtor_account_IBAN": "GB33BUKB20201555555555",
                "debtor_agent_BIC": "BUKBGB22",
                "charge_bearer": "SLEV",
                "payment_amount": "250.00",
                "payment_currency": "EUR",
                "creditor_agent_BIC": "ABCDUS33",
                "creditor_name": "Creditor Name",
                "creditor_street_name": "C St",
                "creditor_building_number": "300",
                "creditor_postal_code": "30000",
                "creditor_town_name": "C City",
                "creditor_country_code": "US",
                "creditor_account_IBAN": "FR1420041010050500013M02606",
                "purpose_code": "SALA",
                "reference_number": "REF-CONSIST",
                "reference_date": "2026-01-15",
            }
        ]

        template_path = "pain001/templates/pain.001.001.03/template.xml"
        xsd_path = "pain001/templates/pain.001.001.03/pain.001.001.03.xsd"

        # Generate string version
        xml_string = generate_xml_string(
            data, "pain.001.001.03", template_path, xsd_path
        )

        # Generate file version
        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Copy template files to tmp directory
            import shutil

            template_src = "pain001/templates/pain.001.001.03"
            if os.path.exists(template_src):
                shutil.copytree(
                    template_src,
                    str(tmp_path / "pain001/templates/pain.001.001.03"),
                    dirs_exist_ok=True,
                )

                os.chdir(
                    old_cwd
                )  # Go back to original directory for generate_xml
                generate_xml(
                    data,
                    "pain.001.001.03",
                    f"{tmp_path}/pain001/templates/pain.001.001.03/template.xml",
                    f"{tmp_path}/pain001/templates/pain.001.001.03/pain.001.001.03.xsd",
                )

                # Find generated file
                generated_files = list(
                    tmp_path.glob("**/pain.001.001.03_*.xml")
                )
                assert len(generated_files) > 0, "No XML file was generated"

                with open(generated_files[0], encoding="utf-8") as f:
                    xml_file_content = f.read()

                # Both should contain same key elements
                assert "CONSIST001" in xml_string
                assert "CONSIST001" in xml_file_content
                assert "Consistency Test" in xml_string
                assert "Consistency Test" in xml_file_content
                assert "250.00" in xml_string
                assert "250.00" in xml_file_content
        finally:
            os.chdir(old_cwd)
