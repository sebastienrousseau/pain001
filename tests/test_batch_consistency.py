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

"""One file, one payment information block: mixed batches are refused.

Every bundled template renders a single ``PmtInf`` whose header
(debtor, debtor account and agent, execution date, method, batch
booking, charge bearer, payment type; the creditor for pain.008) is
read from the first row. Rows that disagree on any of those columns
used to collapse silently under row 1. These tests pin the refusal and
prove, against the templates themselves, that no accepted batch drops
a row's payment-information value.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest
from lxml import etree

from pain001.exceptions import PaymentValidationError
from pain001.xml.batch_consistency import (
    PMTINF_COLUMNS,
    require_single_payment_information,
)
from pain001.xml.generate_xml import generate_xml_string
from pain001.xml.message_registry import MESSAGE_REGISTRY, prepare_xml_data

TEMPLATES = Path("pain001/templates")

# Alternative, schema-plausible values for every column a preparer
# reads. A value the XSD rejects only skips that probe.
_ALTERNATES: dict[str, str] = {
    "payment_information_id": "PMTINF-ALT-1",
    "payment_method": "CHK",
    "instruction_priority": "HIGH",
    "service_level_code": "NURG",
    "local_instrument_code": "INST",
    "local_instrument_proprietary": "LOCALALT",
    "category_purpose_code": "SUPP",
    "requested_execution_date": "2030-01-02",
    "requested_execution_datetime": "2030-01-02T10:00:00",
    "debtor_name": "Other Debtor Ltd",
    "debtor_street_name": "Other Street",
    "debtor_building_number": "9",
    "debtor_postal_code": "99999",
    "debtor_town_name": "Othertown",
    "debtor_country_subdivision": "BY",
    "debtor_country_code": "FR",
    "debtor_country": "FR",
    "debtor_address_line": "Building 7",
    "debtor_lei": "5493001KJTIIGC8Y1R12",
    "debtor_id": "DEBTOR-ALT",
    "debtor_id_scheme": "TXID",
    "debtor_id_scheme_proprietary": "PRTRYALT",
    "debtor_account_IBAN": "FR1420041010050500013M02606",
    "debtor_account_number": "123456789",
    "debtor_account_scheme": "BBAN",
    "debtor_account_scheme_proprietary": "PRTRYALT",
    "debtor_account_currency": "USD",
    "debtor_agent_BIC": "BNPAFRPPXXX",
    "debtor_agent_clearing_system": "USABA",
    "debtor_agent_member_id": "021000021",
    "debtor_agent_name": "Other Bank",
    "debtor_agent_town_name": "Paris",
    "debtor_agent_country_subdivision": "IDF",
    "debtor_agent_country_code": "FR",
    "ultimate_debtor_name": "Ultimate Alt",
    "creditor_name": "Other Creditor",
    "creditor_account_IBAN": "FR1420041010050500013M02606",
    "creditor_agent_BIC": "BNPAFRPPXXX",
    "creditor_agent_BICFI": "BNPAFRPPXXX",
    "payment_amount": "99.00",
    "remittance_information": "Alternate remittance",
    "purpose_code": "SALA",
    "reference_number": "REF-ALT",
    "mandate_id": "MANDATE-ALT",
    "date_of_signature": "2020-02-02",
    "debtor_agent_account_IBAN": "FR1420041010050500013M02606",
    "charge_account_IBAN": "FR1420041010050500013M02606",
    "instruction_for_debtor_agent": "Alt instruction",
}

_FLIPS: dict[str, tuple[str, str]] = {
    "batch_booking": ("true", "false"),
    "charge_bearer": ("SLEV", "SHAR"),
    "sequence_type": ("RCUR", "FRST"),
}


# Columns the .03/.09 templates render only next to a sibling (an
# account number only without an IBAN, a scheme only with an id, a
# clearing system only with a member id). The probe sets the sibling on
# both rows so the column is visible to the oracle.
_ACCOUNT_NUMBER = {"debtor_account_IBAN": "", "debtor_account_number": "111"}
_ENABLERS: dict[str, dict[str, str]] = {
    "debtor_account_number": _ACCOUNT_NUMBER,
    "debtor_account_scheme": _ACCOUNT_NUMBER,
    "debtor_account_scheme_proprietary": _ACCOUNT_NUMBER,
    "debtor_agent_clearing_system": {"debtor_agent_member_id": "021000021"},
    "debtor_id_scheme": {"debtor_id": "DEBTOR-1"},
    "debtor_id_scheme_proprietary": {"debtor_id": "DEBTOR-1"},
}
_STRUCTURED = frozenset({"legacy_v03", "modern_v09_to_v12"})


def _first_row(message_type: str) -> dict[str, Any]:
    """The first row of the bundled sample CSV for ``message_type``."""
    path = TEMPLATES / message_type / "template.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return dict(next(csv.DictReader(handle)))


def _base_row(message_type: str, column: str) -> dict[str, Any]:
    """Row 1 for a probe of ``column``, with any sibling it needs."""
    base = _first_row(message_type)
    if MESSAGE_REGISTRY[message_type].family in _STRUCTURED:
        base.update(_ENABLERS.get(column, {}))
    return base


def _alternate(column: str, base: dict[str, Any]) -> str:
    """A value for ``column`` that differs from the base row's."""
    if column in _FLIPS:
        first, second = _FLIPS[column]
        current = str(base.get(column, "")).strip().lower()
        return second if current == first.lower() else first
    return _ALTERNATES[column]


