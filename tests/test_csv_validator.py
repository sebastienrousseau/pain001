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
from io import StringIO
from unittest.mock import patch

from pain001.csv.validate_csv_data import validate_csv_data


class TestValidateCsvData(unittest.TestCase):
    def test_validate_csv_with_invalid_date_format_fallback(self) -> None:
        """Test CSV validation with date that fails both fromisoformat and strptime."""
        data = [
            {
                "id": "1",
                "date": "invalid-date-format",  # Triggers ValueError in both parsers
                "nb_of_txs": "1",
                "initiator_name": "John Doe",
                "initiator_street_name": "John's Street",
                "initiator_building_number": "123",
                "initiator_postal_code": "12345",
                "initiator_town_name": "City",
                "initiator_country": "US",
                "ctrl_sum": "100.00",
                "payment_information_id": "PMT001",
                "payment_method": "TRF",
                "batch_booking": "true",
                "service_level_code": "SEPA",
                "requested_execution_date": "2023-03-10",
                "debtor_name": "John Doe",
                "debtor_street_name": "Debtor Street",
                "debtor_building_number": "456",
                "debtor_postal_code": "67890",
                "debtor_town_name": "Town",
                "debtor_country": "US",
                "debtor_account_IBAN": "US12345678901234567890",
                "debtor_agent_BIC": "BANKUS33",
                "forwarding_agent_BIC": "FWDUS55",  # Added missing field
                "charge_bearer": "SLEV",
                "payment_id": "PAY001",
                "payment_amount": "100.00",
                "currency": "USD",
                "creditor_agent_BIC": "CREDUS44",
                "creditor_name": "Jane Smith",
                "creditor_street_name": "Creditor Street",
                "creditor_building_number": "789",
                "creditor_postal_code": "11111",
                "creditor_town_name": "City2",
                "creditor_country": "US",
                "creditor_account_IBAN": "US98765432109876543210",
                "remittance_information": "Payment for invoice",
            }
        ]
        # The invalid date format should be caught during validation
        # validate_csv_data returns True/False, not raise
        result = validate_csv_data(data)
        # Should return False due to invalid date
        self.assertFalse(result)

    def test_validate_csv_with_valid_data(self) -> None:
        data = [
            {
                "id": "1",
                "date": "2023-03-10T15:30:47.000Z",
                "nb_of_txs": "2",
                "initiator_name": "John Doe",
                "initiator_street_name": "John's Street",
                "initiator_building_number": "1",
                "initiator_postal_code": "12345",
                "initiator_town_name": "John's Town",
                "initiator_country_code": "DE",
                "payment_information_id": "Payment-Info-12345",
                "payment_method": "TRF",
                "batch_booking": "true",
                "requested_execution_date": "2023-03-12",
                "debtor_name": "Acme Corp",
                "debtor_street_name": "Acme Street",
                "debtor_building_number": "2",
                "debtor_postal_code": "67890",
                "debtor_town_name": "Acme Town",
                "debtor_country_code": "DE",
                "debtor_account_IBAN": "DE75512108001245126162",
                "debtor_agent_BIC": "BANKDEFFXXX",
                "charge_bearer": "SLEV",
                "payment_id": "PaymentID6789",
                "payment_amount": "150",
                "currency": "EUR",
                "payment_currency": "EUR",
                "ctrl_sum": "15000",
                "creditor_agent_BIC": "SPUEDE2UXXX",
                "creditor_name": "Global Tech",
                "creditor_street_name": "Global Street",
                "creditor_building_number": "3",
                "creditor_postal_code": "11223",
                "creditor_town_name": "Global Town",
                "creditor_country_code": "DE",
                "creditor_account_IBAN": "DE68210501700024690959",
                "purpose_code": "OTHR",
                "reference_number": "Invoice-98765",
                "reference_date": "2023-03-09",
                "service_level_code": "SEPA",
                "forwarding_agent_BIC": "SPUEDE2UXXX",
                "remittance_information": "Invoice-12345",
                "charge_account_IBAN": "CHARGE-IBAN-12345",
            }
        ]
        self.assertTrue(validate_csv_data(data))

    def test_validate_csv_with_invalid_data(self) -> None:
        data = [
            {
                "id": "1",
                "date": "not-a-date",
                "nb_of_txs": "2",
                "initiator_name": "John Doe",
                "initiator_street_name": "John's Street",
                "initiator_building_number": "1",
                "initiator_postal_code": "12345",
                "initiator_town_name": "John's Town",
                "initiator_country_code": "DE",
                "payment_information_id": "Payment-Info-12345",
                "payment_method": "TRF",
                "batch_booking": "true",
                "requested_execution_date": "2023-03-12",
                "debtor_name": "Acme Corp",
                "debtor_street_name": "Acme Street",
                "debtor_building_number": "2",
                "debtor_postal_code": "67890",
                "debtor_town_name": "Acme Town",
                "debtor_country_code": "DE",
                "debtor_account_IBAN": "DE75512108001245126162",
                "debtor_agent_BIC": "BANKDEFFXXX",
                "charge_bearer": "SLEV",
                "payment_id": "PaymentID6789",
                "payment_amount": "150",
                "currency": "EUR",
                "payment_currency": "EUR",
                "ctrl_sum": "15000",
                "creditor_agent_BIC": "SPUEDE2UXXX",
                "creditor_name": "Global Tech",
                "creditor_street_name": "Global Street",
                "creditor_building_number": "3",
                "creditor_postal_code": "11223",
                "creditor_town_name": "Global Town",
                "creditor_country_code": "DE",
                "creditor_account_IBAN": "DE68210501700024690959",
                "purpose_code": "OTHR",
                "reference_number": "Invoice-98765",
                "reference_date": "2023-03-09",
                "service_level_code": "SEPA",
                "forwarding_agent_BIC": "SPUEDE2UXXX",
                "remittance_information": "Invoice-12345",
                "charge_account_IBAN": "CHARGE-IBAN-12345",
            }
        ]
        self.assertFalse(validate_csv_data(data))

    def test_validate_csv_with_empty_data(self) -> None:
        """Test validation with empty data list."""
        data: list[dict[str, str]] = []
        self.assertFalse(validate_csv_data(data))

    def test_validate_csv_with_missing_column_values(self) -> None:
        """Test validation with missing required column values."""
        data = [
            {
                "id": "1",
                "date": "2023-03-10T15:30:47.000Z",
                "nb_of_txs": "",  # Empty value
                "initiator_name": "John Doe",
                "initiator_street_name": "John's Street",
                "initiator_building_number": "1",
                "initiator_postal_code": "12345",
                "initiator_town_name": "John's Town",
                "initiator_country_code": "DE",
                "payment_information_id": "Payment-Info-12345",
                "payment_method": "TRF",
                "batch_booking": "true",
                "requested_execution_date": "2023-03-12",
                "debtor_name": "Acme Corp",
                "debtor_street_name": "Acme Street",
                "debtor_building_number": "2",
                "debtor_postal_code": "67890",
                "debtor_town_name": "Acme Town",
                "debtor_country_code": "DE",
                "debtor_account_IBAN": "DE75512108001245126162",
                "debtor_agent_BIC": "BANKDEFFXXX",
                "charge_bearer": "SLEV",
                "payment_id": "PaymentID6789",
                "payment_amount": "150",
                "currency": "EUR",
                "payment_currency": "EUR",
                "ctrl_sum": "15000",
                "creditor_agent_BIC": "SPUEDE2UXXX",
                "creditor_name": "Global Tech",
                "creditor_street_name": "Global Street",
                "creditor_building_number": "3",
                "creditor_postal_code": "11223",
                "creditor_town_name": "Global Town",
                "creditor_country_code": "DE",
                "creditor_account_IBAN": "DE68210501700024690959",
                "purpose_code": "OTHR",
                "reference_number": "Invoice-98765",
                "reference_date": "2023-03-09",
                "service_level_code": "SEPA",
                "forwarding_agent_BIC": "SPUEDE2UXXX",
                "remittance_information": "Invoice-12345",
                "charge_account_IBAN": "CHARGE-IBAN-12345",
            }
        ]
        self.assertFalse(validate_csv_data(data))

    def test_validate_csv_redacts_sensitive_values_in_error_output(self) -> None:
        """Validation errors should not print raw IBAN/BIC/name values."""
        data = [
            {
                "id": "1",
                "date": "2023-03-10T15:30:47.000Z",
                "nb_of_txs": "2",
                "initiator_name": "John Doe",
                "payment_information_id": "Payment-Info-12345",
                "payment_method": "TRF",
                "batch_booking": "true",
                "requested_execution_date": "2023-03-12",
                "debtor_name": "Acme Corp",
                "debtor_account_IBAN": "DE75512108001245126162",
                "debtor_agent_BIC": "BANKDEFFXXX",
                "forwarding_agent_BIC": "SPUEDE2UXXX",
                "charge_bearer": "SLEV",
                "payment_id": "PaymentID6789",
                "payment_amount": "150",
                "currency": "EUR",
                "ctrl_sum": "15000",
                "service_level_code": "SEPA",
                "creditor_agent_BIC": "SPUEDE2UXXX",
                "creditor_name": "",  # force error
                "creditor_account_IBAN": "DE68210501700024690959",
                "remittance_information": "Invoice-12345",
            }
        ]
        fake_stdout = StringIO()
        with patch("sys.stdout", fake_stdout):
            self.assertFalse(validate_csv_data(data))

        output = fake_stdout.getvalue()
        self.assertNotIn("DE75512108001245126162", output)
        self.assertNotIn("DE68210501700024690959", output)
        self.assertNotIn("BANKDEFFXXX", output)
        self.assertNotIn("John Doe", output)
        self.assertIn("[REDACTED]", output)

    def test_validate_csv_with_invalid_boolean(self) -> None:
        """Test validation with invalid boolean value."""
        data = [
            {
                "id": "1",
                "date": "2023-03-10T15:30:47.000Z",
                "nb_of_txs": "2",
                "initiator_name": "John Doe",
                "initiator_street_name": "John's Street",
                "initiator_building_number": "1",
                "initiator_postal_code": "12345",
                "initiator_town_name": "John's Town",
                "initiator_country_code": "DE",
                "payment_information_id": "Payment-Info-12345",
                "payment_method": "TRF",
                "batch_booking": "not-a-boolean",  # Invalid boolean
                "requested_execution_date": "2023-03-12",
                "debtor_name": "Acme Corp",
                "debtor_street_name": "Acme Street",
                "debtor_building_number": "2",
                "debtor_postal_code": "67890",
                "debtor_town_name": "Acme Town",
                "debtor_country_code": "DE",
                "debtor_account_IBAN": "DE75512108001245126162",
                "debtor_agent_BIC": "BANKDEFFXXX",
                "charge_bearer": "SLEV",
                "payment_id": "PaymentID6789",
                "payment_amount": "150",
                "currency": "EUR",
                "payment_currency": "EUR",
                "ctrl_sum": "15000",
                "creditor_agent_BIC": "SPUEDE2UXXX",
                "creditor_name": "Global Tech",
                "creditor_street_name": "Global Street",
                "creditor_building_number": "3",
                "creditor_postal_code": "11223",
                "creditor_town_name": "Global Town",
                "creditor_country_code": "DE",
                "creditor_account_IBAN": "DE68210501700024690959",
                "purpose_code": "OTHR",
                "reference_number": "Invoice-98765",
                "reference_date": "2023-03-09",
                "service_level_code": "SEPA",
                "forwarding_agent_BIC": "SPUEDE2UXXX",
                "remittance_information": "Invoice-12345",
                "charge_account_IBAN": "CHARGE-IBAN-12345",
            }
        ]
        self.assertFalse(validate_csv_data(data))

    def test_validate_csv_with_date_format(self) -> None:
        """Test validation with simple date format (YYYY-MM-DD)."""
        data = [
            {
                "id": "1",
                "date": "2023-03-10",  # Simple date format
                "nb_of_txs": "2",
                "initiator_name": "John Doe",
                "initiator_street_name": "John's Street",
                "initiator_building_number": "1",
                "initiator_postal_code": "12345",
                "initiator_town_name": "John's Town",
                "initiator_country_code": "DE",
                "payment_information_id": "Payment-Info-12345",
                "payment_method": "TRF",
                "batch_booking": "true",
                "requested_execution_date": "2023-03-12",
                "debtor_name": "Acme Corp",
                "debtor_street_name": "Acme Street",
                "debtor_building_number": "2",
                "debtor_postal_code": "67890",
                "debtor_town_name": "Acme Town",
                "debtor_country_code": "DE",
                "debtor_account_IBAN": "DE75512108001245126162",
                "debtor_agent_BIC": "BANKDEFFXXX",
                "charge_bearer": "SLEV",
                "payment_id": "PaymentID6789",
                "payment_amount": "150",
                "currency": "EUR",
                "payment_currency": "EUR",
                "ctrl_sum": "15000",
                "creditor_agent_BIC": "SPUEDE2UXXX",
                "creditor_name": "Global Tech",
                "creditor_street_name": "Global Street",
                "creditor_building_number": "3",
                "creditor_postal_code": "11223",
                "creditor_town_name": "Global Town",
                "creditor_country_code": "DE",
                "creditor_account_IBAN": "DE68210501700024690959",
                "purpose_code": "OTHR",
                "reference_number": "Invoice-98765",
                "reference_date": "2023-03-09",
                "service_level_code": "SEPA",
                "forwarding_agent_BIC": "SPUEDE2UXXX",
                "remittance_information": "Invoice-12345",
                "charge_account_IBAN": "CHARGE-IBAN-12345",
            }
        ]
        self.assertTrue(validate_csv_data(data))

    def test_validate_csv_with_invalid_float(self) -> None:
        """Test validation with invalid float value."""
        data = [
            {
                "id": "1",
                "date": "2023-03-10T15:30:47.000Z",
                "nb_of_txs": "2",
                "initiator_name": "John Doe",
                "initiator_street_name": "John's Street",
                "initiator_building_number": "1",
                "initiator_postal_code": "12345",
                "initiator_town_name": "John's Town",
                "initiator_country_code": "DE",
                "payment_information_id": "Payment-Info-12345",
                "payment_method": "TRF",
                "batch_booking": "true",
                "requested_execution_date": "2023-03-12",
                "debtor_name": "Acme Corp",
                "debtor_street_name": "Acme Street",
                "debtor_building_number": "2",
                "debtor_postal_code": "67890",
                "debtor_town_name": "Acme Town",
                "debtor_country_code": "DE",
                "debtor_account_IBAN": "DE75512108001245126162",
                "debtor_agent_BIC": "BANKDEFFXXX",
                "charge_bearer": "SLEV",
                "payment_id": "PaymentID6789",
                "payment_amount": "not-a-number",  # Invalid float
                "currency": "EUR",
                "payment_currency": "EUR",
                "ctrl_sum": "15000",
                "creditor_agent_BIC": "SPUEDE2UXXX",
                "creditor_name": "Global Tech",
                "creditor_street_name": "Global Street",
                "creditor_building_number": "3",
                "creditor_postal_code": "11223",
                "creditor_town_name": "Global Town",
                "creditor_country_code": "DE",
                "creditor_account_IBAN": "DE68210501700024690959",
                "purpose_code": "OTHR",
                "reference_number": "Invoice-98765",
                "reference_date": "2023-03-09",
                "service_level_code": "SEPA",
                "forwarding_agent_BIC": "SPUEDE2UXXX",
                "remittance_information": "Invoice-12345",
                "charge_account_IBAN": "CHARGE-IBAN-12345",
            }
        ]
        self.assertFalse(validate_csv_data(data))

    def test_validate_csv_with_completely_invalid_datetime(self) -> None:
        """Test validation with datetime that fails both ISO and Y-m-d parsing."""
        data = [
            {
                "id": "1",
                "date": "invalid-datetime-format",  # Not ISO, not Y-m-d
                "nb_of_txs": "2",
                "initiator_name": "John Doe",
                "initiator_street_name": "John's Street",
                "initiator_building_number": "1",
                "initiator_postal_code": "12345",
                "initiator_town_name": "John's Town",
                "initiator_country_code": "DE",
                "payment_information_id": "Payment-Info-12345",
                "payment_method": "TRF",
                "batch_booking": "true",
                "requested_execution_date": "2023-03-12",
                "debtor_name": "Acme Corp",
                "debtor_street_name": "Acme Street",
                "debtor_building_number": "2",
                "debtor_postal_code": "67890",
                "debtor_town_name": "Acme Town",
                "debtor_country_code": "DE",
                "debtor_account_IBAN": "DE75512108001245126162",
                "debtor_agent_BIC": "BANKDEFFXXX",
                "charge_bearer": "SLEV",
                "payment_id": "PaymentID6789",
                "payment_amount": "150",
                "currency": "EUR",
                "payment_currency": "EUR",
                "ctrl_sum": "15000",
                "creditor_agent_BIC": "SPUEDE2UXXX",
                "creditor_name": "Global Tech",
                "creditor_street_name": "Global Street",
                "creditor_building_number": "3",
                "creditor_postal_code": "11223",
                "creditor_town_name": "Global Town",
                "creditor_country_code": "DE",
                "creditor_account_IBAN": "DE68210501700024690959",
                "purpose_code": "OTHR",
                "reference_number": "Invoice-98765",
                "reference_date": "2023-03-09",
                "service_level_code": "SEPA",
                "forwarding_agent_BIC": "SPUEDE2UXXX",
                "remittance_information": "Invoice-12345",
                "charge_account_IBAN": "CHARGE-IBAN-12345",
            }
        ]
        self.assertFalse(validate_csv_data(data))


if __name__ == "__main__":
    unittest.main()
