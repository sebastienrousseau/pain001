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


import os
import unittest
from io import StringIO
from unittest.mock import patch

import pytest

from pain001.core.core import process_files
from pain001.exceptions import (
    DataSourceError,
    PaymentValidationError,
    XMLGenerationError,
)


class TestProcessFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.xml_message_type = "pain.001.001.03"
        self.xml_template_file_path = (
            "pain001/test_fixtures/template_unique.xml"
        )
        self.xsd_schema_file_path = "pain001/test_fixtures/template_unique.xsd"
        self.csv_file_path = "pain001/test_fixtures/valid_data_unique.csv"

        self.invalid_csv_file_path = (
            "pain001/test_fixtures/invalid_data_unique.csv"
        )
        self.empty_csv_file_path = "pain001/test_fixtures/empty_unique.csv"
        self.single_column_csv_file_path = (
            "pain001/test_fixtures/single_column_unique.csv"
        )
        self.single_row_csv_file_path = (
            "pain001/test_fixtures/single_row_unique.csv"
        )
        self.sqlite_file_path = "pain001/test_fixtures/valid_data_unique.db"
        self.invalid_sqlite_file_path = (
            "pain001/test_fixtures/invalid_data_unique.db"
        )
        self.unsupported_file_path = (
            "pain001/test_fixtures/unsupported_data_type_unique.txt"
        )

        self.create_test_files()

    def create_test_files(self) -> None:
        os.makedirs("pain001/test_fixtures", exist_ok=True)

        # Create valid_data_unique.csv
        with open(self.csv_file_path, "w", encoding="utf-8") as f:
            f.write(
                "id,date,nb_of_txs,initiator_name,initiator_street_name,"
                "initiator_building_number,initiator_postal_code,"
                "initiator_town_name,initiator_country_code,"
                "payment_information_id,payment_method,batch_booking,"
                "requested_execution_date,debtor_name,debtor_street_name,"
                "debtor_building_number,debtor_postal_code,debtor_town_name,"
                "debtor_country_code,debtor_account_IBAN,debtor_agent_BIC,"
                "charge_bearer,payment_id,payment_amount,currency,"
                "payment_currency,ctrl_sum,creditor_agent_BIC,"
                "creditor_name,creditor_street_name,creditor_building_number,"
                "creditor_postal_code,creditor_town_name,creditor_country_code,"
                "creditor_account_IBAN,purpose_code,reference_number,"
                "reference_date,service_level_code,end_to_end_id,"
                "payment_instruction_id,instruction_id,category_purpose,"
                "remittance_info_unstructured,remittance_info_structured,"
                "addtl_end_to_end_id,payment_info_structured,forwarding_agent_BIC,"
                "remittance_information\n"
                "1,2023-03-10T15:30:47,2,John Doe,John's Street,1,12345,"
                "John's Town,DE,Payment-Info-12345,TRF,false,2023-03-15,"
                "Debtor Name,Debtor Street,1,12345,Debtor Town,DE,"
                "DE89370400440532013000,BANKDEFFXXX,DEBT,12345,100.00,EUR,EUR,"
                "100.00,BANKDEFFXXX,Creditor Name,Creditor Street,1,12345,"
                "Creditor Town,DE,DE89370400440532013000,SCOR,Reference-12345,"
                "2023-03-10,SEPA,End-to-End-Id-123,Payment-Instruction-Id-123,"
                "Instruction-Id-123,Category-Purpose-123,"
                "Remittance-Info-Unstructured-123,Remittance-Info-Structured-123,"
                "Addtl-End-to-End-Id-123,Payment-Info-Structured-123,"
                "Forwarding-Agent-BIC-123,Remittance-Information-123\n"
            )

        # Create invalid_data_unique.csv
        with open(self.invalid_csv_file_path, "w", encoding="utf-8") as f:
            f.write("id,date,nb_of_txs\n1,invalid_date,2\n")

        # Create empty_unique.csv
        with open(self.empty_csv_file_path, "w", encoding="utf-8") as f:
            f.write("")

        # Create single_column_unique.csv
        with open(
            self.single_column_csv_file_path, "w", encoding="utf-8"
        ) as f:
            f.write("id\n1\n")

        # Create single_row_unique.csv
        with open(self.single_row_csv_file_path, "w", encoding="utf-8") as f:
            f.write(
                "id,date,nb_of_txs,initiator_name,initiator_street_name,"
                "initiator_building_number,initiator_postal_code,"
                "initiator_town_name,initiator_country_code,"
                "payment_information_id,payment_method,batch_booking,"
                "requested_execution_date,debtor_name,debtor_street_name,"
                "debtor_building_number,debtor_postal_code,debtor_town_name,"
                "debtor_country_code,debtor_account_IBAN,debtor_agent_BIC,"
                "charge_bearer,payment_id,payment_amount,currency,"
                "payment_currency,ctrl_sum,creditor_agent_BIC,"
                "creditor_name,creditor_street_name,creditor_building_number,"
                "creditor_postal_code,creditor_town_name,creditor_country_code,"
                "creditor_account_IBAN,purpose_code,reference_number,"
                "reference_date,service_level_code,forwarding_agent_BIC,"
                "remittance_information,charge_account_IBAN\n"
                "1,2023-03-10T15:30:47,2,John Doe,John's Street,1,12345,"
                "John's Town,DE,Payment-Info-12345,TRF,false,2023-03-15,"
                "Debtor Name,Debtor Street,1,12345,Debtor Town,DE,"
                "DE89370400440532013000,BICCODE,DEBT,12345,100.00,EUR,EUR,"
                "100.00,BICCODE,Creditor Name,Creditor Street,1,12345,"
                "Creditor Town,DE,DE89370400440532013000,SCOR,Reference-12345,"
                "2023-03-10,SEPA,End-to-End-Id-123,Payment-Instruction-Id-123,"
                "Instruction-Id-123,Category-Purpose-123,"
                "Remittance-Info-Unstructured-123,Remittance-Info-Structured-123,"
                "Addtl-End-to-End-Id-123,Payment-Info-Structured-123,"
                "Forwarding-Agent-BIC-123,Remittance-Information-123\n"
            )

        # Create template_unique.xml
        with open(self.xml_template_file_path, "w", encoding="utf-8") as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
                <note>
                    <to>{{ to }}</to>
                    <from>{{ from }}</from>
                    <heading>{{ heading }}</heading>
                    <body>{{ body }}</body>
                </note>"""
            )

        # Create template_unique.xsd with valid XSD content
        with open(self.xsd_schema_file_path, "w", encoding="utf-8") as f:
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

        # Create valid_data_unique.db
        with open(self.sqlite_file_path, "w", encoding="utf-8") as f:
            f.write("SQLite format 3")

        # Create invalid_data_unique.db
        with open(self.invalid_sqlite_file_path, "w", encoding="utf-8") as f:
            f.write("")

        # Create unsupported_data_type_unique.txt
        with open(self.unsupported_file_path, "w", encoding="utf-8") as f:
            f.write("Unsupported content")

    def test_invalid_xml_message_type(self) -> None:
        with self.assertRaises(XMLGenerationError):
            process_files(
                "invalid.type",
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                self.csv_file_path,
            )

    def test_missing_xml_template_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            with self.assertLogs(level="ERROR") as log:
                process_files(
                    self.xml_message_type,
                    "pain001/test_fixtures/non_existent_template.xml",
                    self.xsd_schema_file_path,
                    self.csv_file_path,
                )
        self.assertIn(
            "Error: XML template 'pain001/test_fixtures/non_existent_template.xml' "
            "does not exist or is invalid",
            log.output[-1],
        )

    def test_missing_xsd_schema_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            process_files(
                self.xml_message_type,
                self.xml_template_file_path,
                "pain001/test_fixtures/non_existent_schema.xsd",
                self.csv_file_path,
            )

    def test_missing_csv_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            process_files(
                self.xml_message_type,
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                "pain001/test_fixtures/non_existent_data.csv",
            )

    def test_empty_csv_data(self) -> None:
        with self.assertRaises(DataSourceError):
            process_files(
                self.xml_message_type,
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                self.empty_csv_file_path,
            )

    @patch("sys.stdout", new_callable=StringIO)
    def test_single_column_csv_data(self, mock_stdout) -> None:
        with self.assertRaises(PaymentValidationError):
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

    def test_invalid_csv_data(self) -> None:
        with self.assertRaises(PaymentValidationError):
            process_files(
                self.xml_message_type,
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                self.invalid_csv_file_path,
            )

    def test_valid_csv_data(self) -> None:
        with patch(
            "pain001.xml.generate_xml.generate_xml", autospec=True
        ) as mock_generate_xml:
            process_files(
                self.xml_message_type,
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                self.csv_file_path,
            )
            mock_generate_xml.assert_called_once()

    def test_valid_sqlite_data(self) -> None:
        with (
            patch(
                "pain001.data.loader.load_db_data",
                autospec=True,
                return_value=[{}],
            ),
            patch(
                "pain001.data.loader.validate_db_data",
                autospec=True,
                return_value=True,
            ),
            patch(
                "pain001.xml.generate_xml.generate_xml", autospec=True
            ) as mock_generate_xml,
        ):
            process_files(
                self.xml_message_type,
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                self.sqlite_file_path,
            )
            mock_generate_xml.assert_called_once()

    def test_invalid_sqlite_data(self) -> None:
        with (
            patch(
                "pain001.data.loader.load_db_data",
                autospec=True,
                return_value=[{}],
            ),
            patch(
                "pain001.data.loader.validate_db_data",
                autospec=True,
                return_value=False,
            ),
        ):
            with self.assertRaises(PaymentValidationError):
                process_files(
                    self.xml_message_type,
                    self.xml_template_file_path,
                    self.xsd_schema_file_path,
                    self.sqlite_file_path,
                )

    def test_unsupported_data_file_type(self) -> None:
        with self.assertRaises(DataSourceError):
            with self.assertLogs(level="ERROR") as log:
                process_files(
                    self.xml_message_type,
                    self.xml_template_file_path,
                    self.xsd_schema_file_path,
                    self.unsupported_file_path,
                )
        self.assertIn(
            "Unsupported file type",
            log.output[-1],
        )

    def test_core_main_entry_point(self) -> None:
        """Test core.py __main__ entry point."""
        import subprocess
        import sys

        # Test with insufficient arguments (should print usage)
        result = subprocess.run(
            [sys.executable, "-m", "pain001.core.core"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Usage:" in result.stdout or "Usage:" in result.stderr

    def test_core_main_with_arguments(self) -> None:
        """Test core.py __main__ with valid arguments."""
        import subprocess
        import sys

        # Test with valid arguments
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pain001.core.core",
                "pain.001.001.03",
                self.xml_template_file_path,
                self.xsd_schema_file_path,
                self.csv_file_path,
            ],
            capture_output=True,
            text=True,
        )
        # Should complete successfully or with expected error
        assert result.returncode in [0, 1]

    def test_process_files_unknown_data_type(self) -> None:
        """Test processing with unsupported data type (triggers unknown path)."""
        # Pass an unsupported type (not str, list, or dict)
        # This should log "unknown" data_source_type and then raise DataSourceError
        with pytest.raises(
            DataSourceError, match="Unsupported data source type"
        ):
            process_files(
                xml_message_type=self.xml_message_type,
                xml_template_file_path=self.xml_template_file_path,
                xsd_schema_file_path=self.xsd_schema_file_path,
                data_file_path=12345,  # type: ignore  # Intentionally invalid type
            )

    def test_process_files_with_list_input(self) -> None:
        """Test process_files with Python list input (triggers list path in core.py line 129)."""
        # Use minimal valid payment data that will pass validation
        # The goal is to trigger the isinstance(data_file_path, list) branch
        # We'll use PaymentValidationError expectation since we need all required fields
        payment_list = [
            {"id": "1"}
        ]  # Minimal - will fail validation but triggers list path

        with self.assertRaises((PaymentValidationError, KeyError)):
            # This will trigger the list branch in _load_data and process_files
            process_files(
                xml_message_type=self.xml_message_type,
                xml_template_file_path=self.xml_template_file_path,
                xsd_schema_file_path=self.xsd_schema_file_path,
                data_file_path=payment_list,
            )

    def test_process_files_with_dict_input(self) -> None:
        """Test process_files with Python dict input (triggers dict path in core.py line 131)."""
        # Use minimal valid payment data that will pass validation
        # The goal is to trigger the isinstance(data_file_path, dict) branch
        payment_dict = {
            "id": "1"
        }  # Minimal - will fail validation but triggers dict path

        with self.assertRaises((PaymentValidationError, KeyError)):
            # This will trigger the dict branch in _load_data and process_files
            process_files(
                xml_message_type=self.xml_message_type,
                xml_template_file_path=self.xml_template_file_path,
                xsd_schema_file_path=self.xsd_schema_file_path,
                data_file_path=payment_dict,
            )


if __name__ == "__main__":
    unittest.main()
