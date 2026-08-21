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

"""Performance benchmarks for pain001 library."""

import csv
import os
import tempfile
from pathlib import Path

import pytest

from pain001.csv.load_csv_data import load_csv_data
from pain001.xml.generate_xml import generate_xml

# Kept in step with SLO_XML_GEN in the Makefile, which previously only
# printed a number in a banner and never asserted it.
#
# History worth keeping, because the number moved twice for opposite
# reasons. The banner originally said 0.5s per 1000 transactions and had
# never been checked, because the benchmark meant to check it was timing
# an exception. Once it measured real work, a 1000-transaction batch (a
# 1.4 MiB document) came out at ~0.50s at best and ~0.82s on average, so
# the advertised figure did not hold and the guard was set to a
# deliberately loose 2.0s.
#
# It holds comfortably now. XSD validation was 93% of the cost, and with
# libxml2 doing the validating it is 39%:
#
#   generate_xml_string, 1000 transactions   0.501s -> 0.082s  (6.1x)
#   of which XSD validation                  0.465s -> 0.032s
#
# So the threshold comes down from 2.0s to 0.5s — which is, as it
# happens, the figure the banner claimed all along, now measured rather
# than asserted. It keeps roughly 5x headroom over the ~0.10s the
# benchmark reports here, which is the margin a shared runner needs; CI
# measured 0.65-0.88s before this change and should now sit far below it.
#
# Note this guard is only meaningful where lxml is installed. The suite
# installs it, and pain001[fast] declares it; without it the pure-Python
# validator is still correct, just slower, and this threshold would be
# the thing that notices.
SLO_XML_GEN_SECONDS = 0.5
SLO_BATCH_SIZE = 1000


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

    @pytest.mark.perf
    def test_xml_generation_performance(self, benchmark, tmp_path) -> None:
        """Benchmark XML generation against the documented SLO.

        The Makefile states an SLO of ``< 0.5s per 1000 transactions``.
        This measures that: one generation of a 1000-transaction batch
        against the real template and schema, written to disk.

        The previous version passed ``None`` for both the template and
        the schema path and wrapped the call in a bare ``except
        Exception`` commented "expected". ``generate_xml`` rejects an
        empty path before doing any work, so what was timed was a
        ``ValueError`` being raised -- which is why it reported
        single-digit microseconds for a batch job.
        """
        template = Path("pain001/templates/pain.001.001.03/template.xml")
        schema = Path("pain001/templates/pain.001.001.03/pain.001.001.03.xsd")
        assert template.is_file(), f"missing template: {template}"
        assert schema.is_file(), f"missing schema: {schema}"

        record: dict[str, object] = {
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
            "debtor_agent_BIC": "BANKDEFFXXX",
            "charge_bearer": "DEBT",
            "payment_id": "1",
            "payment_amount": "100.00",
            "currency": "EUR",
            "payment_currency": "EUR",
            "ctrl_sum": "100.00",
            "creditor_agent_BIC": "SPUEDE2UXXX",
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
            "forwarding_agent_BIC": "SPUEDE2UXXX",
            "remittance_information": "REM",
        }

        data = []
        for i in range(SLO_BATCH_SIZE):
            row = dict(record)
            row["payment_id"] = f"PMT-{i:06d}"
            row["id"] = str(i)
            data.append(row)

        out = tmp_path / "batch.xml"

        def generate() -> None:
            generate_xml(
                data,
                "pain.001.001.03",
                str(template),
                str(schema),
                output_path=str(out),
            )

        benchmark(generate)

        mean = benchmark.stats.stats.mean
        assert mean < SLO_XML_GEN_SECONDS, (
            f"XML generation of {SLO_BATCH_SIZE} transactions took "
            f"{mean:.3f}s on average, over the {SLO_XML_GEN_SECONDS}s SLO"
        )
