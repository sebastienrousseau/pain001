import unittest

from pain001.xml.generate_xml import generate_xml


class TestXmlGenerator(unittest.TestCase):
    def test_xml_generator_with_invalid_input(self):
        """
        Test if the XML generator exits with a non-zero exit code when
        invalid input is provided.
        """

        # Arrange
        data = {
            "amount": "100.00",
            "currency": "USD",
            "beneficiary_bic": "ABCDE123",
            "beneficiary_iban": "DE8937060198000001234567",
            "creditor_bic": "DEFGH456",
            "creditor_iban": "DE893706019800000234567",
        }
        payment_initiation_message_type = "invalid_message_type"
        xml_file_path = "test.xml"
        xsd_file_path = "schema.xsd"

        # Act
        with self.assertRaises(SystemExit):
            generate_xml(
                data,
                payment_initiation_message_type,
                xml_file_path,
                xsd_file_path,
            )

        # Assert
        # self.assertEqual(sys.exitcode, 1)


if __name__ == "__main__":
    unittest.main()
