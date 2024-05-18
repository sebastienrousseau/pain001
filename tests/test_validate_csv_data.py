import unittest
from pain001.csv.validate_csv_data import validate_csv_data


class TestValidateCsvData(unittest.TestCase):
    def test_validate_csv_with_valid_data(self):
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

    def test_validate_csv_with_invalid_data(self):
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


if __name__ == "__main__":
    unittest.main()
