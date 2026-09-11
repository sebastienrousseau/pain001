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

"""The records twin reads the pipeline's rows back and names the gap."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from pain001 import generate_xml_string
from pain001.constants import TEMPLATES_DIR, valid_xml_types
from pain001.corpus import get_file, list_files
from pain001.twins import (
    SUPPORTED_PREFIX,
    column_paths,
    from_iso_json,
    preparer_required,
    to_iso_json,
    to_records,
)
from pain001.twins import records as rec

EDITIONS = [v for v in valid_xml_types if v.startswith(SUPPORTED_PREFIX)]
MARKET = [
    f for f in list_files("market") if f.version.startswith(SUPPORTED_PREFIX)
]
CHAPS = ("gb.chaps.property-purchase", "pain.001.001.09")


def _regenerate(rows, version: str) -> str:
    template_dir = Path(TEMPLATES_DIR) / version
    return generate_xml_string(
        [dict(r) for r in rows],
        version,
        str(template_dir / "template.xml"),
        str(template_dir / f"{version}.xsd"),
    )


@pytest.mark.parametrize("version", EDITIONS)
def test_every_edition_maps_its_columns(version: str) -> None:
    """Each column lands somewhere or is an input-side gap; core ones land."""
    mapping = column_paths(version)
    columns, _ = rec.input_columns(version)
    assert list(mapping) == columns
    assert mapping["id"] == ("Document/CstmrCdtTrfInitn/GrpHdr/MsgId",)
    assert mapping["creditor_name"] == (
        "Document/CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/Nm",
    )
    assert mapping["payment_amount"] == (
        "Document/CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Amt/InstdAmt",
    )
    assert mapping["currency"] == (
        "Document/CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Amt/InstdAmt/@Ccy",
    )
    assert mapping["currency"] == mapping["payment_currency"], "alias"
    assert any(p.endswith("/NbOfTxs") for p in mapping["nb_of_txs"])
    assert mapping["service_level_code"] == (), "no template renders it"
    assert mapping["forwarding_agent_BIC"] == ()
    for column, paths in mapping.items():
        for path in paths:
            assert path.startswith("Document/CstmrCdtTrfInitn/"), (
                column,
                path,
            )


def test_the_v03_template_writes_accounts_as_other_ids() -> None:
    """A finding the twin makes measurable: .03 has no IBAN element."""
    mapping = column_paths("pain.001.001.03")
    assert mapping["debtor_account_IBAN"] == (
        "Document/CstmrCdtTrfInitn/PmtInf/DbtrAcct/Id/Othr/Id",
    )
    assert column_paths("pain.001.001.09")["debtor_account_IBAN"] == (
        "Document/CstmrCdtTrfInitn/PmtInf/DbtrAcct/Id/IBAN",
    )


def test_chaps_records_and_gap() -> None:
    """One row, the pipeline's columns, and every path it cannot carry."""
    twin = to_records(get_file(*CHAPS), CHAPS[1])
    assert len(twin.rows) == 1
    row = twin.rows[0]
    assert row["id"] == "ELMRD-20260912-0001"
    assert row["payment_amount"] == "425000.00"
    assert row["payment_currency"] == "GBP" and row["currency"] == "GBP"
    assert row["creditor_name"] == "Bramley and Co Solicitors Client Account"
    assert row["nb_of_txs"] == "1"
    assert "CstmrCdtTrfInitn/GrpHdr/InitgPty/Id/OrgId/LEI" in twin.gap
    assert "CstmrCdtTrfInitn/PmtInf/BtchBookg" in twin.gap
    assert "CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Purp/Cd" in twin.gap
    assert (
        "CstmrCdtTrfInitn/PmtInf/PmtInfId (collapsed into payment_id)"
        in twin.gap
    )
    assert twin.missing_required == []
    assert "CstmrCdtTrfInitn/GrpHdr/MsgId" not in twin.gap


@pytest.mark.parametrize("entry", MARKET, ids=lambda f: f.path.name)
def test_records_regenerate_or_say_why_not(entry) -> None:
    """A file with nothing missing regenerates with the same mapped values.

    Otherwise ``missing_required`` names what the preparer demanded and the
    document did not carry, and that list is not empty.
    """
    xml = entry.read()
    twin = to_records(xml, entry.version)
    assert twin.rows, "one row per transaction"
    if twin.missing_required:
        assert all(
            c in preparer_required(entry.version)
            for c in twin.missing_required
        )
        return
    regenerated = _regenerate(twin.rows, entry.version)
    before = to_iso_json(xml, entry.version)
    after = to_iso_json(regenerated, entry.version)
    for column, paths in column_paths(entry.version).items():
        if column in ("nb_of_txs", "ctrl_sum") or not paths:
            continue
        rel = paths[0].split("/", 1)[1]
        for index in range(len(twin.rows)):
            value = rec._read(before, rel, index)
            if value is not None:
                assert rec._read(after, rel, index) == value, (column, rel)


