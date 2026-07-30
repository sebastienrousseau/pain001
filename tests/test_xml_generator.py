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


import unittest

from pain001.xml.generate_xml import generate_xml


class TestXmlGenerator(unittest.TestCase):
    def test_xml_generator_with_invalid_input(self) -> None:
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
        with self.assertRaises(ValueError):
            generate_xml(
                data,
                payment_initiation_message_type,
                xml_file_path,
                xsd_file_path,
            )


if __name__ == "__main__":
    unittest.main()
