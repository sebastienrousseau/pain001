# Copyright (C) 2023-2024 Sebastien Rousseau.
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


import unittest
import xml.etree.ElementTree as ET
from pain001.xml.create_xml_v3 import create_xml_v3
from pain001.xml.create_xml_v4 import create_xml_v4
from pain001.xml.create_xml_v5 import create_xml_v5
from pain001.xml.create_xml_v6 import create_xml_v6
from pain001.xml.create_xml_v7 import create_xml_v7
from pain001.xml.create_xml_v8 import create_xml_v8
from pain001.xml.create_xml_v9 import create_xml_v9
from pain001.xml.create_common_elements import (
    create_common_elements,
)


class TestXMLCreation(unittest.TestCase):
    def setUp(self):
        """
        Test setup
        """
        self.root = ET.Element("Root")
        self.row_v3 = {
            "id": "1",
            "date": "2023-03-10T15:30:47.000Z",
            "nb_of_txs": "2",
            "initiator_name": "Initiator",
            "initiator_street_name": "Street",
            "initiator_building_number": "1",
            "initiator_postal_code": "12345",
            "initiator_town_name": "Town",
            "initiator_country_code": "DE",
            "payment_id": "PID123",
            "payment_method": "pain.001.001.03",
            "batch_booking": "true",
            "requested_execution_date": "2023-05-21",
            "debtor_name": "Debtor",
            "debtor_street_name": "Street",
            "debtor_building_number": "1",
            "debtor_postal_code": "12345",
            "debtor_town_name": "Town",
            "debtor_country_code": "DE",
            "debtor_account_IBAN": "DE123456789",
            "debtor_agent_BIC": "DEUTDEFF",
            "charge_bearer": "SLEV",
            "transactions": [
                {
                    "payment_id": "PID123",
                    "payment_amount": "1500",
                    "payment_currency": "EUR",
                    "charge_bearer": "SLEV",
                    "creditor_agent_BIC": "NOLADE21KIE",
                    "creditor_name": "Creditor",
                    "creditor_street_name": "Street",
                    "creditor_building_number": "1",
                    "creditor_postal_code": "12345",
                    "creditor_town_name": "Town",
                    "creditor_country_code": "DE",
                    "creditor_account_IBAN": "DE123456789",
                    "purpose_code": "Code",
                    "reference_number": "123456789",
                    "reference_date": "2023-05-21",
                }
            ],
        }
        self.row_v4 = {
            "id": "ID001",
            "date": "2023-05-19",
            "nb_of_txs": "1",
            "initiator_name": "John Doe",
            "initiator_street": "Main Street",
            "initiator_building_number": "1",
            "initiator_postal_code": "12345",
            "initiator_town": "Anytown",
            "initiator_country": "US",
            "payment_information_id": "PI001",
            "payment_method": "TRF",
            "batch_booking": "true",
            "requested_execution_date": "2023-05-20",
            "debtor_name": "Jane Doe",
            "debtor_street": "Second Street",
            "debtor_building_number": "2",
            "debtor_postal_code": "54321",
            "debtor_town": "Othertown",
            "debtor_country": "US",
            "debtor_account_IBAN": "US123456789",
            "debtor_agent_BIC": "BANKUS33",
            "payment_instruction_id": "PI002",
            "payment_end_to_end_id": "E2E001",
            "payment_currency": "USD",
            "payment_amount": "100.00",
            "charge_bearer": "SLEV",
            "creditor_agent_BIC": "NOLADE21KIE",
            "creditor_name": "Creditor Name",
            "creditor_street": "Creditor Street",
            "creditor_building_number": "3",
            "creditor_postal_code": "67890",
            "creditor_town": "Creditor Town",
            "creditor_account_IBAN": "DE123456789",
            "purpose_code": "GDDS",
            "reference_number": "REF001",
            "reference_date": "2023-05-19",
        }
        self.row_v5 = {
            "id": "1",
            "date": "2023-03-10T15:30:47.000Z",
            "nb_of_txs": "2",
            "ctrl_sum": "3000",
            "initiator_name": "Initiator",
            "initiator_street_name": "Street",
            "initiator_building_number": "1",
            "initiator_postal_code": "12345",
            "initiator_town_name": "Town",
            "initiator_country": "DE",
            "ultimate_debtor_name": "Ultimate Debtor",
            "service_level_code": "SEPA",
            "payment_information_id": "PID123",
            "payment_id": "PID123",
            "payment_method": "pain.001.001.05",
            "batch_booking": "true",
            "requested_execution_date": "2023-05-21",
            "debtor_name": "Debtor",
            "debtor_street": "Street",
            "debtor_building_number": "1",
            "debtor_postal_code": "12345",
            "debtor_town": "Town",
            "debtor_country": "DE",
            "debtor_account_IBAN": "DE123456789",
            "debtor_agent_BIC": "DEUTDEFF",
            "charge_bearer": "SLEV",
            "payment_instruction_id": "PID123",
            "payment_end_to_end_id": "E2E123",
            "payment_currency": "EUR",
            "payment_amount": "1500",
            "creditor_name": "Creditor",
            "creditor_street": "Street",
            "creditor_building_number": "1",
            "creditor_postal_code": "12345",
            "creditor_town": "Town",
            "creditor_country": "DE",
            "creditor_account_IBAN": "DE123456789",
            "creditor_agent_BICFI": "NOLADE21KIE",
            "purpose_code": "GDDS",
            "reference_number": "RF123",
            "reference_date": "2023-03-10T15:30:47.000Z",
        }
        self.row_v6 = {
            "id": "2",
            "date": "2023-03-11T15:30:47.000Z",
            "nb_of_txs": "3",
            "ctrl_sum": "4500",
            "initiator_name": "Initiator 6",
            "initiator_street_name": "Street 6",
            "initiator_building_number": "6",
            "initiator_postal_code": "12346",
            "initiator_town_name": "Town 6",
            "initiator_country": "DE",
            "ultimate_debtor_name": "Ultimate Debtor 6",
            "service_level_code": "SEPA",
            "payment_information_id": "PID123",
            "payment_id": "PID123",
            "payment_method": "pain.001.001.06",
            "batch_booking": "true",
            "requested_execution_date": "2023-06-21",
            "debtor_name": "Debtor 6",
            "debtor_street": "Street 6",
            "debtor_building_number": "6",
            "debtor_postal_code": "12346",
            "debtor_town": "Town 6",
            "debtor_country": "DE",
            "debtor_account_IBAN": "DE123456780",
            "debtor_agent_name": "Agent",
            "debtor_agent_BIC": "DEUTDEFG",
            "charge_bearer": "SLEV",
            "payment_instruction_id": "PID123",
            "payment_end_to_end_id": "E2E124",
            "payment_currency": "USD",
            "payment_amount": "1600",
            "creditor_name": "Creditor 6",
            "creditor_street": "Street 6",
            "creditor_building_number": "6",
            "creditor_postal_code": "12346",
            "creditor_town": "Town 6",
            "creditor_country": "DE",
            "creditor_account_IBAN": "DE123456780",
            "creditor_agent_BICFI": "NOLADE21KIF",
            "creditor_agent_name": "Creditor Agent",
            "purpose_code": "GDDS",
            "reference_number": "RF124",
            "reference_date": "2023-03-11T15:30:47.000Z",
        }

        self.row_v7 = {
            "id": "3",
            "date": "2023-03-12T15:30:47.000Z",
            "nb_of_txs": "4",
            "ctrl_sum": "6000",
            "initiator_name": "Initiator 7",
            "initiator_street_name": "Street 7",
            "initiator_building_number": "7",
            "initiator_postal_code": "12347",
            "initiator_town_name": "Town 7",
            "initiator_country": "DE",
            "ultimate_debtor_name": "Ultimate Debtor 7",
            "service_level_code": "SEPA",
            "payment_information_id": "PID123",
            "payment_id": "PID123",
            "payment_method": "pain.001.001.07",
            "batch_booking": "true",
            "requested_execution_date": "2023-07-21",
            "debtor_name": "Debtor 7",
            "debtor_street": "Street 7",
            "debtor_building_number": "7",
            "debtor_postal_code": "12347",
            "debtor_town": "Town 7",
            "debtor_country": "DE",
            "debtor_account_IBAN": "DE123456781",
            "debtor_agent_name": "Agent",
            "debtor_agent_BIC": "DEUTDEFH",
            "charge_bearer": "SLEV",
            "payment_instruction_id": "PID123",
            "payment_end_to_end_id": "E2E125",
            "payment_currency": "GBP",
            "payment_amount": "1700",
            "creditor_name": "Creditor 7",
            "creditor_street": "Street 7",
            "creditor_building_number": "7",
            "creditor_postal_code": "12347",
            "creditor_town": "Town 7",
            "creditor_country": "DE",
            "creditor_account_IBAN": "DE123456781",
            "creditor_agent_BICFI": "NOLADE21KIG",
            "creditor_agent_name": "Creditor Agent",
            "purpose_code": "GDDS",
            "reference_number": "RF125",
            "reference_date": "2023-03-12T15:30:47.000Z",
        }

        self.row_v8 = {
            "id": "4",
            "date": "2023-03-13T15:30:47.000Z",
            "nb_of_txs": "5",
            "ctrl_sum": "7500",
            "initiator_name": "Initiator 8",
            "initiator_street_name": "Street 8",
            "initiator_building_number": "8",
            "initiator_postal_code": "12348",
            "initiator_town_name": "Town 8",
            "initiator_country": "DE",
            "ultimate_debtor_name": "Ultimate Debtor 8",
            "service_level_code": "SEPA",
            "payment_information_id": "PID123",
            "payment_id": "PID123",
            "payment_method": "pain.001.001.08",
            "batch_booking": "true",
            "requested_execution_date": "2023-08-21",
            "debtor_name": "Debtor 8",
            "debtor_street": "Street 8",
            "debtor_building_number": "8",
            "debtor_postal_code": "12348",
            "debtor_town": "Town 8",
            "debtor_country": "DE",
            "debtor_account_IBAN": "DE123456782",
            "debtor_agent_name": "Agent",
            "debtor_agent_BIC": "DEUTDEFH",
            "charge_bearer": "SLEV",
            "payment_instruction_id": "PID123",
            "payment_end_to_end_id": "E2E126",
            "payment_currency": "JPY",
            "payment_amount": "1800",
            "creditor_name": "Creditor 8",
            "creditor_street": "Street 8",
            "creditor_building_number": "8",
            "creditor_postal_code": "12348",
            "creditor_town": "Town 8",
            "creditor_country": "DE",
            "creditor_account_IBAN": "DE123456782",
            "creditor_agent_name": "Creditor Agent",
            "creditor_agent_BICFI": "NOLADE21KIH",
            "purpose_code": "GDDS",
            "reference_number": "RF126",
            "reference_date": "2023-03-13T15:30:47.000Z",
        }

        self.row_v9 = {
            "id": "1",
            "date": "2023-03-10T15:30:47.000Z",
            "nb_of_txs": "2",
            "initiator_name": "Initiator",
            "initiator_street_name": "Street",
            "initiator_building_number": "1",
            "initiator_postal_code": "12345",
            "initiator_town_name": "Town",
            "initiator_country_code": "DE",
            "payment_id": "PID123",
            "payment_method": "pain.001.001.09",  # Set to "pain.001.001.09"
            "batch_booking": "true",
            "requested_execution_date": "2023-05-21",
            "debtor_name": "Debtor",
            "debtor_street_name": "Street",
            "debtor_building_number": "1",
            "debtor_postal_code": "12345",
            "debtor_town_name": "Town",
            "debtor_country_code": "DE",
            "debtor_account_IBAN": "DE123456789",
            "debtor_agent_BIC": "DEUTDEFF",
            "charge_bearer": "SLEV",
            "transactions": [
                {
                    "payment_id": "PID123",
                    "payment_amount": "1500",
                    "payment_currency": "EUR",
                    "charge_bearer": "SLEV",
                    "creditor_agent_name": "Creditor Agent",
                    "creditor_agent_BIC": "NOLADE21KIE",
                    "creditor_name": "Creditor",
                    "creditor_street_name": "Street",
                    "creditor_building_number": "1",
                    "creditor_postal_code": "12345",
                    "creditor_town_name": "Town",
                    "creditor_country_code": "DE",
                    "creditor_account_IBAN": "DE123456789",
                    "purpose_code": "Code",
                    "reference_number": "123456789",
                    "reference_date": "2023-05-21",
                }
            ],
        }

        self.mapping = {
            "MsgId": "payment_id",
            "CreDtTm": "requested_execution_date",
            "NbOfTxs": "nb_of_txs",
            "PmtInfId": "payment_id",
            "PmtMtd": "payment_method",
        }

    def generate_xml(self):
        """
        Generate XML using create_xml_v3
        """
        create_xml_v3(self.root, [self.row_v3])
        create_xml_v4(self.root, [self.row_v4])
        create_xml_v5(self.root, [self.row_v5])
        create_xml_v6(self.root, [self.row_v6])
        create_xml_v7(self.root, [self.row_v7])
        create_xml_v8(self.root, [self.row_v8])
        create_xml_v9(self.root, [self.row_v9])

    def test_create_common_elements_v3(self):
        """
        Test create_common_elements for version 3
        """
        create_common_elements(self.root, self.row_v3, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.03")

    def test_create_xml_v4(self):
        """
        Test create_xml_v4
        """
        create_xml_v4(self.root, [self.row_v4])
        # Check if the root contains the expected elements and values
        self.assertTrue(self.root.find(".//CstmrCdtTrfInitn") is not None)

    def test_create_common_elements_v5(self):
        """
        Test create_common_elements for version 5
        """
        create_common_elements(self.root, self.row_v5, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.05")

    def test_create_common_elements_v6(self):
        """
        Test create_common_elements for version 6
        """
        create_common_elements(self.root, self.row_v6, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.06")

    def test_create_common_elements_v7(self):
        """
        Test create_common_elements for version 7
        """
        create_common_elements(self.root, self.row_v7, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.07")

    def test_create_common_elements_v8(self):
        """
        Test create_common_elements for version 8
        """
        create_common_elements(self.root, self.row_v8, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.08")

    def test_create_common_elements_v9(self):
        """
        Test create_common_elements for version 9
        """
        create_common_elements(self.root, self.row_v9, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.09")

    def test_create_xml_v3(self):
        """
        Test create_xml_v3
        """
        create_xml_v3(self.root, [self.row_v3])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v4(self):
        """
        Test create_xml_v4
        """
        create_xml_v4(self.root, [self.row_v4])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v5(self):
        """
        Test create_xml_v5
        """
        create_xml_v5(self.root, [self.row_v5])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v6(self):
        """
        Test create_xml_v6
        """
        create_xml_v6(self.root, [self.row_v6])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v7(self):
        """
        Test create_xml_v7
        """
        create_xml_v7(self.root, [self.row_v7])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v8(self):
        """
        Test create_xml_v8
        """
        create_xml_v8(self.root, [self.row_v8])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v9(self):
        """
        Test create_xml_v9
        """
        create_xml_v9(self.root, [self.row_v9])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")


if __name__ == "__main__":
    unittest.main()
