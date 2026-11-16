# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Contract tests for :class:`VersionMapper` migration semantics.

They pin which version pairs migrate, the generic legacy-to-modern
field mapping, how ``field_map``, ``fallbacks`` and ``defaults``
combine, and how group header fields are filled across rows.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from pain001.exceptions import DataSourceError
from pain001.migration.version_mapper import VersionMapper

GENERIC_FIELDS = [
    "id",
    "date",
    "nb_of_txs",
    "initiator_name",
    "payment_id",
    "payment_method",
    "requested_execution_date",
    "debtor_name",
    "debtor_account_IBAN",
    "debtor_agent_BIC",
    "charge_bearer",
    "payment_amount",
    "payment_currency",
    "creditor_agent_BIC",
    "creditor_name",
    "creditor_account_IBAN",
]

EXPECTED_GENERIC = {
    "field_map": {name: name for name in GENERIC_FIELDS},
    "defaults": {"payment_method": "TRF", "charge_bearer": "SLEV"},
    "fallbacks": {
        "creditor_agent_BIC": ["creditor_agent_BIC", "creditor_agent_BICFI"],
        "remittance_information": [
            "remittance_information",
            "reference_number",
            "payment_id",
        ],
    },
}


def _mapper_with(tmp_path: Path, yaml_text: str) -> VersionMapper:
    """Return a mapper whose v03 to v09 mapping is ``yaml_text``."""
    mapper = VersionMapper()
    mapper.mappings_dir = tmp_path
    (tmp_path / "v03_to_v09.yaml").write_text(yaml_text, encoding="utf-8")
    return mapper


def test_generic_mapping_is_identity_plus_defaults_and_fallbacks() -> None:
    """The generic mapping copies every modern field by name."""
    assert (
        VersionMapper._generic_legacy_to_modern_mapping() == EXPECTED_GENERIC
    )


def test_generic_pair_is_served_for_paths_without_yaml() -> None:
    """Pairs with no YAML file get exactly the generic mapping."""
    mapper = VersionMapper()
    assert mapper.load_mapping("v09", "v12") == EXPECTED_GENERIC
    assert mapper.load_mapping("pain.001.001.04", "13") == EXPECTED_GENERIC


def test_bundled_yaml_mappings_are_found() -> None:
    """The mapper reads its bundled ``mappings`` directory."""
    mapper = VersionMapper()
    assert mapper.mappings_dir.name == "mappings"
    loaded = mapper.load_mapping("v03", "v09")
    assert loaded["source_version"] == "v03"
    assert loaded["target_version"] == "v09"


@pytest.mark.parametrize(
    ("source", "target", "supported"),
    [
        ("v03", "v09", True),
        ("v03", "v04", True),
        ("v09", "v12", True),
        ("v13", "v09", True),
        ("v09", "v03", False),
        ("v12", "v08", False),
        ("v02", "v09", False),
        ("v09", "v14", False),
        ("v02", "v14", False),
    ],
)
def test_generic_pair_support(
    source: str, target: str, supported: bool
) -> None:
    """Legacy or modern to modern, and legacy to legacy, are supported."""
    assert (
        VersionMapper._is_supported_generic_pair(source, target) is supported
    )


def test_unknown_source_version_is_refused() -> None:
    """An unknown source raises, naming the requested path."""
    with pytest.raises(DataSourceError, match="v02 -> v09"):
        VersionMapper().load_mapping("v02", "v09")


def test_migrate_rows_rejects_empty_input() -> None:
    """Migrating nothing is an error with a clear message."""
    with pytest.raises(
        DataSourceError, match="^No payment rows supplied for migration$"
    ):
        VersionMapper().migrate_rows([], "v03", "v09")


def test_fallbacks_only_fill_blank_fields(tmp_path: Path) -> None:
    """A field set by ``field_map`` keeps its value; later fallbacks run."""
    mapper = _mapper_with(
        tmp_path,
        "field_map:\n  creditor_name: name\n"
        "fallbacks:\n"
        "  creditor_name: [alias]\n"
        "  remittance_information: [ref]\n",
    )
    rows = [{"name": "Primary", "alias": "Other", "ref": "R-1"}]
    migrated = mapper.migrate_rows(rows, "v03", "v09")
    assert migrated[0]["creditor_name"] == "Primary"
    assert migrated[0]["remittance_information"] == "R-1"


def test_fallback_skips_blank_candidates(tmp_path: Path) -> None:
    """Empty and missing candidates are skipped in favour of the next."""
    mapper = _mapper_with(
        tmp_path,
        "fallbacks:\n  creditor_name: [missing, blank, good, later]\n",
    )
    rows = [{"blank": "", "good": "Found", "later": "Late"}]
    migrated = mapper.migrate_rows(rows, "v03", "v09")
    assert migrated[0]["creditor_name"] == "Found"