def _render(message_type: str, rows: list[dict[str, Any]]) -> str:
    """Generate and XSD-validate ``rows`` with the bundled template."""
    folder = TEMPLATES / message_type
    return generate_xml_string(
        rows,
        message_type,
        str(folder / "template.xml"),
        str(folder / f"{message_type}.xsd"),
    )


def _pmtinf_header(xml: str) -> bytes:
    """The PmtInf block without its transactions and computed totals."""
    root = etree.fromstring(xml.encode("utf-8"))
    pmtinf = root.find(".//{*}PmtInf")
    assert pmtinf is not None
    for child in list(pmtinf):
        name = etree.QName(child).localname
        if name in ("CdtTrfTxInf", "DrctDbtTxInf", "NbOfTxs", "CtrlSum"):
            pmtinf.remove(child)
    return etree.tostring(pmtinf, method="c14n")


def _probe(
    message_type: str, column: str
) -> tuple[bool, bytes | None, bytes | None]:
    """Vary ``column`` on row 2 only; report refusal and both headers."""
    base = _base_row(message_type, column)
    varied = dict(base)
    varied[column] = _alternate(column, base)
    try:
        alone = _pmtinf_header(_render(message_type, [varied]))
    except (PaymentValidationError, RuntimeError, ValueError):
        alone = None
    first = _pmtinf_header(_render(message_type, [base]))
    try:
        combined = _pmtinf_header(_render(message_type, [base, varied]))
    except PaymentValidationError as exc:
        assert column in str(exc)
        return True, first, alone
    assert combined == first
    return False, first, alone


# payment_id is the per-transaction identifier; .04 (always) and .09+
# (without payment_information_id) also borrow row 1's as PmtInfId, a
# documented fallback rather than a column the rows must share.
_PROBED = sorted((set(_ALTERNATES) | set(_FLIPS)) - {"payment_id"})


@pytest.mark.parametrize("message_type", sorted(MESSAGE_REGISTRY))
@pytest.mark.parametrize("column", _PROBED)
def test_no_accepted_batch_drops_a_payment_information_value(
    message_type: str, column: str
) -> None:
    """Accepted iff row 2's value would not change the rendered PmtInf.

    The oracle is the template: row 2 rendered alone gives the PmtInf
    header it asks for. A batch that is accepted must render the same
    header row 1 alone renders (nothing of row 2's was dropped), and a
    refusal must be warranted (row 2 alone renders a different one).
    """
    refused, first, alone = _probe(message_type, column)
    if alone is None:
        return  # the alternate value is invalid for this schema
    if refused:
        assert alone != first, f"{column} refused but not PmtInf-level"
    else:
        assert alone == first, f"{column} differs in PmtInf but accepted"


def test_every_message_type_declares_its_columns() -> None:
    """The column table and the registry list the same message types."""
    assert set(PMTINF_COLUMNS) == set(MESSAGE_REGISTRY)


