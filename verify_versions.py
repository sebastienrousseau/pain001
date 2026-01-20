import os
import sys
import traceback

from pain001.constants import valid_xml_types
from pain001.xml.generate_xml import generate_xml


def test_all_versions():
    data = [
        {
            "id": "MSG001",
            "date": "2024-01-15T12:00:00",
            "nb_of_txs": 1,
            "ctrl_sum": 100.50,
            "initiator_name": "ACME Corp",
            "initiator_street_name": "Main Street",
            "initiator_building_number": "123",
            "initiator_postal_code": "12345",
            "initiator_town_name": "Anytown",
            "initiator_country_code": "DE",
            "payment_information_id": "PYT001",
            "payment_method": "TRF",
            "batch_booking": "false",
            "service_level_code": "SEPA",
            "requested_execution_date": "2024-01-16",
            "debtor_name": "John Doe",
            "debtor_street_name": "Debtor St",
            "debtor_building_number": "456",
            "debtor_postal_code": "67890",
            "debtor_town_name": "Debtortown",
            "debtor_country_code": "DE",
            "debtor_account_IBAN": "DE89370400440532013000",
            "debtor_agent_BIC": "DEUTDEFF",
            "charge_bearer": "SLEV",
            "payment_id": "PAY001",
            "payment_amount": 100.50,
            "payment_currency": "EUR",
            "creditor_agent_BIC": "COBADEFF",
            "creditor_name": "Creditor Corp",
            "creditor_street_name": "Creditor St",
            "creditor_building_number": "789",
            "creditor_postal_code": "11223",
            "creditor_town_name": "Creditortown",
            "creditor_country_code": "DE",
            "creditor_account_IBAN": "DE89370400440532013001",
            "purpose_code": "CASH",
            "reference_number": "REF123",
            "reference_date": "2024-01-14",
            "remittance_information": "Invoice 12345",
        }
    ]

    print(f"Testing {len(valid_xml_types)} XML versions...")

    success_count = 0
    for xml_type in valid_xml_types:
        try:
            # Construct paths
            template_path = os.path.join(
                "pain001", "templates", xml_type, "template.xml"
            )
            xsd_path = os.path.join(
                "pain001", "templates", xml_type, f"{xml_type}.xsd"
            )

            # Call generate_xml with template_path as 3rd Arg (it determines output path internally)
            generate_xml(data, xml_type, template_path, xsd_path)

            # note: generate_xml writes to a timestamped file, we can't easily assert the specific filename here
            # without duplicating logic, but if it doesn't crash, it's a good sign.
            print("OK")
            success_count += 1

        except Exception as e:
            print(f"FAILED: {e}")
            traceback.print_exc()

    print(
        f"\nSummary: {success_count}/{len(valid_xml_types)} versions passed."
    )

    if success_count == len(valid_xml_types):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    test_all_versions()
