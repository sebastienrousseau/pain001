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
