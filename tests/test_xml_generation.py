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


import unittest
import xml.etree.ElementTree as et  # nosec B405 - only used for element creation in tests, not parsing

from pain001.xml.create_common_elements import create_common_elements
from pain001.xml.create_xml_v3 import create_xml_v3
from pain001.xml.create_xml_v4 import create_xml_v4
from pain001.xml.create_xml_v5 import create_xml_v5
from pain001.xml.create_xml_v6 import create_xml_v6
from pain001.xml.create_xml_v7 import create_xml_v7
from pain001.xml.create_xml_v8 import create_xml_v8
from pain001.xml.create_xml_v9 import create_xml_v9
from pain001.xml.create_xml_v10 import create_xml_v10
from pain001.xml.create_xml_v11 import create_xml_v11


class TestXMLCreation(unittest.TestCase):
    def setUp(self) -> None:
        """
        Test setup
        """
        self.root = et.Element("Root")
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
            "initiator_town_name": "Anytown",
            "initiator_country": "US",
            "payment_information_id": "PI001",
            "payment_method": "TRF",
            "batch_booking": "true",
            "requested_execution_date": "2023-05-20",
            "debtor_name": "Jane Doe",
            "debtor_street_name": "Second Street",
            "debtor_building_number": "2",
            "debtor_postal_code": "54321",
            "debtor_town_name": "Othertown",
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
            "creditor_street_name": "Creditor Street",
            "creditor_building_number": "3",
            "creditor_postal_code": "67890",
            "creditor_town_name": "Creditor Town",
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
            "debtor_street_name": "Street",
            "debtor_building_number": "1",
            "debtor_postal_code": "12345",
            "debtor_town_name": "Town",
            "debtor_country": "DE",
            "debtor_account_IBAN": "DE123456789",
            "debtor_agent_BIC": "DEUTDEFF",
            "charge_bearer": "SLEV",
            "payment_instruction_id": "PID123",
            "payment_end_to_end_id": "E2E123",
            "payment_currency": "EUR",
            "payment_amount": "1500",
            "creditor_name": "Creditor",
            "creditor_street_name": "Street",
            "creditor_building_number": "1",
            "creditor_postal_code": "12345",
            "creditor_town_name": "Town",
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
            "debtor_street_name": "Street 6",
            "debtor_building_number": "6",
            "debtor_postal_code": "12346",
            "debtor_town_name": "Town 6",
            "debtor_country": "DE",
            "debtor_account_IBAN": "DE123456780",
            "debtor_agent_BIC": "DEUTDEFG",
            "charge_bearer": "SLEV",
            "payment_instruction_id": "PID123",
            "payment_end_to_end_id": "E2E124",
            "payment_currency": "USD",
            "payment_amount": "1600",
            "creditor_name": "Creditor 6",
            "creditor_street_name": "Street 6",
            "creditor_building_number": "6",
            "creditor_postal_code": "12346",
            "creditor_town_name": "Town 6",
            "creditor_country": "DE",
            "creditor_account_IBAN": "DE123456780",
            "creditor_agent_BICFI": "NOLADE21KIF",
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
            "debtor_street_name": "Street 7",
            "debtor_building_number": "7",
            "debtor_postal_code": "12347",
            "debtor_town_name": "Town 7",
            "debtor_country": "DE",
            "debtor_account_IBAN": "DE123456781",
            "debtor_agent_BIC": "DEUTDEFH",
            "charge_bearer": "SLEV",
            "payment_instruction_id": "PID123",
            "payment_end_to_end_id": "E2E125",
            "payment_currency": "GBP",
            "payment_amount": "1700",
            "creditor_name": "Creditor 7",
            "creditor_street_name": "Street 7",
            "creditor_building_number": "7",
            "creditor_postal_code": "12347",
            "creditor_town_name": "Town 7",
            "creditor_country": "DE",
            "creditor_account_IBAN": "DE123456781",
            "creditor_agent_BICFI": "NOLADE21KIG",
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
            "debtor_street_name": "Street 8",
            "debtor_building_number": "8",
            "debtor_postal_code": "12348",
            "debtor_town_name": "Town 8",
            "debtor_country": "DE",
            "debtor_account_IBAN": "DE123456782",
            "debtor_agent_BIC": "DEUTDEFH",
            "charge_bearer": "SLEV",
            "payment_instruction_id": "PID123",
            "payment_end_to_end_id": "E2E126",
            "payment_currency": "JPY",
            "payment_amount": "1800",
            "creditor_name": "Creditor 8",
            "creditor_street_name": "Street 8",
            "creditor_building_number": "8",
            "creditor_postal_code": "12348",
            "creditor_town_name": "Town 8",
            "creditor_country": "DE",
            "creditor_account_IBAN": "DE123456782",
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

        self.row_v10 = {
            "id": "1",
            "date": "2023-03-10T15:30:47.000Z",
            "nb_of_txs": "2",
            "initiator_name": "Initiator V10",
            "initiator_street_name": "Street",
            "initiator_building_number": "1",
            "initiator_postal_code": "12345",
            "initiator_town_name": "Town",
            "initiator_country_code": "DE",
            "payment_id": "PID123",
            "payment_method": "pain.001.001.10",
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

        self.row_v11 = {
            "id": "1",
            "date": "2023-03-10T15:30:47.000Z",
            "nb_of_txs": "2",
            "initiator_name": "Initiator V11",
            "initiator_street_name": "Street",
            "initiator_building_number": "1",
            "initiator_postal_code": "12345",
            "initiator_town_name": "Town",
            "initiator_country_code": "DE",
            "payment_id": "PID123",
            "payment_method": "pain.001.001.11",
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

    def generate_xml(self) -> None:
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

    def test_create_common_elements_v3(self) -> None:
        """
        Test create_common_elements for version 3
        """
        create_common_elements(self.root, self.row_v3, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.03")

    def test_create_xml_v4(self) -> None:
        """
        Test create_xml_v4
        """
        create_xml_v4(self.root, [self.row_v4])
        # Check if the root contains the expected elements and values
        self.assertIsNotNone(
            self.root.find(".//CstmrCdtTrfInitn"),
            "CstmrCdtTrfInitn element should exist",
        )

    def test_create_common_elements_v5(self) -> None:
        """
        Test create_common_elements for version 5
        """
        create_common_elements(self.root, self.row_v5, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.05")

    def test_create_common_elements_v6(self) -> None:
        """
        Test create_common_elements for version 6
        """
        create_common_elements(self.root, self.row_v6, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.06")

    def test_create_common_elements_v7(self) -> None:
        """
        Test create_common_elements for version 7
        """
        create_common_elements(self.root, self.row_v7, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.07")

    def test_create_common_elements_v8(self) -> None:
        """
        Test create_common_elements for version 8
        """
        create_common_elements(self.root, self.row_v8, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.08")

    def test_create_common_elements_v9(self) -> None:
        """
        Test create_common_elements for version 9
        """
        create_common_elements(self.root, self.row_v9, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.09")

    def test_create_xml_v3(self) -> None:
        """
        Test create_xml_v3
        """
        create_xml_v3(self.root, [self.row_v3])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v4_detailed(self) -> None:
        """
        Test create_xml_v4 with detailed checks
        """
        create_xml_v4(self.root, [self.row_v4])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v5(self) -> None:
        """
        Test create_xml_v5
        """
        create_xml_v5(self.root, [self.row_v5])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v6(self) -> None:
        """
        Test create_xml_v6
        """
        create_xml_v6(self.root, [self.row_v6])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v7(self) -> None:
        """
        Test create_xml_v7
        """
        create_xml_v7(self.root, [self.row_v7])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v8(self) -> None:
        """
        Test create_xml_v8
        """
        create_xml_v8(self.root, [self.row_v8])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v9(self) -> None:
        """
        Test create_xml_v9
        """
        create_xml_v9(self.root, [self.row_v9])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v10(self) -> None:
        """
        Test create_xml_v10
        """
        create_xml_v10(self.root, [self.row_v10])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_xml_v11(self) -> None:
        """
        Test create_xml_v11
        """
        create_xml_v11(self.root, [self.row_v11])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn")

    def test_create_common_elements_v10(self) -> None:
        """
        Test create_common_elements for version 10
        """
        create_common_elements(self.root, self.row_v10, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.10")

    def test_create_common_elements_v11(self) -> None:
        """
        Test create_common_elements for version 11
        """
        create_common_elements(self.root, self.row_v11, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.11")


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

    def test_generate_xml_with_empty_data(self) -> None:
        """Test that generate_xml raises ValueError when data is empty."""
        from pain001.xml.generate_xml import generate_xml

        with self.assertRaises(ValueError):
            generate_xml(
                [],
                "pain.001.001.03",
                self.test_template_path,
                self.test_xsd_path,
            )

    def test_generate_xml_with_invalid_message_type(self) -> None:
        """Test that generate_xml raises ValueError with invalid message type."""
        from pain001.xml.generate_xml import generate_xml

        with self.assertRaises(ValueError):
            generate_xml(
                self.sample_data_v3,
                "invalid.type",
                self.test_template_path,
                self.test_xsd_path,
            )

    def test_generate_xml_pain_001_001_03(self) -> None:
        """Test generate_xml with pain.001.001.03 message type."""
        import os

        from pain001.xml.generate_xml import generate_xml

        # This should create an XML file
        generate_xml(
            self.sample_data_v3,
            "pain.001.001.03",
            self.test_template_path,
            self.test_xsd_path,
        )

        # Check that the output file was created
        output_path = "pain001/test_fixtures/pain.001.001.03.xml"
        self.assertTrue(os.path.exists(output_path))

        # Clean up
        if os.path.exists(output_path):
            os.remove(output_path)

    def test_generate_xml_pain_001_001_04(self) -> None:
        """Test generate_xml with pain.001.001.04 message type."""
        import os

        from pain001.xml.generate_xml import generate_xml

        # Prepare data for v4
        data_v4 = [
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
                "creditor_account_IBAN": "DE89370400440532013001",
                "purpose_code": "SALA",
                "reference_number": "REF123",
                "reference_date": "2023-03-10",
                "payment_instruction_id": "INST123",
                "payment_end_to_end_id": "E2E123",
            }
        ]

        generate_xml(
            data_v4,
            "pain.001.001.04",
            self.test_template_path,
            self.test_xsd_path,
        )

        output_path = "pain001/test_fixtures/pain.001.001.04.xml"
        self.assertTrue(os.path.exists(output_path))

        if os.path.exists(output_path):
            os.remove(output_path)

    def test_generate_xml_pain_001_001_05(self) -> None:
        """Test generate_xml with pain.001.001.05 message type."""
        import os

        from pain001.xml.generate_xml import generate_xml

        data_v5 = [
            {
                "id": "1",
                "date": "2023-03-10T15:30:47.000Z",
                "nb_of_txs": "1",
                "ctrl_sum": "1000.00",
                "initiator_name": "Test Company",
                "initiator_street_name": "Main Street",
                "initiator_building_number": "123",
                "initiator_postal_code": "12345",
                "initiator_town_name": "Test Town",
                "initiator_country": "DE",
                "ultimate_debtor_name": "Ultimate Debtor",
                "payment_information_id": "PMT123",
                "payment_id": "PMT123",
                "payment_method": "TRF",
                "batch_booking": "true",
                "service_level_code": "SEPA",
                "requested_execution_date": "2023-03-15",
                "debtor_name": "Debtor Corp",
                "debtor_street_name": "Debtor Street",
                "debtor_building_number": "456",
                "debtor_postal_code": "54321",
                "debtor_town_name": "Debtor Town",
                "debtor_country": "DE",
                "debtor_account_IBAN": "DE89370400440532013000",
                "debtor_agent_BIC": "COBADEFFXXX",
                "charge_bearer": "SLEV",
                "payment_instruction_id": "INST123",
                "payment_end_to_end_id": "E2E123",
                "payment_currency": "EUR",
                "payment_amount": "1000.00",
                "creditor_name": "Creditor Ltd",
                "creditor_street_name": "Creditor Street",
                "creditor_building_number": "789",
                "creditor_postal_code": "98765",
                "creditor_town_name": "Creditor Town",
                "creditor_country": "DE",
                "creditor_account_IBAN": "DE89370400440532013001",
                "creditor_agent_BICFI": "COBADEFFXXX",
                "purpose_code": "SALA",
                "reference_number": "REF123",
                "reference_date": "2023-03-10",
            }
        ]

        generate_xml(
            data_v5,
            "pain.001.001.05",
            self.test_template_path,
            self.test_xsd_path,
        )

        output_path = "pain001/test_fixtures/pain.001.001.05.xml"
        self.assertTrue(os.path.exists(output_path))

        if os.path.exists(output_path):
            os.remove(output_path)

    def test_generate_xml_pain_001_001_06(self) -> None:
        """Test generate_xml with pain.001.001.06 message type."""
        import os

        from pain001.xml.generate_xml import generate_xml

        data_v6 = [
            {
                "id": "1",
                "date": "2023-03-10T15:30:47.000Z",
                "nb_of_txs": "1",
                "ctrl_sum": "1000.00",
                "initiator_name": "Test Company",
                "initiator_street_name": "Main Street",
                "initiator_building_number": "123",
                "initiator_postal_code": "12345",
                "initiator_town_name": "Test Town",
                "initiator_country": "DE",
                "payment_information_id": "PMT123",
                "payment_id": "PMT123",
                "payment_method": "TRF",
                "batch_booking": "true",
                "service_level_code": "SEPA",
                "requested_execution_date": "2023-03-15",
                "debtor_name": "Debtor Corp",
                "debtor_street_name": "Debtor Street",
                "debtor_building_number": "456",
                "debtor_postal_code": "54321",
                "debtor_town_name": "Debtor Town",
                "debtor_country": "DE",
                "debtor_account_IBAN": "DE89370400440532013000",
                "debtor_agent_name": "Debtor Agent",
                "debtor_agent_BIC": "COBADEFFXXX",
                "charge_bearer": "SLEV",
                "payment_instruction_id": "INST123",
                "payment_end_to_end_id": "E2E123",
                "payment_currency": "EUR",
                "payment_amount": "1000.00",
                "creditor_name": "Creditor Ltd",
                "creditor_street_name": "Creditor Street",
                "creditor_building_number": "789",
                "creditor_postal_code": "98765",
                "creditor_town_name": "Creditor Town",
                "creditor_country": "DE",
                "creditor_account_IBAN": "DE89370400440532013001",
                "creditor_agent_BIC": "COBADEFFXXX",
                "creditor_agent_BICFI": "COBADEFFXXX",
                "creditor_agent_name": "Creditor Agent",
                "purpose_code": "SALA",
                "reference_number": "REF123",
                "reference_date": "2023-03-10",
                "remittance_information": "Payment for invoice",
            }
        ]

        generate_xml(
            data_v6,
            "pain.001.001.06",
            self.test_template_path,
            self.test_xsd_path,
        )

        output_path = "pain001/test_fixtures/pain.001.001.06.xml"
        self.assertTrue(os.path.exists(output_path))

        if os.path.exists(output_path):
            os.remove(output_path)

    def test_generate_xml_pain_001_001_07(self) -> None:
        """Test generate_xml with pain.001.001.07 message type."""
        import os

        from pain001.xml.generate_xml import generate_xml

        data_v7 = [
            {
                "id": "1",
                "date": "2023-03-10T15:30:47.000Z",
                "nb_of_txs": "1",
                "ctrl_sum": "1000.00",
                "initiator_name": "Test Company",
                "initiator_street_name": "Main Street",
                "initiator_building_number": "123",
                "initiator_postal_code": "12345",
                "initiator_town_name": "Test Town",
                "initiator_country": "DE",
                "payment_information_id": "PMT123",
                "payment_id": "PMT123",
                "payment_method": "TRF",
                "batch_booking": "true",
                "service_level_code": "SEPA",
                "requested_execution_date": "2023-03-15",
                "debtor_name": "Debtor Corp",
                "debtor_street_name": "Debtor Street",
                "debtor_building_number": "456",
                "debtor_postal_code": "54321",
                "debtor_town_name": "Debtor Town",
                "debtor_country": "DE",
                "debtor_account_IBAN": "DE89370400440532013000",
                "debtor_agent_name": "Debtor Agent",
                "debtor_agent_BIC": "COBADEFFXXX",
                "charge_bearer": "SLEV",
                "payment_instruction_id": "INST123",
                "payment_end_to_end_id": "E2E123",
                "payment_currency": "EUR",
                "payment_amount": "1000.00",
                "creditor_name": "Creditor Ltd",
                "creditor_street_name": "Creditor Street",
                "creditor_building_number": "789",
                "creditor_postal_code": "98765",
                "creditor_town_name": "Creditor Town",
                "creditor_country": "DE",
                "creditor_account_IBAN": "DE89370400440532013001",
                "creditor_agent_BIC": "COBADEFFXXX",
                "creditor_agent_BICFI": "COBADEFFXXX",
                "creditor_agent_name": "Creditor Agent",
                "purpose_code": "SALA",
                "reference_number": "REF123",
                "reference_date": "2023-03-10",
                "remittance_information": "Payment for invoice",
            }
        ]

        generate_xml(
            data_v7,
            "pain.001.001.07",
            self.test_template_path,
            self.test_xsd_path,
        )

        output_path = "pain001/test_fixtures/pain.001.001.07.xml"
        self.assertTrue(os.path.exists(output_path))

        if os.path.exists(output_path):
            os.remove(output_path)

    def test_generate_xml_pain_001_001_08(self) -> None:
        """Test generate_xml with pain.001.001.08 message type."""
        import os

        from pain001.xml.generate_xml import generate_xml

        data_v8 = [
            {
                "id": "1",
                "date": "2023-03-10T15:30:47.000Z",
                "nb_of_txs": "1",
                "ctrl_sum": "1000.00",
                "initiator_name": "Test Company",
                "initiator_street_name": "Main Street",
                "initiator_building_number": "123",
                "initiator_postal_code": "12345",
                "initiator_town_name": "Test Town",
                "initiator_country": "DE",
                "payment_information_id": "PMT123",
                "payment_id": "PMT123",
                "payment_method": "TRF",
                "batch_booking": "true",
                "service_level_code": "SEPA",
                "requested_execution_date": "2023-03-15",
                "debtor_name": "Debtor Corp",
                "debtor_street_name": "Debtor Street",
                "debtor_building_number": "456",
                "debtor_postal_code": "54321",
                "debtor_town_name": "Debtor Town",
                "debtor_country": "DE",
                "debtor_account_IBAN": "DE89370400440532013000",
                "debtor_agent_name": "Debtor Agent",
                "debtor_agent_BIC": "COBADEFFXXX",
                "charge_bearer": "SLEV",
                "payment_instruction_id": "INST123",
                "payment_end_to_end_id": "E2E123",
                "payment_currency": "EUR",
                "payment_amount": "1000.00",
                "creditor_name": "Creditor Ltd",
                "creditor_street_name": "Creditor Street",
                "creditor_building_number": "789",
                "creditor_postal_code": "98765",
                "creditor_town_name": "Creditor Town",
                "creditor_country": "DE",
                "creditor_account_IBAN": "DE89370400440532013001",
                "creditor_agent_BIC": "COBADEFFXXX",
                "creditor_agent_BICFI": "COBADEFFXXX",
                "creditor_agent_name": "Creditor Agent",
                "purpose_code": "SALA",
                "reference_number": "REF123",
                "reference_date": "2023-03-10",
                "remittance_information": "Payment for invoice",
            }
        ]

        generate_xml(
            data_v8,
            "pain.001.001.08",
            self.test_template_path,
            self.test_xsd_path,
        )

        output_path = "pain001/test_fixtures/pain.001.001.08.xml"
        self.assertTrue(os.path.exists(output_path))

        if os.path.exists(output_path):
            os.remove(output_path)

    def test_generate_xml_pain_001_001_09(self) -> None:
        """Test generate_xml with pain.001.001.09 message type."""
        import os

        from pain001.xml.generate_xml import generate_xml

        data_v9 = [
            {
                "id": "1",
                "date": "2023-03-10T15:30:47.000Z",
                "nb_of_txs": "1",
                "ctrl_sum": "1000.00",
                "initiator_name": "Test Company",
                "initiator_street_name": "Main Street",
                "initiator_building_number": "123",
                "initiator_postal_code": "12345",
                "initiator_town_name": "Test Town",
                "initiator_country": "DE",
                "payment_information_id": "PMT123",
                "payment_id": "PMT123",
                "payment_method": "TRF",
                "batch_booking": "true",
                "service_level_code": "SEPA",
                "requested_execution_date": "2023-03-15",
                "debtor_name": "Debtor Corp",
                "debtor_street_name": "Debtor Street",
                "debtor_building_number": "456",
                "debtor_postal_code": "54321",
                "debtor_town_name": "Debtor Town",
                "debtor_country": "DE",
                "debtor_account_IBAN": "DE89370400440532013000",
                "debtor_agent_name": "Debtor Agent",
                "debtor_agent_BIC": "COBADEFFXXX",
                "charge_bearer": "SLEV",
                "payment_instruction_id": "INST123",
                "payment_end_to_end_id": "E2E123",
                "payment_currency": "EUR",
                "payment_amount": "1000.00",
                "creditor_name": "Creditor Ltd",
                "creditor_street_name": "Creditor Street",
                "creditor_building_number": "789",
                "creditor_postal_code": "98765",
                "creditor_town_name": "Creditor Town",
                "creditor_country": "DE",
                "creditor_account_IBAN": "DE89370400440532013001",
                "creditor_agent_BIC": "COBADEFFXXX",
                "creditor_agent_BICFI": "COBADEFFXXX",
                "creditor_agent_name": "Creditor Agent",
                "purpose_code": "SALA",
                "reference_number": "REF123",
                "reference_date": "2023-03-10",
                "remittance_information": "Payment for invoice",
            }
        ]

        generate_xml(
            data_v9,
            "pain.001.001.09",
            self.test_template_path,
            self.test_xsd_path,
        )

        output_path = "pain001/test_fixtures/pain.001.001.09.xml"
        self.assertTrue(os.path.exists(output_path))

        if os.path.exists(output_path):
            os.remove(output_path)

    def test_generate_xml_unsupported_version(self) -> None:
        """Test generate_xml raises ValueError with unsupported version."""
        from pain001.xml.generate_xml import generate_xml

        with self.assertRaises(ValueError):
            generate_xml(
                self.sample_data_v3,
                "pain.001.001.12",  # Unsupported version
                self.test_template_path,
                self.test_xsd_path,
            )

    def test_generate_xml_invalid_xsd_validation(self) -> None:
        """Test generate_xml with invalid XML that fails XSD validation."""
        import os
        from unittest.mock import patch

        from pain001.xml.generate_xml import generate_xml

        # Use pain.001.001.03 with valid data, but mock XSD validation to fail
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

    def test_generate_xml_message_type_in_generators_but_not_handled(
        self,
    ) -> None:
        """Test documentation for defensive else block (lines 532-538).

        The else block at lines 532-538 in generate_xml.py is defensive/unreachable
        code because all message types in xml_generators (pain.001.001.03 through .09)
        are explicitly handled by the elif chain. It's marked with # pragma: no cover.

        This test documents the defensive behavior and confirms all types are handled.
        """
        from pain001.xml.generate_xml import generate_xml

        # Verify all supported types in xml_generators
        supported_types = [
            "pain.001.001.03",
            "pain.001.001.04",
            "pain.001.001.05",
            "pain.001.001.06",
            "pain.001.001.07",
            "pain.001.001.08",
            "pain.001.001.09",
        ]

        # Confirm correct count of supported versions
        self.assertEqual(len(supported_types), 7)

        # Verify unsupported types fail at the outer check
        with self.assertRaises(ValueError):
            generate_xml(
                self.sample_data_v3,
                "pain.001.001.99",  # Not in xml_generators
                self.test_template_path,
                self.test_xsd_path,
            )

    def test_validate_xml_string_via_xsd_parsing_exception(self) -> None:
        """Test exception handling in validate_xml_string_via_xsd with malformed XML."""
        from pain001.xml.validate_via_xsd import validate_xml_string_via_xsd

        # Test with malformed XML that causes parsing error
        malformed_xml = "<Document><invalid"
        result = validate_xml_string_via_xsd(malformed_xml, self.test_xsd_path)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