def test_bundled_nine_sample_names_every_conflict() -> None:
    """Rows from five debtors are refused, naming column and rows."""
    rows = [
        {"debtor_name": "Acme Corp", "requested_execution_date": "2023-03-12"},
        {"debtor_name": "Acme Corp", "requested_execution_date": "2023-03-12"},
        {"debtor_name": "Brown Ltd", "requested_execution_date": "2023-03-12"},
        {"debtor_name": "Acme Corp", "requested_execution_date": "2023-03-14"},
    ]
    with pytest.raises(PaymentValidationError) as caught:
        require_single_payment_information(rows, "pain.001.001.09")
    message = str(caught.value)
    assert "debtor_name (row 1 vs row 3)" in message
    assert "requested_execution_date (row 1 vs row 4)" in message
    assert caught.value.field == "records"


def test_blank_later_value_inherits_the_first() -> None:
    """A later row may leave a header column blank (header on row 1)."""
    rows = [
        {"debtor_name": "Acme Corp", "batch_booking": "true"},
        {"debtor_name": "", "batch_booking": None},
        {"debtor_name": " Acme Corp ", "batch_booking": "TRUE"},
    ]
    require_single_payment_information(rows, "pain.001.001.09")


def test_value_missing_on_row_one_is_a_conflict() -> None:
    """A value only a later row carries would be dropped: refused."""
    rows = [
        {"debtor_name": "Acme"},
        {"debtor_name": "Acme", "debtor_lei": "X"},
    ]
    with pytest.raises(PaymentValidationError, match="debtor_lei"):
        require_single_payment_information(rows, "pain.001.001.09")


def test_alias_chain_compares_the_effective_value() -> None:
    """``debtor_country_code`` wins over ``debtor_country`` (.05 to .08)."""
    rows = [
        {"debtor_country_code": "DE"},
        {"debtor_country_code": "DE", "debtor_country": "FR"},
    ]
    require_single_payment_information(rows, "pain.001.001.05")
    with pytest.raises(PaymentValidationError, match="debtor_country"):
        require_single_payment_information(
            [{"debtor_country": "DE"}, {"debtor_country": "FR"}],
            "pain.001.001.05",
        )


def test_unknown_message_type_is_left_to_the_registry() -> None:
    """The registry, not this check, reports an unsupported type."""
    require_single_payment_information(
        [{"debtor_name": "A"}, {"debtor_name": "B"}], "pain.999.001.01"
    )


def test_prepare_xml_data_refuses_mixed_batches() -> None:
    """The registry pipeline (every generation path) runs the check."""
    base = _first_row("pain.008.001.08")
    other = dict(base, creditor_name="Another Creditor")
    with pytest.raises(PaymentValidationError, match="creditor_name"):
        prepare_xml_data([base, other], "pain.008.001.08")


def _mixed_rows() -> list[dict[str, Any]]:
    """Two .03 rows from two debtors, otherwise valid."""
    path = TEMPLATES / "pain.001.001.03" / "template.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)][:2]
    rows[1]["debtor_name"] = "Brown Industries"
    return rows


def test_every_generation_entry_point_refuses(tmp_path: Path) -> None:
    """String, file, streamed and chunked generation all refuse."""
    from pain001.core.core import process_files, process_files_streaming
    from pain001.xml.generate_xml import stream_xml_to_file

    folder = TEMPLATES / "pain.001.001.03"
    template = str(folder / "template.xml")
    xsd = str(folder / "pain.001.001.03.xsd")
    rows = _mixed_rows()
    data_file = tmp_path / "mixed.csv"
    with data_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    calls = [
        lambda: generate_xml_string(rows, "pain.001.001.03", template, xsd),
        lambda: stream_xml_to_file(
            rows, "pain.001.001.03", template, str(tmp_path / "s.xml")
        ),
        lambda: process_files(
            "pain.001.001.03", template, xsd, rows, str(tmp_path / "p.xml")
        ),
        lambda: process_files_streaming(
            "pain.001.001.03",
            template,
            xsd,
            str(data_file),
            output_dir=str(tmp_path),
        ),
    ]
    for call in calls:
        with pytest.raises(PaymentValidationError, match="debtor_name"):
            call()
