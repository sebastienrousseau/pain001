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

"""The integration recipes in ``docs/integration-recipes.md``, end to end.

1. Map an ERP or treasury system's CSV export to pain001's input
   columns.
2. Run the batch pipeline: ``validate``, ``generate``, ``check``.
3. Read the bank's pain.002 reply with ``pain001 status`` (exit 3 on a
   rejection).
4. Reconcile the statement (camt.053) with the payments sent, by
   end-to-end identifier, through ``pain001[camt]``. Skipped, with a
   message, when the ``camt053`` package is not installed.

Everything runs offline on synthetic data. Run from the repository
root::

    python examples/30_integration_recipes.py
"""

import csv
import importlib.util
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

from pain001.constants import TEMPLATES_DIR
from pain001.corpus.rules.projection import rows_from_xml
from pain001.pain002 import build_pain002_report

MESSAGE = "pain.001.001.09"
TEMPLATE = TEMPLATES_DIR / MESSAGE / "template.csv"

#: A synthetic ERP payment-run export: one row per supplier invoice.
ERP_EXPORT = """\
Invoice,Supplier,SupplierIBAN,SupplierBIC,Amount,Currency
INV-1001,Global Tech,DE36210501700024690959,RQKKDEF0XXX,150.00,EUR
INV-1002,Green Energy,DE67370400440532013008,RQKKDEF0XXX,300.00,EUR
"""

#: ERP column -> pain001 column.
MAPPING = {
    "Invoice": "payment_id",
    "Supplier": "creditor_name",
    "SupplierIBAN": "creditor_account_IBAN",
    "SupplierBIC": "creditor_agent_BIC",
    "Amount": "payment_amount",
    "Currency": "payment_currency",
}


def pain001(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the pain001 command line in ``cwd`` and return its result.

    ``validate`` and ``generate`` read data files only inside the
    working directory, so a pipeline runs them from its own directory
    with relative paths.
    """
    return subprocess.run(  # nosec B603
        [sys.executable, "-m", "pain001", *args],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        cwd=cwd,
    )


def map_export(export: str, out: Path) -> list[dict[str, str]]:
    """Recipe 1: ERP columns onto pain001's, batch fields from defaults.

    The batch-level fields (debtor, initiating party, execution date)
    come from the bundled template's first row, standing in for your
    company's own configuration.
    """
    with TEMPLATE.open(encoding="utf-8", newline="") as handle:
        defaults = next(csv.DictReader(handle))
    rows = []
    for number, record in enumerate(csv.DictReader(export.splitlines()), 1):
        row = dict(defaults, id=str(number))
        row.update({MAPPING[k]: v for k, v in record.items()})
        row["currency"] = row["payment_currency"]
        row["remittance_information"] = f"Payment for {record['Invoice']}"
        rows.append(row)
    total = sum(float(r["payment_amount"]) for r in rows)
    for row in rows:
        row["nb_of_txs"] = str(len(rows))
        row["ctrl_sum"] = f"{total:.2f}"
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(defaults))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def batch(work: Path) -> Path:
    """Recipe 2: validate, generate, then check what was written."""
    (work / "out").mkdir()
    for args in (
        ("validate", "-t", MESSAGE, "-d", "payments.csv"),
        ("generate", "-t", MESSAGE, "-d", "payments.csv", "-o", "out"),
    ):
        result = pain001(work, *args)
        assert result.returncode == 0, result.stdout + result.stderr
    xml_file = work / "out" / f"{MESSAGE}.xml"
    checked = pain001(work, "check", str(xml_file))
    assert checked.returncode == 0, checked.stdout
    print(f"batch: validated, generated and checked {xml_file.name}")
    return xml_file


def reply(xml_file: Path, out: Path) -> str:
    """Recipe 3: a pain.002 rejecting one payment makes status exit 3."""
    ids = [r["end_to_end_id"] for r in rows_from_xml(xml_file.read_text())]
    rejected = ids[-1]
    report = out / "reply.pain002.xml"
    report.write_text(
        build_pain002_report(
            "STS-1",
            "MSG-1",
            "PART",
            [
                {
                    "original_payment_information_id": "Payment-Info-12345",
                    "payment_information_status": "PART",
                    "original_end_to_end_id": rejected,
                    "transaction_status": "RJCT",
                    "status_reason": "AC04",
                }
            ],
            original_message_name_id=MESSAGE,
        ),
        encoding="utf-8",
    )
    result = pain001(out, "status", str(report))
    assert result.returncode == 3, result.stdout
    print(f"status: exit {result.returncode}, rejected {rejected} (AC04)")
    return rejected


def bank_statement(sent: list[dict[str, str]], rejected: str) -> str:
    """A synthetic camt.053 booking every payment except the rejected one."""
    import camt053  # noqa: PLC0415
    from camt053.models import (  # noqa: PLC0415
        Account,
        Entry,
        ParsedDocument,
        Statement,
        TransactionDetails,
    )

    entries = [
        Entry(
            amount=r["payment_amount"],
            currency=r["payment_currency"],
            credit_debit_indicator="DBIT",
            status="BOOK",
            details=[TransactionDetails(end_to_end_id=r["end_to_end_id"])],
        )
        for r in sent
        if r["end_to_end_id"] != rejected
    ]
    account = Account(iban=sent[0]["debtor_account_IBAN"])
    statement = Statement(id="S-1", account=account, entries=entries)
    return camt053.serialize_document(
        ParsedDocument(
            message_type="camt.053.001.14",
            msg_id="STMT-1",
            statements=[statement],
        )
    )


def reconcile(xml_file: Path, rejected: str, out: Path) -> None:
    """Recipe 4: match statement entries to payments by end-to-end id."""
    if importlib.util.find_spec("camt053") is None:
        print("reconcile: skipped, install pain001[camt] to run it")
        return
    import camt053  # noqa: PLC0415

    sent = rows_from_xml(xml_file.read_text())
    stmt_file = out / "statement.camt053.xml"
    stmt_file.write_text(bank_statement(sent, rejected), encoding="utf-8")
    assert pain001(out, "status", str(stmt_file)).returncode == 0
    parsed = camt053.parse_document(stmt_file.read_text(encoding="utf-8"))
    booked = {d.end_to_end_id for e in parsed.all_entries() for d in e.details}
    open_items = sorted({r["end_to_end_id"] for r in sent} - booked)
    print(f"reconcile: {len(booked)} booked, open {open_items}")
    assert open_items == [rejected]


def main() -> None:
    """Run the four recipes in a temporary directory."""
    with tempfile.TemporaryDirectory() as workdir:
        work = Path(workdir)
        rows = map_export(ERP_EXPORT, work / "payments.csv")
        print(f"mapping: {len(rows)} ERP rows -> {work.name}/payments.csv")
        xml_file = batch(work)
        rejected = reply(xml_file, work)
        reconcile(xml_file, rejected, work)


if __name__ == "__main__":
    main()
