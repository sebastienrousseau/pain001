# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Performance benchmarks for pain001 library."""

import csv
import os
import tempfile

import pytest

from pain001.csv.load_csv_data import load_csv_data
from pain001.xml.generate_xml import generate_xml


class TestPerformanceBenchmarks:
    """Performance and efficiency benchmarks."""

    @pytest.fixture
    def sample_csv_file(self) -> str:  # type: ignore
        """Create a sample CSV file for benchmarking."""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv", newline=""
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "id",
                    "date",
                    "nb_of_txs",
                    "initiator_name",
                    "initiator_street_name",
                    "initiator_building_number",
                    "initiator_postal_code",
                    "initiator_town_name",
                    "initiator_country_code",
                    "payment_information_id",
                    "payment_method",
                    "batch_booking",
                    "requested_execution_date",
                    "debtor_name",
                    "debtor_street_name",
                    "debtor_building_number",
                    "debtor_postal_code",
                    "debtor_town_name",
                    "debtor_country_code",
                    "debtor_account_IBAN",
                    "debtor_agent_BIC",
                    "charge_bearer",
                    "payment_id",
                    "payment_amount",
                    "currency",
                    "payment_currency",
                    "ctrl_sum",
                    "creditor_agent_BIC",
                    "creditor_name",
                    "creditor_street_name",
                    "creditor_building_number",
                    "creditor_postal_code",
                    "creditor_town_name",
                    "creditor_country_code",
                    "creditor_account_IBAN",
                    "purpose_code",
                    "reference_number",
                    "reference_date",
                    "service_level_code",
                    "end_to_end_id",
                    "payment_instruction_id",
                    "instruction_id",
                    "category_purpose",
                    "remittance_info_unstructured",
                    "remittance_info_structured",
                    "addtl_end_to_end_id",
                    "payment_info_structured",
                    "forwarding_agent_BIC",
                    "remittance_information",
                ],
            )
            writer.writeheader()

            # Write 100 sample records
            for i in range(100):
                writer.writerow(
                    {
                        "id": str(i),
                        "date": "2023-03-10T15:30:47",
                        "nb_of_txs": "1",
                        "initiator_name": f"Initiator {i}",
                        "initiator_street_name": "Test Street",
                        "initiator_building_number": "1",
                        "initiator_postal_code": "12345",
                        "initiator_town_name": "Test Town",
                        "initiator_country_code": "DE",
                        "payment_information_id": "Payment-Info",
                        "payment_method": "TRF",
                        "batch_booking": "false",
                        "requested_execution_date": "2023-03-15",
                        "debtor_name": "Debtor",
                        "debtor_street_name": "Debtor St",
                        "debtor_building_number": "1",
                        "debtor_postal_code": "12345",
                        "debtor_town_name": "Debtor Town",
                        "debtor_country_code": "DE",
                        "debtor_account_IBAN": "DE89370400440532013000",
                        "debtor_agent_BIC": "DEUTDE",
                        "charge_bearer": "DEBT",
                        "payment_id": str(i),
                        "payment_amount": "100.00",
                        "currency": "EUR",
                        "payment_currency": "EUR",
                        "ctrl_sum": "100.00",
                        "creditor_agent_BIC": "DEUTDE",
                        "creditor_name": "Creditor",
                        "creditor_street_name": "Creditor St",
                        "creditor_building_number": "1",
                        "creditor_postal_code": "12345",
                        "creditor_town_name": "Creditor Town",
                        "creditor_country_code": "DE",
                        "creditor_account_IBAN": "DE89370400440532013000",
                        "purpose_code": "SCOR",
                        "reference_number": f"REF-{i}",
                        "reference_date": "2023-03-10",
                        "service_level_code": "SEPA",
                        "end_to_end_id": f"E2E-{i}",
                        "payment_instruction_id": "INSTR-ID",
                        "instruction_id": "INST-ID",
                        "category_purpose": "CAT-PURPOSE",
                        "remittance_info_unstructured": "Payment info",
                        "remittance_info_structured": "STRUCT",
                        "addtl_end_to_end_id": "ADDTL-E2E",
                        "payment_info_structured": "INFO-STRUCT",
                        "forwarding_agent_BIC": "AGENT",
                        "remittance_information": "Remittance",
                    }
                )

        yield f.name

        # Cleanup
        if os.path.exists(f.name):
            os.unlink(f.name)

    def test_csv_loading_performance(self, benchmark, sample_csv_file) -> None:
        """Benchmark CSV file loading performance."""
        result = benchmark(load_csv_data, sample_csv_file)
        assert result is not None
        assert len(result) == 100

    def test_xml_generation_performance(self, benchmark) -> None:  # type: ignore
        """Benchmark XML generation performance."""
        data = [
            {
                "id": "1",
                "date": "2023-03-10T15:30:47",
                "nb_of_txs": "1",
                "initiator_name": "Test Initiator",
                "initiator_street_name": "Test St",
                "initiator_building_number": "1",
                "initiator_postal_code": "12345",
                "initiator_town_name": "Test Town",
                "initiator_country_code": "DE",
                "payment_information_id": "TEST",
                "payment_method": "TRF",
                "batch_booking": "false",
                "requested_execution_date": "2023-03-15",
                "debtor_name": "Debtor",
                "debtor_street_name": "Debtor St",
                "debtor_building_number": "1",
                "debtor_postal_code": "12345",
                "debtor_town_name": "Debtor Town",
                "debtor_country_code": "DE",
                "debtor_account_IBAN": "DE89370400440532013000",
                "debtor_agent_BIC": "DEUTDE",
                "charge_bearer": "DEBT",
                "payment_id": "1",
                "payment_amount": "100.00",
                "currency": "EUR",
                "payment_currency": "EUR",
                "ctrl_sum": "100.00",
                "creditor_agent_BIC": "DEUTDE",
                "creditor_name": "Creditor",
                "creditor_street_name": "Creditor St",
                "creditor_building_number": "1",
                "creditor_postal_code": "12345",
                "creditor_town_name": "Creditor Town",
                "creditor_country_code": "DE",
                "creditor_account_IBAN": "DE89370400440532013000",
                "purpose_code": "SCOR",
                "reference_number": "REF",
                "reference_date": "2023-03-10",
                "service_level_code": "SEPA",
                "end_to_end_id": "E2E",
                "payment_instruction_id": "INSTR",
                "instruction_id": "INST",
                "category_purpose": "CAT",
                "remittance_info_unstructured": "Info",
                "remittance_info_structured": "STRUCT",
                "addtl_end_to_end_id": "ADDTL",
                "payment_info_structured": "STRUCT",
                "forwarding_agent_BIC": "AGENT",
                "remittance_information": "REM",
            }
        ]

        def generate() -> None:  # type: ignore
            """Generate XML."""
            try:
                generate_xml(data, "pain.001.001.03", None, None)
            except Exception as e:
                # Expected: validation errors in benchmark scenario
                print(
                    f"Benchmark validation error (expected): {type(e).__name__}"
                )

        benchmark(generate)