def test_defaults_do_not_override_supplied_values() -> None:
    """``defaults`` fill only blank fields."""
    rows = [{"payment_method": "CHK", "charge_bearer": ""}]
    migrated = VersionMapper().migrate_rows(rows, "v09", "v12")
    assert migrated[0]["payment_method"] == "CHK"
    assert migrated[0]["charge_bearer"] == "SLEV"


def test_group_fields_fill_from_first_row_only_when_blank() -> None:
    """Header fields copy from row one into blanks, never over values."""
    rows: list[dict[str, Any]] = [
        {"id": "MSG-1", "debtor_name": "Alpha", "payment_id": "P1"},
        {"id": "", "debtor_name": "Beta", "payment_id": "P2"},
    ]
    migrated = VersionMapper().migrate_rows(rows, "v09", "v12")
    assert migrated[1]["id"] == "MSG-1"
    assert migrated[1]["debtor_name"] == "Beta"
    assert migrated[1]["initiator_name"] == ""


def test_sparse_mapping_gets_header_defaults(tmp_path: Path) -> None:
    """Fields a mapping never sets get the documented group defaults."""
    mapper = _mapper_with(tmp_path, "field_map:\n  payment_id: pid\n")
    migrated = mapper.migrate_rows([{"pid": "P-9"}, {}], "v03", "v09")
    first, second = migrated
    assert first["nb_of_txs"] == "2"
    assert second["nb_of_txs"] == "2"
    for row in migrated:
        assert row["payment_currency"] == "EUR"
        assert row["initiator_name"] == ""
    assert first["remittance_information"] == "P-9"
    assert second["remittance_information"] == ""
    assert second["payment_id"] == ""


def test_remittance_is_empty_without_any_payment_id(tmp_path: Path) -> None:
    """With no payment id at all, remittance is an empty string."""
    mapper = _mapper_with(tmp_path, "field_map:\n  id: id\n")
    migrated = mapper.migrate_rows([{"id": "M-1"}], "v03", "v09")
    assert migrated[0]["remittance_information"] == ""
    assert "payment_id" not in migrated[0]


def test_blank_remittance_falls_back_to_payment_id(tmp_path: Path) -> None:
    """An empty remittance string is replaced by the payment id."""
    mapper = _mapper_with(
        tmp_path,
        "field_map:\n  payment_id: pid\n  remittance_information: rmt\n",
    )
    migrated = mapper.migrate_rows([{"pid": "P-1", "rmt": ""}], "v03", "v09")
    assert migrated[0]["remittance_information"] == "P-1"


def test_write_csv_creates_missing_parent_directories(tmp_path: Path) -> None:
    """The output's parent chain is created, however deep."""
    target = tmp_path / "a" / "b" / "c" / "out.csv"
    rows = VersionMapper().migrate_rows([{"id": "M"}], "v09", "v12")
    written = VersionMapper().write_csv(rows, str(target))
    assert written == str(target)
    with open(target, encoding="utf-8", newline="") as handle:
        read_back = list(csv.DictReader(handle))
    assert read_back[0]["id"] == "M"


def test_group_fields_default_the_method_and_bearer() -> None:
    """Without a value in any row, TRF and SLEV apply, as EUR does."""
    rows: list[dict[str, Any]] = [
        {"id": "MSG1", "payment_id": "P1"},
        {"id": "", "payment_id": "P2", "charge_bearer": "DEBT"},
    ]
    VersionMapper._normalize_group_fields(rows)
    assert [
        (r["payment_method"], r["charge_bearer"], r["payment_currency"])
        for r in rows
    ] == [("TRF", "SLEV", "EUR"), ("TRF", "DEBT", "EUR")]


def test_a_mapping_default_fills_blank_values_and_beats_the_group_default(
    tmp_path: Path,
) -> None:
    """A mapping's ``defaults`` fill empty and missing fields first."""
    mapper = _mapper_with(
        tmp_path,
        "field_map:\n"
        "  charge_bearer: charge_bearer\n"
        "  payment_method: payment_method\n"
        "defaults:\n"
        "  charge_bearer: DEBT\n"
        "  payment_method: CHK\n",
    )
    migrated = mapper.migrate_rows([{"charge_bearer": ""}], "v03", "v09")
    assert (migrated[0]["charge_bearer"], migrated[0]["payment_method"]) == (
        "DEBT",
        "CHK",
    )