def test_at_least_the_iban_editions_regenerate() -> None:
    """The measured state today: every .09 file with IBANs on both sides."""
    regenerable = [
        f.path.name
        for f in MARKET
        if not to_records(f.read(), f.version).missing_required
    ]
    assert len(regenerable) >= 15
    assert "gb.chaps.property-purchase.pain.001.001.09.xml" in regenerable
    assert "gb.fps.single.pain.001.001.09.xml" not in regenerable, (
        "sort code and account, not an IBAN"
    )
    v03 = [f for f in MARKET if f.version == "pain.001.001.03"]
    assert all(
        to_records(f.read(), f.version).missing_required for f in v03
    ), "the .03 template needs address and reference columns and Othr ids"


def test_preparer_requirements_are_learned_from_the_preparer() -> None:
    """The gate is the preparer's list, aliases understood."""
    required = preparer_required("pain.001.001.09")
    assert "id" in required and "creditor_account_IBAN" in required
    assert "currency" in required and "payment_currency" not in required
    assert "(or" not in " ".join(required)
    assert len(preparer_required("pain.001.001.03")) > len(required)
    assert "initiator_street_name" in preparer_required("pain.001.001.03")


def test_second_payment_block_is_a_gap() -> None:
    """The pipeline renders one PmtInf; a second one is reported."""
    twin = to_iso_json(get_file(*CHAPS), CHAPS[1])
    doubled = copy.deepcopy(twin)
    block = doubled["Document"]["CstmrCdtTrfInitn"]["PmtInf"][0]
    second = copy.deepcopy(block)
    second["PmtInfId"] = "SECOND"
    doubled["Document"]["CstmrCdtTrfInitn"]["PmtInf"].append(second)
    doubled["Document"]["CstmrCdtTrfInitn"]["GrpHdr"]["NbOfTxs"] = "2"
    doubled["Document"]["CstmrCdtTrfInitn"]["GrpHdr"]["CtrlSum"] = "850000.00"
    result = to_records(from_iso_json(doubled, CHAPS[1]), CHAPS[1])
    assert result.gap[-1] == "CstmrCdtTrfInitn/PmtInf (occurrences 2 to 2)"
    assert len(result.rows) == 1


def test_read_walks_arrays_amounts_and_absences() -> None:
    """The reader follows the always-array twin and returns None when absent."""
    twin = to_iso_json(get_file(*CHAPS), CHAPS[1])
    base = "CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf"
    assert rec._read(twin, f"{base}/Amt/InstdAmt", 0) == "425000.00"
    assert rec._read(twin, f"{base}/Amt/InstdAmt/@Ccy", 0) == "GBP"
    assert rec._read(twin, f"{base}/Nope", 0) is None
    assert rec._read(twin, f"{base}/Amt/InstdAmt", 5) is None, (
        "no such transaction"
    )
    assert rec._read(
        twin, "CstmrCdtTrfInitn/GrpHdr/InitgPty/Nm", 0
    ).startswith("Elm")
    assert (
        rec._read(twin, "CstmrCdtTrfInitn/GrpHdr/InitgPty/PstlAdr/AdrLine", 0)
        == "14 Elm Road"
    )


def test_read_attribute_on_a_text_leaf_is_absent() -> None:
    """Asking for an attribute where the twin holds a plain string gives None."""
    twin = to_iso_json(get_file(*CHAPS), CHAPS[1])
    assert rec._read(twin, "CstmrCdtTrfInitn/GrpHdr/MsgId/@Ccy", 0) is None


def test_equal_values_on_a_shared_column_do_not_collapse() -> None:
    """When PmtInfId equals EndToEndId nothing is reported as collapsed."""
    twin = to_iso_json(get_file(*CHAPS), CHAPS[1])
    block = twin["Document"]["CstmrCdtTrfInitn"]["PmtInf"][0]
    block["PmtInfId"] = block["CdtTrfTxInf"][0]["PmtId"]["EndToEndId"]
    result = to_records(from_iso_json(twin, CHAPS[1]), CHAPS[1])
    assert not any("collapsed" in g for g in result.gap)
    assert result.rows[0]["payment_id"] == block["PmtInfId"]
