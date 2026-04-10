from pathlib import Path

from click.testing import CliRunner

from pain001.migrate import main
from pain001.migration.version_mapper import VersionMapper


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

