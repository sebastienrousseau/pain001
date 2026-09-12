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

"""The CSV pipeline extension: the shared column vocabulary (0.0.69).

Every optional column renders its element in both extended editions,
an account may be an IBAN or a number, an agent a BIC or a clearing
member, and the corpus is the golden target: every pain.001 market file
but the cheque regenerates through the pipeline with the same values.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pain001 import generate_xml_string
from pain001.constants import TEMPLATES_DIR
from pain001.corpus import get_file
from pain001.exceptions import PaymentValidationError
from pain001.twins import to_iso_json, to_records
from pain001.twins.records import input_columns
from pain001.xml.message_registry import prepare_xml_data

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_input_columns  # noqa: E402

EXTENDED = ["pain.001.001.03", "pain.001.001.09", "pain.001.001.13"]

BASE = {
    "id": "MSG-1",
    "date": "2026-09-12T08:00:00",
    "initiator_name": "Elm Road Developments Ltd",
    "payment_id": "E2E-1",
    "requested_execution_date": "2026-09-12",
    "debtor_name": "Elm Road Developments Ltd",
    "debtor_account_IBAN": "GB07OUER60969382168086",
    "debtor_agent_BIC": "OICSGB40",
    "payment_amount": "100.00",
    "currency": "GBP",
    "creditor_agent_BIC": "NPHBGBS0",
    "creditor_name": "Northgate Timber Supplies",
    "creditor_account_IBAN": "GB20OYKL60284231569811",
}

OPTIONAL = {
    "payment_information_id": ("PmtInfId", "PMT-INF-1"),
    "batch_booking": ("BtchBookg", "true"),
    "instruction_priority": ("InstrPrty", "HIGH"),
    "service_level_code": ("SvcLvl", "URGP"),
    "local_instrument_code": ("LclInstrm", "INST"),
    "category_purpose_code": ("CtgyPurp", "SALA"),
    "initiator_street_name": ("StrtNm", "Elm Road"),
    "initiator_building_number": ("BldgNb", "14"),
    "initiator_postal_code": ("PstCd", "SW1A 1AA"),
    "initiator_town_name": ("TwnNm", "London"),
    "initiator_country_subdivision": ("CtrySubDvsn", "England"),
    "initiator_country_code": ("Ctry", "GB"),
    "initiator_address_line": ("AdrLine", "14 Elm Road"),
    "initiator_id": ("Othr", "123456"),
    "initiator_id_scheme": ("SchmeNm", "CUST"),
    "debtor_id": ("Othr", "123456"),
    "debtor_id_scheme_proprietary": ("Prtry", "KBO-BCE"),
    "debtor_account_currency": ("Ccy", "GBP"),
    "debtor_agent_name": ("Nm", "Elm Bank"),
    "debtor_agent_town_name": ("TwnNm", "London"),
    "debtor_agent_country_code": ("Ctry", "GB"),
    "ultimate_debtor_name": ("UltmtDbtr", "Elm Road Holdings"),
    "instruction_id": ("InstrId", "INSTR-1"),
    "creditor_street_name": ("StrtNm", "Bridge Street"),
    "creditor_town_name": ("TwnNm", "Leeds"),
    "creditor_country_code": ("Ctry", "GB"),
    "creditor_agent_name": ("Nm", "Northgate Bank"),
    "creditor_agent_country_code": ("Ctry", "GB"),
    "creditor_account_currency": ("Ccy", "GBP"),
    "ultimate_creditor_name": ("UltmtCdtr", "Northgate Group"),
    "purpose_code": ("Purp", "GDDS"),
    "regulatory_reporting_indicator": ("DbtCdtRptgInd", "CRED"),
    "regulatory_reporting_country": ("RgltryRptg", "AE"),
    "regulatory_reporting_code": ("Cd", "GDS"),
    "regulatory_reporting_info": ("Inf", "/BENEFRES/AE//GDS"),
    "remittance_information": ("Ustrd", "Invoice 1"),
    "creditor_reference": ("CdtrRefInf", "RF18539007547034"),
    "creditor_reference_type": ("CdOrPrtry", "SCOR"),
    "creditor_reference_issuer": ("Issr", "ISO"),
    "additional_remittance_information": ("AddtlRmtInf", "Thank you"),
}


def _render(row: dict, version: str) -> str:
    template_dir = Path(TEMPLATES_DIR) / version
    return generate_xml_string(
        [dict(row)],
        version,
        str(template_dir / "template.xml"),
        str(template_dir / f"{version}.xsd"),
    )


@pytest.mark.parametrize("version", EXTENDED)
def test_base_row_renders_without_optional_elements(version: str) -> None:
    """The mandatory columns alone give a valid, minimal document."""
    xml = _render(BASE, version)
    assert "<CtrlSum>100.00</CtrlSum>" in xml
    for tag in (
        "PmtTpInf",
        "PstlAdr",
        "UltmtDbtr",
        "Purp",
        "RgltryRptg",
        "RmtInf",
    ):
        assert f"<{tag}>" not in xml, tag
    assert "<IBAN>GB07OUER60969382168086</IBAN>" in xml
    assert ("<BtchBookg>false</BtchBookg>" in xml) == (
        version == "pain.001.001.03"
    )


@pytest.mark.parametrize("version", EXTENDED)
@pytest.mark.parametrize("column", sorted(OPTIONAL))
def test_each_optional_column_renders_its_element(
    version: str, column: str
) -> None:
    """Given alone, an optional column adds exactly its element."""
    tag, value = OPTIONAL[column]
    row = dict(BASE, **{column: value})
    if column in (
        "creditor_reference_type",
        "creditor_reference_issuer",
        "additional_remittance_information",
    ):
        row["creditor_reference"] = "RF18539007547034"
    if column == "creditor_reference_issuer":
        row["creditor_reference_type"] = "SCOR"  # Issr sits inside Tp
    if column == "initiator_id_scheme":
        row["initiator_id"] = "123456"
    if column == "debtor_id_scheme_proprietary":
        row["debtor_id"] = "123456"
    if (
        column.startswith("regulatory_reporting_")
        and column != "regulatory_reporting_code"
    ):
        row["regulatory_reporting_code"] = "GDS"
    if column == "regulatory_reporting_code" and version == "pain.001.001.13":
        tag = "RptgCd"  # renamed in the 2024 edition
    xml = _render(row, version)
    assert f"<{tag}>" in xml or f"<{tag} " in xml, (column, tag)
    assert value in xml, column


@pytest.mark.parametrize("version", EXTENDED)
def test_accounts_and_agents_take_either_form(version: str) -> None:
    """An account number with a scheme, and a clearing member without a BIC."""
    row = dict(BASE)
    del row["debtor_account_IBAN"], row["creditor_account_IBAN"]
    del row["debtor_agent_BIC"], row["creditor_agent_BIC"]
    row.update(
        debtor_account_number="12345678",
        debtor_account_scheme="BBAN",
        debtor_agent_clearing_system="GBDSC",
        debtor_agent_member_id="040004",
        creditor_account_number="87654321",
        creditor_account_scheme_proprietary="BGNR",
        creditor_agent_clearing_system="GBDSC",
        creditor_agent_member_id="309634",
    )
    xml = _render(row, version)
    assert "<IBAN>" not in xml and "<Othr>" in xml
    assert "<Cd>BBAN</Cd>" in xml and "<Prtry>BGNR</Prtry>" in xml
    assert "<MmbId>040004</MmbId>" in xml and "<Cd>GBDSC</Cd>" in xml
    assert "BICFI" not in xml and "<BIC>" not in xml
    for gone in ("debtor_account_number", "debtor_agent_member_id"):
        broken = dict(row)
        del broken[gone]
        with pytest.raises(PaymentValidationError, match=r"\(or"):
            prepare_xml_data([broken], version)


def test_datetime_execution_date_in_the_modern_editions() -> None:
    """A date-time renders DtTm in .09; .03 keeps the date."""
    row = dict(BASE)
    del row["requested_execution_date"]
    row["requested_execution_datetime"] = "2026-09-12T10:00:00"
    assert "<DtTm>2026-09-12T10:00:00</DtTm>" in _render(
        row, "pain.001.001.09"
    )
    with pytest.raises(
        PaymentValidationError, match="requested_execution_date"
    ):
        prepare_xml_data([row], "pain.001.001.03")


def test_v03_referred_document_and_defaults() -> None:
    """The .03 referred document still renders; its instruction id defaults."""
    row = dict(BASE, reference_number="INV-7", reference_date="2026-09-01")
    xml = _render(row, "pain.001.001.03")
    assert "<Nb>INV-7</Nb>" in xml and "<RltdDt>2026-09-01</RltdDt>" in xml
    assert "<InstrId>TX-1</InstrId>" in xml
    assert "<ChrgBr>SLEV</ChrgBr>" in xml


@pytest.mark.parametrize("version", ["pain.001.001.03", "pain.001.001.09"])
def test_input_schema_names_the_vocabulary(version: str) -> None:
    """Every rendered column is in the input schema, and the schema's
    required list is the preparer's unconditional set."""
    columns, required = input_columns(version)
    for column in OPTIONAL:
        if version == "pain.001.001.03" and column == "uetr":
            continue
        assert column in columns, column
    assert "debtor_account_IBAN" not in required
    assert {
        "id",
        "date",
        "initiator_name",
        "payment_id",
        "debtor_name",
    } <= set(required)


