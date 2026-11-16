# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""How the records twin learns where each column lands.

``column_paths`` renders the edition's template with a sentinel value
per column and reads the sentinels back. It is cached, so these tests
also run the derivation afresh and compare it with the cached mapping
the other tests pin, and they check the sentinels themselves: each one
is a value its column's template accepts, and no two columns share one.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

import pytest

from pain001.constants import valid_xml_types
from pain001.data.loader import load_payment_data
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.twins import SUPPORTED_PREFIX, column_paths
from pain001.twins import records as rec

EDITIONS = [v for v in valid_xml_types if v.startswith(SUPPORTED_PREFIX)]


def _iban_ok(iban: str) -> bool:
    """ISO 13616 mod-97 check."""
    moved = iban[4:] + iban[:4]
    digits = "".join(str(int(ch, 36)) for ch in moved)
    return int(digits) % 97 == 1


@pytest.mark.parametrize("version", EDITIONS)
def test_a_fresh_derivation_matches_the_cached_mapping(version: str) -> None:
    """Running the derivation again gives the mapping already served."""
    assert column_paths.__wrapped__(version) == column_paths(version)


@pytest.mark.parametrize("version", EDITIONS)
def test_first_row_sentinels_are_unique(version: str) -> None:
    """No two columns of an edition share a first-row sentinel."""
    columns, _ = rec.input_columns(version)
    values = [rec._sentinel(c, i, 0) for i, c in enumerate(columns)]
    shared = {"nb_of_txs", "batch_booking"}
    own = [v for v, c in zip(values, columns, strict=True) if c not in shared]
    assert len(own) == len(set(own))


def test_sentinels_are_values_the_templates_accept() -> None:
    """Dates, date-times, amounts, IBANs and codes are well formed."""
    for index in range(200):
        for row in range(rec._ROWS):
            dt.date.fromisoformat(rec._sentinel("x_date", index, row))
            dt.datetime.fromisoformat(rec._sentinel("x_datetime", index, row))
            dt.datetime.fromisoformat(rec._sentinel("date", index, row))
            amount = rec._sentinel("payment_amount", index, row)
            assert re.fullmatch(r"[1-9][0-9]{2}\.[0-9]{2,3}", amount)
            assert rec._sentinel("ctrl_sum", index, row) == amount
            iban = rec._sentinel("creditor_account_IBAN", index, row)
            assert re.fullmatch(r"DE[0-9]{20}", iban) and _iban_ok(iban)
            assert re.fullmatch(
                r"S[0-9]{2,3}R[0-9]", rec._sentinel("x", index, row)
            )
    assert rec._sentinel("nb_of_txs", 7, 0) == str(rec._ROWS) == "2"
    assert rec._sentinel("batch_booking", 7, 1) == "true"
    assert rec._sentinel("currency", 7, 1) == "C07"


def test_sentinels_differ_by_row_and_by_index() -> None:
    """Each row and each column index has its own value."""
    for column in ("payment_amount", "date", "x_datetime", "x_date", "x"):
        assert rec._sentinel(column, 3, 0) != rec._sentinel(column, 3, 1)
        assert rec._sentinel(column, 3, 0) != rec._sentinel(column, 4, 0)
    assert rec._sentinel("payment_amount", 3, 0) == "100.13"
    assert rec._sentinel("payment_amount", 3, 1) == "101.13"
    assert rec._sentinel("date", 3, 1) == "2001-01-02T03:03:00"
    assert rec._sentinel("x_datetime", 13, 0) == "2003-02-01T13:00:00"
    assert rec._sentinel("x_date", 13, 1) == "2002-02-02"
    assert rec._sentinel("debtor_account_IBAN", 1, 1) == (
        rec._sentinel_iban(1, 1)
    )
    assert rec._sentinel("x", 5, 1) == "S05R1"


