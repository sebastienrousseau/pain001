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
from unittest.mock import patch
from pain001.db.validate_db_data import validate_db_data


class TestValidateDbData(unittest.TestCase):
    def setUp(self):
        self.valid_data = [
            {
                "id": 1,
                "date": "2023-03-10T15:30:47",
                "nb_of_txs": 2,
                "initiator_name": "John Doe",
                "initiator_street_name": "John's Street",
                "initiator_building_number": 1,
                "initiator_postal_code": "12345",
                "initiator_town_name": "John's Town",
                "initiator_country_code": "DE",
                "payment_information_id": "Payment-Info-12345",
                "payment_method": "TRF",
                "batch_booking": False,
                "requested_execution_date": "2023-03-15",
                "debtor_name": "Debtor Name",
                "debtor_street_name": "Debtor Street",
                "debtor_building_number": 1,
                "debtor_postal_code": "12345",
                "debtor_town_name": "Debtor Town",
                "debtor_country_code": "DE",
                "debtor_account_IBAN": "DE89370400440532013000",
                "debtor_agent_BIC": "BICCODE",
                "charge_bearer": "DEBT",
                "payment_id": "12345",
                "payment_amount": "100.00",
                "currency": "EUR",
                "payment_currency": "EUR",
                "ctrl_sum": "100.00",
                "creditor_agent_BIC": "BICCODE",
                "creditor_name": "Creditor Name",
                "creditor_street_name": "Creditor Street",
                "creditor_building_number": 1,
                "creditor_postal_code": "12345",
                "creditor_town_name": "Creditor Town",
                "creditor_country_code": "DE",
                "creditor_account_IBAN": "DE89370400440532013000",
                "purpose_code": "SCOR",
                "reference_number": "Reference-12345",
                "reference_date": "2023-03-10",
                "service_level_code": "SEPA",
                "end_to_end_id": "End-to-End-Id-123",
                "payment_instruction_id": "Payment-Instruction-Id-123",
                "instruction_id": "Instruction-Id-123",
                "category_purpose": "Category-Purpose-123",
                "remittance_info_unstructured": "Remittance-Info-Unstructured-123",
                "remittance_info_structured": "Remittance-Info-Structured-123",
                "addtl_end_to_end_id": "Addtl-End-to-End-Id-123",
                "payment_info_structured": "Payment-Info-Structured-123",
                "forwarding_agent_BIC": "Forwarding-Agent-BIC-123",
                "remittance_information": "Remittance-Information-123",
            }
        ]

    def test_validate_db_data_valid(self):
        self.assertTrue(validate_db_data(self.valid_data))

    @patch("pain001.db.validate_db_data.logger.error")
    def test_validate_db_data_logging(self, mock_logging_error):
        invalid_data = self.valid_data.copy()
        invalid_data[0].pop("id")
        validate_db_data(invalid_data)
        mock_logging_error.assert_called_once_with(
            "Error: Missing value for column '%s' in row: %s",
            "id",
            invalid_data[0],
        )


if __name__ == "__main__":
    unittest.main()
