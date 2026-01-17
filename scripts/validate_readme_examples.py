"""
Script to validate README Code Examples.
"""

from pathlib import Path

from pain001 import main
from pain001.core.core import process_files


def validate_readme_examples():
    print("Testing README Examples...")

    # Setup paths
    base_dir = Path.cwd()
    template_dir = base_dir / "pain001/templates/pain.001.001.03"
    csv_file = template_dir / "template.csv"
    xml_template = template_dir / "template.xml"
    xsd_schema = template_dir / "pain.001.001.03.xsd"
    db_file = template_dir / "template.db"

    # 1. Test CSV Command Line using python -m
    print("\n1. Testing CSV Command Line execution...")
    try:
        main(
            xml_message_type="pain.001.001.03",
            xml_template_file_path=str(xml_template),
            xsd_schema_file_path=str(xsd_schema),
            data_file_path=str(csv_file),
        )
        print("✓ CSV Command Line: Success")
    except Exception as e:
        print(f"✗ CSV Command Line: Failed - {e}")

    # 2. Test SQLite Command Line
    print("\n2. Testing SQLite Command Line execution...")
    try:
        main(
            xml_message_type="pain.001.001.03",
            xml_template_file_path=str(xml_template),
            xsd_schema_file_path=str(xsd_schema),
            data_file_path=str(db_file),
        )
        print("✓ SQLite Command Line: Success")
    except Exception as e:
        print(f"✗ SQLite Command Line: Failed - {e}")

    # 3. Test Python List
    print("\n3. Testing Python List API...")
    try:
        payments = [
            {
                "id": "12345",
                "date": "2024-01-15T10:00:00",
                "nb_of_txs": "1",
                "initiator_name": "ACME Corp",
                "initiator_street_name": "Main St",
                "initiator_building_number": "1",
                "initiator_postal_code": "12345",
                "initiator_town_name": "Springfield",
                "initiator_country_code": "US",
                "payment_information_id": "PYT001",
                "payment_method": "TRF",
                "batch_booking": "true",
                "ctrl_sum": "1000.00",
                "service_level_code": "SEPA",
                "requested_execution_date": "2024-01-16",
                "debtor_name": "John Doe",
                "debtor_street_name": "Elm St",
                "debtor_building_number": "2",
                "debtor_postal_code": "54321",
                "debtor_town_name": "Shelbyville",
                "debtor_country_code": "US",
                "debtor_account_IBAN": "DE89370400440532013000",
                "debtor_agent_BIC": "TESTDEUTXXX",
                "forwarding_agent_BIC": "TESTDEUTXXX",
                "charge_bearer": "SLEV",
                "payment_id": "TX001",
                "payment_amount": "1000.00",
                "payment_currency": "EUR",
                "currency": "EUR",
                "creditor_agent_BIC": "TESTDEUTXXX",
                "creditor_name": "Jane Smith",
                "creditor_street_name": "Oak St",
                "creditor_building_number": "3",
                "creditor_postal_code": "98765",
                "creditor_town_name": "Capital City",
                "creditor_country_code": "US",
                "creditor_account_IBAN": "DE89370400440532013000",
                "remittance_information": "Invoice 123",
                "purpose_code": "OTHR",
                "reference_number": "REF123",
                "reference_date": "2024-01-15",
            }
        ]

        process_files(
            xml_message_type="pain.001.001.03",
            data_file_path=payments,
            xml_template_file_path=str(xml_template),
            xsd_schema_file_path=str(xsd_schema),
        )
        print("✓ Python List API: Success")
    except Exception as e:
        print(f"✗ Python List API: Failed - {e}")

    # 4. Test Python Dict
    print("\n4. Testing Python Dict API...")
    try:
        payment = {
            "id": "12346",
            "date": "2024-01-15T10:00:00",
            "nb_of_txs": "1",
            "initiator_name": "ACME Corp",
            "initiator_street_name": "Main St",
            "initiator_building_number": "1",
            "initiator_postal_code": "12345",
            "initiator_town_name": "Springfield",
            "initiator_country_code": "US",
            "payment_information_id": "PYT002",
            "payment_method": "TRF",
            "batch_booking": "true",
            "ctrl_sum": "500.00",
            "service_level_code": "SEPA",
            "requested_execution_date": "2024-01-16",
            "debtor_name": "John Doe",
            "debtor_street_name": "Elm St",
            "debtor_building_number": "2",
            "debtor_postal_code": "54321",
            "debtor_town_name": "Shelbyville",
            "debtor_country_code": "US",
            "debtor_account_IBAN": "DE89370400440532013000",
            "debtor_agent_BIC": "TESTDEUTXXX",
            "forwarding_agent_BIC": "TESTDEUTXXX",
            "charge_bearer": "SLEV",
            "payment_id": "TX002",
            "payment_amount": "500.00",
            "payment_currency": "EUR",
            "currency": "EUR",
            "creditor_agent_BIC": "TESTDEUTXXX",
            "creditor_name": "Jane Smith",
            "creditor_street_name": "Oak St",
            "creditor_building_number": "3",
            "creditor_postal_code": "98765",
            "creditor_town_name": "Capital City",
            "creditor_country_code": "US",
            "creditor_account_IBAN": "DE89370400440532013000",
            "remittance_information": "Invoice 456",
            "purpose_code": "OTHR",
            "reference_number": "REF456",
            "reference_date": "2024-01-15",
        }

        process_files(
            xml_message_type="pain.001.001.03",
            data_file_path=payment,
            xml_template_file_path=str(xml_template),
            xsd_schema_file_path=str(xsd_schema),
        )
        print("✓ Python Dict API: Success")
    except Exception as e:
        print(f"✗ Python Dict API: Failed - {e}")


if __name__ == "__main__":
    validate_readme_examples()