def test_sentinel_ibans_are_valid_and_distinct() -> None:
    """Every index and row gives its own IBAN that passes mod-97."""
    seen = {rec._sentinel_iban(i, r) for i in range(150) for r in range(2)}
    assert len(seen) == 300
    assert all(_iban_ok(iban) for iban in seen)
    assert rec._sentinel_iban(12, 1) == "DE82000012000001000000"
    assert rec._sentinel_iban(0, 0) == "DE36000000000000000000"


def test_texts_index_values_by_path() -> None:
    """Text and plain attributes by value; blanks and xsi hints skipped."""
    xml = (
        '<Document xmlns="urn:x" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="urn:x a.xsd"><A Ccy="EUR"> 1.00 </A>'
        "<B><C>1.00</C><D>  </D><E/></B></Document>"
    )
    assert rec._texts(xml) == {
        "EUR": ["Document/A/@Ccy"],
        "1.00": ["Document/A", "Document/B/C"],
    }
    assert rec._texts("<R><A>v</A></R>") == {"v": ["R/A"]}


def test_merge_texts_appends_paths() -> None:
    """A further rendering adds paths to known values and new values."""
    texts = {"a": ["x"]}
    rec._merge_texts(texts, {"a": ["y"], "b": ["z"]})
    assert texts == {"a": ["x", "y"], "b": ["z"]}


def test_preferred_chain_climbs_to_the_top() -> None:
    """A proprietary scheme drops its scheme and the IBAN above it."""
    assert rec._preferred_chain("debtor_account_scheme_proprietary") == {
        "debtor_account_scheme",
        "debtor_account_IBAN",
    }
    assert rec._preferred_chain("creditor_account_number") == {
        "creditor_account_IBAN"
    }
    assert rec._preferred_chain("debtor_name") == set()


def test_is_sentinel_lets_amounts_differ_by_row() -> None:
    """An amount is recognised by its index; other columns need row 0."""
    assert rec._is_sentinel("101.13", "payment_amount", 3)
    assert rec._is_sentinel("100.13", "ctrl_sum", 3)
    assert not rec._is_sentinel("101.13", "ctrl_sum", 3)
    assert not rec._is_sentinel("100.14", "payment_amount", 3)
    assert rec._is_sentinel("S03R0", "x", 3)
    assert not rec._is_sentinel("S03R1", "x", 3)


def test_map_sentinels_and_totals() -> None:
    """Sentinels map to their paths; totals map to every NbOfTxs/CtrlSum."""
    columns = ["x", "nb_of_txs", "ctrl_sum"]
    mapping: dict[str, set[str]] = {c: set() for c in columns}
    texts = {
        "S00R0": ["D/A", "D/B"],
        "2": ["D/GrpHdr/NbOfTxs", "D/PmtInf/NbOfTxs"],
        "9.99": ["D/GrpHdr/CtrlSum"],
        "S00R1": ["D/C"],
    }
    rec._map_sentinels(texts, columns, mapping)
    assert mapping == {
        "x": {"D/A", "D/B"},
        "nb_of_txs": set(),
        "ctrl_sum": set(),
    }
    rec._map_totals(texts, mapping)
    assert mapping["nb_of_txs"] == {"D/GrpHdr/NbOfTxs", "D/PmtInf/NbOfTxs"}
    assert mapping["ctrl_sum"] == {"D/GrpHdr/CtrlSum"}
    partial: dict[str, set[str]] = {"x": set()}
    rec._map_totals(texts, partial)
    assert partial == {"x": set()}, "a column the edition lacks stays out"


def test_fold_aliases_copies_the_canonical_paths() -> None:
    """An alias with no paths of its own takes its canonical column's."""
    mapping = {"currency": {"D/Amt/@Ccy"}, "payment_currency": set()}
    rec._fold_aliases(["currency", "payment_currency", "amount"], mapping)
    assert mapping["payment_currency"] == {"D/Amt/@Ccy"}
    assert mapping["payment_currency"] is not mapping["currency"]
    assert "amount" not in mapping, "its canonical column is not mapped"
    own = {"currency": {"D/A"}, "payment_currency": {"D/B"}}
    rec._fold_aliases(["payment_currency"], own)
    assert own["payment_currency"] == {"D/B"}


