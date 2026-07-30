# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

from pathlib import Path

from pain001.core.core import process_files_streaming


def test_process_files_streaming_generates_multiple_xml_outputs(
    tmp_path: Path,
) -> None:
    template = Path("pain001/templates/pain.001.001.03/template.xml").resolve()
    schema = Path(
        "pain001/templates/pain.001.001.03/pain.001.001.03.xsd"
    ).resolve()
    data = tmp_path / "payments.csv"
    data.write_text(
        (
            "id,date,nb_of_txs,initiator_name,initiator_street_name,"
            "initiator_building_number,initiator_postal_code,"
            "initiator_town_name,initiator_country_code,payment_id,"
            "payment_method,batch_booking,requested_execution_date,"
            "debtor_name,debtor_street_name,debtor_building_number,"
            "debtor_postal_code,debtor_town_name,debtor_country_code,"
            "debtor_account_IBAN,debtor_agent_BIC,charge_bearer,"
            "payment_amount,payment_currency,creditor_agent_BIC,"
            "creditor_name,creditor_street_name,creditor_building_number,"
            "creditor_postal_code,creditor_town_name,creditor_country_code,"
            "creditor_account_IBAN,purpose_code,reference_number,reference_date\n"
            "MSG001,2026-01-15T10:30:00,2,Test Corp,Main,1,12345,TestCity,US,"
            "PMT001,TRF,false,2026-01-20,John Doe,Oak,2,54321,DebtorCity,US,"
            "GB33BUKB20201555555555,BUKBGB22,SLEV,100.00,EUR,ABCDUS33,Jane Smith,"
            "Elm,3,67890,CreditorCity,US,FR1420041010050500013M02606,SALA,REF1,2026-01-15\n"
            "MSG001,2026-01-15T10:30:00,2,Test Corp,Main,1,12345,TestCity,US,"
            "PMT002,TRF,false,2026-01-20,John Doe,Oak,2,54321,DebtorCity,US,"
            "GB33BUKB20201555555555,BUKBGB22,SLEV,200.00,EUR,ABCDUS33,Jane Smith,"
            "Elm,3,67890,CreditorCity,US,FR1420041010050500013M02606,SALA,REF2,2026-01-15\n"
        ),
        encoding="utf-8",
    )

    outputs = process_files_streaming(
        "pain.001.001.03",
        str(template),
        str(schema),
        str(data),
        chunk_size=1,
    )

    assert len(outputs) == 2
    assert all(Path(path).exists() for path in outputs)
