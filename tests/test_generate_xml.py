import unittest

import xml.etree.ElementTree as ET

from pain001.xml.generate_xml import (
    create_common_elements,
    create_xml_v3,
    create_xml_v9,
)


class TestXMLCreation(unittest.TestCase):
    def setUp(self):
        """
        Test setup
        """
        self.root = ET.Element("Root")
        self.row = {
            "initiator_name": "Initiator",
            "batch_booking": "true",
            "nb_of_txs": "2",
            "control_sum": "3000",
            "service_level_code": "Code",
            "requested_execution_date": "2023-05-21",
            "debtor_name": "Debtor",
            "debtor_account_IBAN": "DE123456789",
            "debtor_agent_BIC": "DEUTDEFF",
            "charge_bearer": "Bearer",
            "payment_id": "PID123",
            "payment_amount": "1500",
            "payment_method": "pain.001.001.09",
            "currency": "EUR",
            "creditor_agent_BIC": "NOLADE21KIE",
            "creditor_name": "Creditor",
            "creditor_account_IBAN": "DE26500700100096773701",
            "remittance_information": "Invoice 123",
        }
        self.mapping = {
            "MsgId": "payment_id",
            "CreDtTm": "requested_execution_date",
            "NbOfTxs": "nb_of_txs",
            "PmtInfId": "payment_id",
            "PmtMtd": "payment_method",
        }

    def test_create_common_elements(self):
        """
        Test create_common_elements
        """
        create_common_elements(self.root, self.row, self.mapping)
        self.assertEqual(len(self.root), 2)
        self.assertEqual(self.root[0].tag, "PmtInfId")
        self.assertEqual(self.root[0].text, "PID123")
        self.assertEqual(self.root[1].tag, "PmtMtd")
        self.assertEqual(self.root[1].text, "pain.001.001.09")

    def test_create_xml_v3(self):
        """
        Test create_xml_v3
        """
        create_xml_v3(self.root, [self.row], self.mapping)
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(
            cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn"
        )
        # You can continue to assert more conditions based on your expectations

    def test_create_xml_v9(self):
        """
        Test create_xml_v9
        """

        create_xml_v9(self.root, [self.row], self.mapping)
        cstmr_cdt_trf_initn_element = self.root[0]
        self.assertEqual(
            cstmr_cdt_trf_initn_element.tag, "CstmrCdtTrfInitn"
        )
        # You can continue to assert more conditions based on your expectations


if __name__ == "__main__":
    unittest.main()
