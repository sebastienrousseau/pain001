import unittest
from pain001.csv.validate_csv_data import validate_csv_data

# Test if the CSV data is validated correctly


class TestValidateCsvData(unittest.TestCase):
    def test_valid_data(self):
        # Test valid data
        data = [
            {
                "id": "1",
                "date": "2022-01-01",
                "nb_of_txs": "1",
                "initiator_name": "John Doe",
                "payment_information_id": "12345",
                "payment_method": "TRF",
                "batch_booking": "false",
                "control_sum": "100",
                "service_level_code": "SEPA",
                "requested_execution_date": "2022-01-01",
                "debtor_name": "John Doe",
                "debtor_account_IBAN": "DE89370400440532013000",
                "debtor_agent_BIC": "DEUTDEDBFRA",
                "forwarding_agent_BIC": "FORWARD",
                "charge_bearer": "SHA",
                "payment_id": "12345",
                "payment_amount": "100.00",
                "currency": "EUR",
                "creditor_agent_BIC": "DABADEHHXXX",
                "creditor_name": "Jane Doe",
                "creditor_account_IBAN": "DE89370400440532013001",
                "remittance_information": "Invoice 1234",
            },
            {
                "id": "2",
                "date": "2022-01-02",
                "nb_of_txs": "1",
                "initiator_name": "Jane Doe",
                "payment_information_id": "67890",
                "payment_method": "TRF",
                "batch_booking": "false",
                "control_sum": "200",
                "service_level_code": "SEPA",
                "requested_execution_date": "2022-01-02",
                "debtor_name": "Jane Doe",
                "debtor_account_IBAN": "DE89370400440532013001",
                "debtor_agent_BIC": "DEUTDEDBFRA",
                "forwarding_agent_BIC": "FORWARD2",
                "charge_bearer": "SHA",
                "payment_id": "67890",
                "payment_amount": "200.00",
                "currency": "EUR",
                "creditor_agent_BIC": "DABADEHHXXX",
                "creditor_name": "John Doe",
                "creditor_account_IBAN": "DE89370400440532013000",
                "remittance_information": "Invoice 5678",
            },
        ]

        assert validate_csv_data(data) is True

    def test_missing_required_columns(self):
        # Test missing required columns
        data = [
            {
                "id": "1",
                "date": "2022-01-01",
                "nb_of_txs": "1",
                "payment_information_id": "12345",
                "payment_method": "TRF",
                "batch_booking": "false",
                "control_sum": "100",
                "service_level_code": "SEPA",
                "requested_execution_date": "2022-01-01",
                "debtor_name": "John Doe",
                "debtor_account_IBAN": "DE89370400440532013000",
                "debtor_agent_BIC": "DEUTDEDBFRA",
                "forwarding_agent_BIC": "FORWARD",
                "charge_bearer": "SHA",
                "payment_id": "12345",
                "payment_amount": "100.00",
                "currency": "EUR",
                "creditor_agent_BIC": "DABADEHHXXX",
                "creditor_name": "Jane Doe",
                "creditor_account_IBAN": "DE89370400440532013001",
                "remittance_information": "Invoice 1234",
            },
            {
                "id": "2",
                "date": "2022-01-02",
                "nb_of_txs": "1",
                "initiator_name": "Jane Doe",
                "payment_information_id": "67890",
                "payment_method": "TRF",
                "batch_booking": "false",
                "control_sum": "200",
                "service_level_code": "SEPA",
                "requested_execution_date": "2022-01-02",
                "debtor_name": "Jane Doe",
                "debtor_account_IBAN": "DE89370400440532013001",
                "debtor_agent_BIC": "DEUTDEDBFRA",
                "forwarding_agent_BIC": "FORWARD",
                "charge_bearer": "SHA",
                "payment_id": "67890",
                "payment_amount": "200.00",
                "currency": "EUR",
                "creditor_agent_BIC": "DABADEHHXXX",
                "creditor_name": "John Doe",
                "creditor_account_IBAN": "DE89370400440532013000",
                "remittance_information": "Invoice 5678",
            },
        ]

        assert not validate_csv_data(data)
