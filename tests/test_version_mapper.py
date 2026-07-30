# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from pain001.exceptions import DataSourceError
from pain001.migrate import main
from pain001.migration.version_mapper import (
    VersionMapper,
    cast_list_mapping,
    cast_mapping,
)

SAMPLE_ROW = {
    "id": "MSG001",
    "date": "2026-01-15T10:30:00",
    "nb_of_txs": "1",
    "initiator_name": "Test Corp",
    "payment_id": "PMT001",
    "payment_method": "TRF",
    "requested_execution_date": "2026-01-20",
    "debtor_name": "John Doe",
    "debtor_account_IBAN": "GB33BUKB20201555555555",
    "debtor_agent_BIC": "BUKBGB22",
    "charge_bearer": "SLEV",
    "payment_amount": "100.00",
    "payment_currency": "EUR",
    "creditor_agent_BIC": "ABCDUS33",
    "creditor_name": "Jane Smith",
    "creditor_account_IBAN": "FR1420041010050500013M02606",
    "reference_number": "REF12345",
}


def test_version_mapper_migrates_v03_to_v09() -> None:
    mapper = VersionMapper()
    rows = [
        {
            "id": "MSG001",
            "date": "2026-01-15T10:30:00",
            "nb_of_txs": "1",
            "initiator_name": "Test Corp",
            "payment_id": "PMT001",
            "payment_method": "TRF",
            "requested_execution_date": "2026-01-20",
            "debtor_name": "John Doe",
            "debtor_account_IBAN": "GB33BUKB20201555555555",
            "debtor_agent_BIC": "BUKBGB22",
            "charge_bearer": "SLEV",
            "payment_amount": "100.00",
            "payment_currency": "EUR",
            "creditor_agent_BIC": "ABCDUS33",
            "creditor_name": "Jane Smith",
            "creditor_account_IBAN": "FR1420041010050500013M02606",
            "reference_number": "REF12345",
        }
    ]

    migrated = mapper.migrate_rows(rows, "v03", "v09")

    assert migrated[0]["remittance_information"] == "REF12345"
    assert migrated[0]["creditor_agent_BIC"] == "ABCDUS33"


def test_version_mapper_validates_v05_to_v11() -> None:
    mapper = VersionMapper()
    rows = [
        {
            "id": "MSG001",
            "date": "2026-01-15T10:30:00",
            "nb_of_txs": "1",
            "initiator_name": "Test Corp",
            "payment_id": "PMT001",
            "payment_method": "TRF",
            "requested_execution_date": "2026-01-20",
            "debtor_name": "John Doe",
            "debtor_account_IBAN": "GB33BUKB20201555555555",
            "debtor_agent_BIC": "BUKBGB22",
            "charge_bearer": "SLEV",
            "payment_amount": "100.00",
            "payment_currency": "EUR",
            "creditor_agent_BICFI": "ABCDUS33",
            "creditor_name": "Jane Smith",
            "creditor_account_IBAN": "FR1420041010050500013M02606",
            "reference_number": "REF12345",
        }
    ]
    migrated = mapper.migrate_rows(rows, "v05", "v11")
    assert mapper.validate_migrated_rows(migrated, "v11") is True


def test_migration_cli_writes_default_output(tmp_path: Path) -> None:
    csv_file = tmp_path / "payments.csv"
    csv_file.write_text(
        (
            "id,date,nb_of_txs,initiator_name,payment_id,payment_method,"
            "requested_execution_date,debtor_name,debtor_account_IBAN,"
            "debtor_agent_BIC,charge_bearer,payment_amount,payment_currency,"
            "creditor_agent_BIC,creditor_name,creditor_account_IBAN,reference_number\n"
            "MSG001,2026-01-15T10:30:00,1,Test Corp,PMT001,TRF,2026-01-20,"
            "John Doe,GB33BUKB20201555555555,BUKBGB22,SLEV,100.00,EUR,"
            "ABCDUS33,Jane Smith,FR1420041010050500013M02606,REF12345\n"
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--from", "v03", "--to", "v09", "--source", str(csv_file)],
    )

    assert result.exit_code == 0
    migrated = tmp_path / "payments_v09.csv"
    assert migrated.exists()


def test_normalize_version_variants() -> None:
    assert VersionMapper.normalize_version("pain.001.001.03") == "v03"
    assert VersionMapper.normalize_version("V05") == "v05"
    assert VersionMapper.normalize_version("09") == "v09"


def test_load_mapping_uses_bundled_yaml() -> None:
    mapping = VersionMapper().load_mapping("v03", "v09")
    assert "field_map" in mapping


def test_load_mapping_generic_fallback() -> None:
    mapping = VersionMapper().load_mapping("v04", "v10")
    assert mapping["field_map"]["payment_id"] == "payment_id"


def test_load_mapping_generic_fallback_supports_v12() -> None:
    mapping = VersionMapper().load_mapping("v03", "v12")
    assert mapping["field_map"]["payment_id"] == "payment_id"


def test_load_mapping_unsupported_pair() -> None:
    with pytest.raises(DataSourceError, match="Unsupported migration path"):
        VersionMapper().load_mapping("v01", "v02")


def test_migrate_rows_requires_rows() -> None:
    with pytest.raises(DataSourceError, match="No payment rows"):
        VersionMapper().migrate_rows([], "v03", "v09")


def test_write_csv_and_default_output_path(tmp_path: Path) -> None:
    mapper = VersionMapper()
    migrated = mapper.migrate_rows([dict(SAMPLE_ROW)], "v03", "v09")
    output = mapper.write_csv(migrated, str(tmp_path / "out" / "result.csv"))
    assert Path(output).exists()
    assert (
        mapper.default_output_path("/data/payments.csv", "pain.001.001.09")
        == "/data/payments_v09.csv"
    )


def test_migrate_file_from_json_and_jsonl(tmp_path: Path) -> None:
    mapper = VersionMapper()
    json_path = tmp_path / "rows.json"
    json_path.write_text(json.dumps([SAMPLE_ROW]), encoding="utf-8")
    jsonl_path = tmp_path / "rows.jsonl"
    jsonl_path.write_text(json.dumps(SAMPLE_ROW) + "\n", encoding="utf-8")

    for source in (json_path, jsonl_path):
        migrated = mapper.migrate_file(str(source), "v03", "v09")
        assert migrated[0]["remittance_information"] == "REF12345"


def test_migrate_file_from_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "rows.db"
    conn = sqlite3.connect(db_path)
    columns = ", ".join(f'"{key}" TEXT' for key in SAMPLE_ROW)
    conn.execute(f"CREATE TABLE pain001 ({columns})")
    conn.execute(
        f"INSERT INTO pain001 VALUES ({', '.join('?' for _ in SAMPLE_ROW)})",
        list(SAMPLE_ROW.values()),
    )
    conn.commit()
    conn.close()

    migrated = VersionMapper().migrate_file(str(db_path), "v03", "v09")
    assert migrated[0]["payment_id"] == "PMT001"


def test_migrate_file_rejects_unsupported_extension(tmp_path: Path) -> None:
    source = tmp_path / "rows.txt"
    source.write_text("nope", encoding="utf-8")
    with pytest.raises(DataSourceError, match="Unsupported migration source"):
        VersionMapper().migrate_file(str(source), "v03", "v09")


def test_cast_helpers_reject_non_mappings() -> None:
    assert cast_mapping(["not", "a", "mapping"]) == {}
    assert cast_list_mapping("nope") == {}
    assert cast_list_mapping({"a": ["x"], "b": "skip"}) == {"a": ["x"]}
