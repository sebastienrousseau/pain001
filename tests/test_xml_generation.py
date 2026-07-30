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

"""Tests for the live XML generation path (generate_xml)."""

import os
import unittest
from unittest.mock import patch

from pain001.xml.generate_xml import generate_xml
from pain001.xml.validate_via_xsd import validate_xml_string_via_xsd


class TestGenerateXMLFunction(unittest.TestCase):
    """Test the generate_xml function directly."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.test_template_path = "pain001/test_fixtures/template.xml"
        self.test_xsd_path = "pain001/test_fixtures/template.xsd"

        # Sample data for pain.001.001.03
        self.sample_data_v3 = [
            {
                "id": "1",
                "date": "2023-03-10T15:30:47.000Z",
                "nb_of_txs": "1",
                "initiator_name": "Test Company",
                "initiator_street_name": "Main Street",
                "initiator_building_number": "123",
                "initiator_postal_code": "12345",
                "initiator_town_name": "Test Town",
                "initiator_country_code": "DE",
                "payment_id": "PMT123",
                "payment_method": "TRF",
                "batch_booking": "true",
                "requested_execution_date": "2023-03-15",
                "debtor_name": "Debtor Corp",
                "debtor_street_name": "Debtor Street",
                "debtor_building_number": "456",
                "debtor_postal_code": "54321",
                "debtor_town_name": "Debtor Town",
                "debtor_country_code": "DE",
                "debtor_account_IBAN": "DE89370400440532013000",
                "debtor_agent_BIC": "COBADEFFXXX",
                "charge_bearer": "SLEV",
                "payment_amount": "1000.00",
                "payment_currency": "EUR",
                "creditor_agent_BIC": "COBADEFFXXX",
                "creditor_name": "Creditor Ltd",
                "creditor_street_name": "Creditor Street",
                "creditor_building_number": "789",
                "creditor_postal_code": "98765",
                "creditor_town_name": "Creditor Town",
                "creditor_country_code": "DE",
                "creditor_account_IBAN": "DE89370400440532013001",
                "purpose_code": "SALA",
                "reference_number": "REF123",
                "reference_date": "2023-03-10",
            }
        ]

    def _data_for_version(self, version: str) -> list:
        """Build a valid one-row dataset for any supported version."""
        row = dict(self.sample_data_v3[0])
        row.update(
            {
                "ctrl_sum": "1000.00",
                "initiator_country": "DE",
                "ultimate_debtor_name": "Ultimate Debtor",
                "payment_information_id": "PMT123",
                "service_level_code": "SEPA",
                "debtor_country": "DE",
                "debtor_agent_name": "Debtor Agent",
                "payment_instruction_id": "INST123",
                "payment_end_to_end_id": "E2E123",
                "creditor_country": "DE",
                "creditor_agent_BICFI": "COBADEFFXXX",
                "creditor_agent_name": "Creditor Agent",
                "remittance_information": "Payment for invoice",
            }
        )
        return [row]

    def test_generate_xml_with_empty_data(self) -> None:
        """Test that generate_xml raises ValueError when data is empty."""
        with self.assertRaises(ValueError):
            generate_xml(
                [],
                "pain.001.001.03",
                self.test_template_path,
                self.test_xsd_path,
            )

    def test_generate_xml_with_invalid_message_type(self) -> None:
        """Test that generate_xml raises ValueError with invalid message type."""
        with self.assertRaises(ValueError):
            generate_xml(
                self.sample_data_v3,
                "invalid.type",
                self.test_template_path,
                self.test_xsd_path,
            )

    def test_generate_xml_all_versions(self) -> None:
        """Test generate_xml writes a file for every supported version."""
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
            with self.subTest(version=version):
                output_path = f"pain001/test_fixtures/{version}.xml"
                try:
                    written = generate_xml(
                        self._data_for_version(version),
                        version,
                        self.test_template_path,
                        self.test_xsd_path,
                        output_path=output_path,
                    )
                    self.assertTrue(os.path.exists(written))
                finally:
                    if os.path.exists(output_path):
                        os.remove(output_path)

    def test_generate_xml_legacy_path_emits_deprecation(self) -> None:
        """Omitting output_path still works but warns."""
        output_path = "pain001/test_fixtures/pain.001.001.03.xml"
        try:
            with self.assertWarns(DeprecationWarning):
                written = generate_xml(
                    self.sample_data_v3,
                    "pain.001.001.03",
                    self.test_template_path,
                    self.test_xsd_path,
                )
            self.assertTrue(os.path.exists(written))
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    def test_generate_xml_unsupported_version(self) -> None:
        """Test generate_xml raises ValueError with unsupported version."""
        with self.assertRaises(ValueError):
            generate_xml(
                self.sample_data_v3,
                "pain.001.001.99",  # Unsupported version
                self.test_template_path,
                self.test_xsd_path,
            )

    def test_generate_xml_invalid_xsd_validation(self) -> None:
        """Test generate_xml with invalid XML that fails XSD validation."""
        with patch(
            "pain001.xml.generate_xml.validate_xml_string_via_xsd",
            autospec=True,
            return_value=False,
        ):
            with self.assertRaises(RuntimeError):
                generate_xml(
                    self.sample_data_v3,
                    "pain.001.001.03",
                    self.test_template_path,
                    self.test_xsd_path,
                )

            # Clean up if file was created
            output_path = "pain001/test_fixtures/pain.001.001.03.xml"
            if os.path.exists(output_path):
                os.remove(output_path)

    def test_validate_xml_string_via_xsd_parsing_exception(self) -> None:
        """Test exception handling in validate_xml_string_via_xsd with malformed XML."""
        malformed_xml = "<Document><invalid"
        result = validate_xml_string_via_xsd(malformed_xml, self.test_xsd_path)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