def _sentinel_rows(version: str) -> list[dict[str, str]]:
    """The sentinel rows the derivation renders for an edition."""
    columns, _ = rec.input_columns(version)
    return [
        {c: rec._sentinel(c, i, r) for i, c in enumerate(columns)}
        for r in range(rec._ROWS)
    ]


def test_batch_booking_is_found_by_flipping_it() -> None:
    """Only the element whose text flips is BtchBookg, not every "true"."""
    version = "pain.001.001.09"
    rows = [dict(r, debtor_name="true") for r in _sentinel_rows(version)]
    assert rec._batch_booking_paths(version, rows) == {
        "Document/CstmrCdtTrfInitn/PmtInf/BtchBookg"
    }


def test_render_computes_the_totals_itself() -> None:
    """NbOfTxs and CtrlSum come from the rows, not from their columns."""
    version = "pain.001.001.09"
    rows = [
        dict(r, nb_of_txs="7", ctrl_sum="1.00")
        for r in _sentinel_rows(version)
    ]
    texts = rec._texts(rec._render(version, rows))
    total = sum(float(r["payment_amount"]) for r in rows)
    block = "Document/CstmrCdtTrfInitn"
    assert texts["2"] == [f"{block}/GrpHdr/NbOfTxs", f"{block}/PmtInf/NbOfTxs"]
    assert texts[f"{total:.2f}"] == [
        f"{block}/GrpHdr/CtrlSum",
        f"{block}/PmtInf/CtrlSum",
    ]
    assert "7" not in texts and "1.00" not in texts


def test_record_row_reads_every_path_and_notes_collapses() -> None:
    """An absent first path does not hide the second; differing ones collapse."""
    twin = {"Document": {"A": {"C": "x", "D": "y", "E": "x"}}}
    paths = {
        "one": ("Document/A/B", "Document/A/C"),
        "two": ("Document/A/C", "Document/A/D"),
        "same": ("Document/A/C", "Document/A/E"),
    }
    collapsed: set[str] = set()
    row = rec._record_row(twin, list(paths), paths, 0, collapsed)
    assert row == {"one": "x", "two": "x", "same": "x"}
    assert collapsed == {"A/D (collapsed into two)"}


def test_read_past_the_last_transaction_is_absent() -> None:
    """The index one past the end of the transactions reads nothing."""
    twin = {"Document": {"P": {"CdtTrfTxInf": [{"N": "a"}, {"N": "b"}]}}}
    assert rec._read(twin, "P/CdtTrfTxInf/N", 1) == "b"
    assert rec._read(twin, "P/CdtTrfTxInf/N", 2) is None


@pytest.mark.parametrize(
    "version", DEFAULT_TEMPLATE_REGISTRY.list_supported_versions()
)
def test_rendered_totals_are_the_rows_count_and_sum(version: str) -> None:
    """NbOfTxs is the row count and CtrlSum the sum to two places."""
    bundle = DEFAULT_TEMPLATE_REGISTRY.get_template(version)
    rows = [
        {key: str(value) for key, value in row.items()}
        for row in load_payment_data(str(bundle.example_data_path))
    ]
    xml = rec._render(version, rows)
    total = sum(Decimal(row["payment_amount"]) for row in rows)
    counts = set(re.findall(r"<NbOfTxs>([^<]*)</NbOfTxs>", xml))
    sums = set(re.findall(r"<CtrlSum>([^<]*)</CtrlSum>", xml))
    has_sum = "CtrlSum" in bundle.template_path.read_text(encoding="utf-8")
    assert counts == {str(len(rows))}
    assert sums == ({f"{total:.2f}"} if has_sum else set())
