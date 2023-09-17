import unittest
import xml.etree.ElementTree as ET
from pain001.xml.create_xml_v3 import create_xml_v3
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
        self.assertEqual(
            cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn"
        )

    def test_create_xml_v9(self):
        """
        Test create_xml_v9
        """
        create_xml_v9(self.root, [self.row_v9])
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(
            cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn"
        )


if __name__ == "__main__":
    unittest.main()
