# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

from pathlib import Path

import pytest

from pain001.xml.generate_xml import generate_xml_string


def test_template_loader_blocks_jinja_filesystem_directives(tmp_path) -> None:
    template_path = tmp_path / "template.xml"
    schema_path = tmp_path / "schema.xsd"
    template_path.write_text(
        '{% include "secret.xml" %}',
        encoding="utf-8",
    )
    schema_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
           xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
  <xs:element name="Document" type="xs:string"/>
</xs:schema>
""",
        encoding="utf-8",
    )
    data = [
        {
            "id": "1",
            "date": "2026-01-01T00:00:00",
            "nb_of_txs": "1",
            "initiator_name": "Test",
            "payment_id": "PAY-1",
            "payment_method": "TRF",
            "requested_execution_date": "2026-01-02",
            "debtor_name": "Debtor",
            "debtor_account_IBAN": "DE89370400440532013000",
            "debtor_agent_BIC": "DEUTDEFF",
            "charge_bearer": "SLEV",
            "payment_amount": "1.00",
            "payment_currency": "EUR",
            "creditor_agent_BIC": "DEUTDEFF",
            "creditor_name": "Creditor",
            "creditor_account_IBAN": "DE89370400440532013000",
            "remittance_information": "test",
        }
    ]
    with pytest.raises(ValueError, match="disabled Jinja filesystem"):
        generate_xml_string(
            data,
            "pain.001.001.11",
            str(template_path),
            str(schema_path),
        )


def test_v12_template_bundle_exists() -> None:
    base = Path("pain001/templates/pain.001.001.12")
    assert (base / "template.xml").exists()
    assert (base / "pain.001.001.12.xsd").exists()
    assert (base / "metadata.yaml").exists()
