# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Parse — and generate — the messages your bank sends back.

After you submit a pain.001, banks reply with a pain.002 payment status
report and an end-of-day camt.053 statement. Pain001 reads both into plain
Python structures so you can reconcile programmatically — and it can *build*
a pain.002 too (e.g. to simulate a bank in tests), which round-trips back
through the parser.

Run from the repository root::

    python examples/07_parse_bank_responses.py
"""

import tempfile
from pathlib import Path

from pain001 import (
    build_camt053_statement,
    build_pain002_report,
    parse_camt053_statement,
    parse_pain002_report,
)

FIXTURES = Path("pain001/test_fixtures")


def main() -> None:
    """Parse sample bank responses and round-trip a generated pain.002."""
    status = parse_pain002_report(str(FIXTURES / "pain002_sample.xml"))
    assert isinstance(status, dict) and status
    print("pain.002 status report parsed:")
    for key in list(status)[:5]:
        print(f"  {key}: {status[key]!r}")

    statement = parse_camt053_statement(str(FIXTURES / "camt053_sample.xml"))
    assert isinstance(statement, dict) and statement
    print("camt.053 statement parsed:")
    for key in list(statement)[:5]:
        print(f"  {key}: {statement[key]!r}")

    # Generate a pain.002 (simulate a bank) and prove it round-trips.
    xml = build_pain002_report(
        message_id="STS-EXAMPLE-1",
        original_message_id="MSG-12345",
        group_status="ACCP",
        payment_statuses=[
            {
                "original_payment_information_id": "Payment-Info-12345",
                "payment_information_status": "ACCP",
                "original_end_to_end_id": "PaymentID6789",
                "transaction_status": "ACSC",
            }
        ],
    )
    with tempfile.TemporaryDirectory() as workdir:
        path = Path(workdir) / "generated_pain002.xml"
        path.write_text(xml, encoding="utf-8")
        reparsed = parse_pain002_report(str(path))
    assert reparsed["message_id"] == "STS-EXAMPLE-1"
    assert reparsed["payment_statuses"][0]["transaction_status"] == "ACSC"
    print(
        "pain.002 generated and round-tripped: "
        f"{reparsed['group_status']} / "
        f"{reparsed['payment_statuses'][0]['transaction_status']}"
    )

    # Generate a camt.053 statement and prove it round-trips too.
    stmt_xml = build_camt053_statement(
        statement_id="STMT-EXAMPLE-1",
        iban="DE89370400440532013000",
        currency="EUR",
        entries=[
            {
                "credit_debit_indicator": "CRDT",
                "status": "BOOK",
                "amount": "150.00",
                "booking_date": "2026-04-10",
                "entry_reference": "ENTRY-001",
                "remittance_information": "Invoice 42",
            }
        ],
    )
    with tempfile.TemporaryDirectory() as workdir:
        spath = Path(workdir) / "generated_camt053.xml"
        spath.write_text(stmt_xml, encoding="utf-8")
        restmt = parse_camt053_statement(str(spath))
    assert restmt["statement_id"] == "STMT-EXAMPLE-1"
    assert restmt["entries"][0]["amount"] == "150.00"
    print(
        "camt.053 generated and round-tripped: "
        f"{restmt['statement_id']} / {restmt['entries'][0]['amount']} "
        f"{restmt['currency']}"
    )

    print("Bank-response parse + generate example completed.")


if __name__ == "__main__":
    main()