def test_corpus_is_the_golden_target() -> None:
    """A regenerated CHAPS file carries the same twin values at every mapped path."""
    version = "pain.001.001.09"
    xml = get_file("gb.chaps.property-purchase", version)
    records = to_records(xml, version)
    assert records.gap == [] and records.missing_required == []
    regenerated = _render(records.rows[0], version)
    before = to_iso_json(xml, version)["Document"]["CstmrCdtTrfInitn"]
    after = to_iso_json(regenerated, version)["Document"]["CstmrCdtTrfInitn"]
    assert (
        after["PmtInf"][0]["CdtTrfTxInf"] == before["PmtInf"][0]["CdtTrfTxInf"]
    )
    assert after["GrpHdr"]["InitgPty"] == before["GrpHdr"]["InitgPty"]


def test_column_table_script(capsys) -> None:
    """The documentation table comes from the same mapping."""
    assert generate_input_columns.main(["pain.001.001.09"]) == 0
    out = capsys.readouterr().out
    assert (
        "| `creditor_account_number` |" in out and "CdtrAcct/Id/Othr/Id" in out
    )
    assert generate_input_columns.main([]) == 0
    assert "## pain.001.001.03" in capsys.readouterr().out


def test_boolean_column_forms() -> None:
    """JSON booleans, 1/0, yes/no and blanks all resolve; blank means absent."""
    from pain001.xml.message_registry import _boolean

    assert _boolean({"batch_booking": True}, "batch_booking") == "true"
    assert _boolean({"batch_booking": False}, "batch_booking") == "false"
    assert _boolean({"batch_booking": "yes"}, "batch_booking") == "true"
    assert _boolean({"batch_booking": "0"}, "batch_booking") == "false"
    assert _boolean({"batch_booking": "  "}, "batch_booking") is None
    assert _boolean({}, "batch_booking") is None
    xml = _render(dict(BASE, batch_booking=False), "pain.001.001.09")
    assert "<BtchBookg>false</BtchBookg>" in xml
