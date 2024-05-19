import os
import unittest
from unittest.mock import patch
from io import StringIO
from pain001.core.core import process_files


class TestProcessFiles(unittest.TestCase):
    def setUp(self):
        self.xml_message_type = "pain.001.001.03"
        self.xml_template_file_path = "tests/data/template.xml"
        self.xsd_schema_file_path = "tests/data/template.xsd"
        self.csv_file_path = "tests/data/valid_data.csv"

        self.invalid_csv_file_path = "tests/data/invalid_data.csv"
        self.empty_csv_file_path = "tests/data/empty.csv"
        self.single_column_csv_file_path = (
            "tests/data/single_column.csv"
        )
        self.single_row_csv_file_path = "tests/data/single_row.csv"
        self.sqlite_file_path = "tests/data/valid_data.db"
        self.invalid_sqlite_file_path = "tests/data/invalid_data.db"
        self.unsupported_file_path = (
            "tests/data/unsupported_data_type.txt"
        )

        self.create_test_files()

    def create_test_files(self):
        os.makedirs("tests/data", exist_ok=True)

        # Create valid_data.csv
        with open(self.csv_file_path, "w") as f:
            f.write(
                "id,date,nb_of_txs,initiator_name,initiator_street_name,"
                "initiator_building_number,initiator_postal_code,initiator_town_name,"
                "initiator_country_code,payment_information_id,payment_method,"
                "batch_booking,requested_execution_date,debtor_name,debtor_street_name,"
                "debtor_building_number,debtor_postal_code,debtor_town_name,debtor_country_code,"
                "debtor_account_IBAN,debtor_agent_BIC,charge_bearer,payment_id,payment_amount,"
                "currency,payment_currency,ctrl_sum,creditor_agent_BIC,creditor_name,creditor_street_name,"
                "creditor_building_number,creditor_postal_code,creditor_town_name,creditor_country_code,"
                "creditor_account_IBAN,purpose_code,reference_number,reference_date,service_level_code,"
                "forwarding_agent_BIC,remittance_information,charge_account_IBAN\n"
                "1,2023-03-10T15:30:47,2,John Doe,John's Street,1,12345,John's Town,DE,"
                "Payment-Info-12345,TRF,false,2023-03-15,Debtor Name,Debtor Street,1,"
                "12345,Debtor Town,DE,DE89370400440532013000,BICCODE,DEBT,12345,100.00,"
                "EUR,EUR,100.00,BICCODE,Creditor Name,Creditor Street,1,12345,Creditor Town,"
                "DE,DE89370400440532013000,SCOR,Reference-12345,2023-03-10,SEPA,BICCODE,"
                "Remittance Information,DE89370400440532013000\n"
            )

        # Create invalid_data.csv
        with open(self.invalid_csv_file_path, "w") as f:
            f.write("id,date,nb_of_txs\n" "1,invalid_date,2\n")

        # Create empty.csv
        with open(self.empty_csv_file_path, "w") as f:
            f.write("")

        # Create single_column.csv
        with open(self.single_column_csv_file_path, "w") as f:
            f.write("id\n1\n")

        # Create single_row.csv
        with open(self.single_row_csv_file_path, "w") as f:
            f.write(
                "id,date,nb_of_txs,initiator_name,initiator_street_name,"
                "initiator_building_number,initiator_postal_code,initiator_town_name,"
                "initiator_country_code,payment_information_id,payment_method,"
                "batch_booking,requested_execution_date,debtor_name,debtor_street_name,"
                "debtor_building_number,debtor_postal_code,debtor_town_name,debtor_country_code,"
                "debtor_account_IBAN,debtor_agent_BIC,charge_bearer,payment_id,payment_amount,"
                "currency,payment_currency,ctrl_sum,creditor_agent_BIC,creditor_name,creditor_street_name,"
                "creditor_building_number,creditor_postal_code,creditor_town_name,creditor_country_code,"
                "creditor_account_IBAN,purpose_code,reference_number,reference_date,service_level_code,"
                "forwarding_agent_BIC,remittance_information,charge_account_IBAN\n"
                "1,2023-03-10T15:30:47,2,John Doe,John's Street,1,12345,John's Town,DE,"
                "Payment-Info-12345,TRF,false,2023-03-15,Debtor Name,Debtor Street,1,"
                "12345,Debtor Town,DE,DE89370400440532013000,BICCODE,DEBT,12345,100.00,"
                "EUR,EUR,100.00,BICCODE,Creditor Name,Creditor Street,1,12345,Creditor Town,"
                "DE,DE89370400440532013000,SCOR,Reference-12345,2023-03-10,SEPA,BICCODE,"
                "Remittance Information,DE89370400440532013000\n"
            )

        # Create template.xml
        with open(self.xml_template_file_path, "w") as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
                <note>
                    <to>{{ to }}</to>
                    <from>{{ from }}</from>
                    <heading>{{ heading }}</heading>
                    <body>{{ body }}</body>
                </note>"""
            )

        # Create template.xsd with valid XSD content
        with open(self.xsd_schema_file_path, "w") as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:element name="note">
                        <xs:complexType>
                            <xs:sequence>
                                <xs:element name="to" type="xs:string"/>
                                <xs:element name="from" type="xs:string"/>
                                <xs:element name="heading" type="xs:string"/>
                                <xs:element name="body" type="xs:string"/>
                            </xs:sequence>
                        </xs:complexType>
                    </xs:element>
                </xs:schema>"""
            )

        # Create valid_data.db
        with open(self.sqlite_file_path, "w") as f:
            f.write("SQLite format 3")

        # Create invalid_data.db
        with open(self.invalid_sqlite_file_path, "w") as f:
            f.write("")

        # Create unsupported_data_type.txt
        with open(self.unsupported_file_path, "w") as f:
            f.write("Unsupported content")

    def test_invalid_xml_message_type(self):
        with self.assertRaises(ValueError):
            process_files(
                "invalid.type",
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                self.csv_file_path,
            )

    def test_missing_xml_template_file(self):
        with self.assertRaises(FileNotFoundError):
            with self.assertLogs(level="ERROR") as log:
                process_files(
                    self.xml_message_type,
                    "tests/data/non_existent_template.xml",
                    self.xsd_schema_file_path,
                    self.csv_file_path,
                )
        self.assertIn(
            """
Error: XML template 'tests/data/non_existent_template.xml' does not exist.
""",
            log.output[0],
        )

    def test_missing_xsd_schema_file(self):
        with self.assertRaises(FileNotFoundError):
            process_files(
                self.xml_message_type,
                self.xml_template_file_path,
                "tests/data/non_existent_schema.xsd",
                self.csv_file_path,
            )

    def test_missing_csv_file(self):
        with self.assertRaises(FileNotFoundError):
            process_files(
                self.xml_message_type,
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                "tests/data/non_existent_data.csv",
            )

    def test_empty_csv_data(self):
        with self.assertRaises(ValueError):
            process_files(
                self.xml_message_type,
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                self.empty_csv_file_path,
            )

    @patch("sys.stdout", new_callable=StringIO)
    def test_single_column_csv_data(self, mock_stdout):
        with self.assertRaises(ValueError):
            process_files(
                self.xml_message_type,
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                self.single_column_csv_file_path,
            )
        self.assertIn(
            "Error: Missing value(s) for column(s)",
            mock_stdout.getvalue(),
        )

    def test_invalid_csv_data(self):
        with self.assertRaises(ValueError):
            process_files(
                self.xml_message_type,
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                self.invalid_csv_file_path,
            )

    def test_valid_csv_data(self):
        with patch(
            "pain001.core.core.generate_xml"
        ) as mock_generate_xml:
            process_files(
                self.xml_message_type,
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                self.csv_file_path,
            )
            mock_generate_xml.assert_called_once()

    def test_valid_sqlite_data(self):
        with (
            patch("pain001.core.core.load_db_data", return_value=[{}]),
            patch(
                "pain001.core.core.validate_db_data", return_value=True
            ),
            patch(
                "pain001.core.core.generate_xml"
            ) as mock_generate_xml,
        ):
            process_files(
                self.xml_message_type,
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                self.sqlite_file_path,
            )
            mock_generate_xml.assert_called_once()

    def test_invalid_sqlite_data(self):
        with (
            patch("pain001.core.core.load_db_data", return_value=[{}]),
            patch(
                "pain001.core.core.validate_db_data", return_value=False
            ),
        ):
            with self.assertRaises(ValueError):
                process_files(
                    self.xml_message_type,
                    self.xml_template_file_path,
                    self.xsd_schema_file_path,
                    self.sqlite_file_path,
                )

    def test_unsupported_data_file_type(self):
        with self.assertRaises(ValueError):
            with self.assertLogs(level="ERROR") as log:
                process_files(
                    self.xml_message_type,
                    self.xml_template_file_path,
                    self.xsd_schema_file_path,
                    self.unsupported_file_path,
                )
        self.assertIn(
            "Error: Unsupported data file type.",
            log.output[0],
        )


if __name__ == "__main__":
    unittest.main()
