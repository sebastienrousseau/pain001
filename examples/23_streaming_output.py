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

"""Render pain.001 XML in chunks and see what row normalisation does.

``stream_xml_chunks`` yields the document piece by piece and
``stream_xml_to_file`` writes those pieces straight to disk, so a large
batch never sits in memory as one string. Neither validates against
the XSD (that needs the whole document), so this example checks the
streamed output against ``generate_xml_string`` byte for byte and
validates the written file explicitly.

``normalize_payment_records`` and ``canonicalize_payment_record`` show
the row shape every generator renders from: canonical keys, two-decimal
amounts, XSD booleans and dates, and batch totals computed from rows.

Run from the repository root::

    python examples/23_streaming_output.py
"""

import tempfile
from pathlib import Path

from pain001 import (
    canonicalize_payment_record,
    normalize_payment_records,
    stream_xml_chunks,
    stream_xml_to_file,
)
from pain001.constants import TEMPLATES_DIR
from pain001.csv.load_csv_data import load_csv_data
from pain001.xml.generate_xml import generate_xml_string
from pain001.xml.validate_via_xsd import validate_via_xsd

MESSAGE_TYPE = "pain.001.001.03"
DATA_FILE = Path(__file__).resolve().parent / "data" / "payments.csv"
TEMPLATE_DIR = TEMPLATES_DIR / MESSAGE_TYPE
TEMPLATE = str(TEMPLATE_DIR / "template.xml")
XSD = str(TEMPLATE_DIR / f"{MESSAGE_TYPE}.xsd")


def show_chunk_parity(rows: list[dict]) -> str:
    """Join streamed chunks and compare them with the in-memory render."""
    chunks = list(stream_xml_chunks(rows, MESSAGE_TYPE, TEMPLATE))
    streamed = "".join(chunks)
    assert len(chunks) > 1
    assert streamed == generate_xml_string(rows, MESSAGE_TYPE, TEMPLATE, XSD)
    print(f"{len(chunks)} chunks join to the generate_xml_string output")
    return streamed


def show_file_streaming(rows: list[dict], expected: str) -> None:
    """Stream the document to a file and validate it against the XSD."""
    with tempfile.TemporaryDirectory() as output_dir:
        target = Path(output_dir) / f"{MESSAGE_TYPE}.xml"
        written = stream_xml_to_file(rows, MESSAGE_TYPE, TEMPLATE, str(target))
        assert Path(written) == target.resolve()
        assert Path(written).read_text(encoding="utf-8") == expected
        assert validate_via_xsd(written, XSD)
        size = Path(written).stat().st_size
        print(f"Streamed {target.name} ({size} bytes), XSD-valid")


def show_csv_normalisation(rows: list[dict]) -> None:
    """Show amounts, totals and dates after normalising the CSV rows."""
    normalized = normalize_payment_records(rows)
    first = normalized[0]
    assert rows[0]["payment_amount"] == "150"
    assert first["payment_amount"] == "150.00"
    # Header totals come from the rows, not from the CSV columns.
    assert rows[0]["nb_of_txs"] == "2" and rows[0]["ctrl_sum"] == "15000"
    assert first["nb_of_txs"] == len(rows) == 4
    assert first["ctrl_sum"] == 900.0
    assert first["requested_execution_date"] == "2023-03-12"
    assert rows[0]["payment_amount"] == "150", "input must not be mutated"
    print(
        f"CSV rows: amount 150 -> {first['payment_amount']}, "
        f"nb_of_txs={first['nb_of_txs']}, ctrl_sum={first['ctrl_sum']}"
    )


TYPED_RECORD = {
    "amount": 12.5,
    "currency": "EUR",
    "debtor_account_iban": "DE07512108001245126162",
    "batch_booking": True,
    "date": "2026-01-02",
    "requested_execution_date": "2026-01-03T10:00:00",
}


def show_key_canonicalisation() -> None:
    """Map alias keys to canonical names without touching the values."""
    canonical = canonicalize_payment_record(TYPED_RECORD)
    # Keys are mapped, values keep their types for JSON-Schema checks.
    assert canonical["payment_amount"] == 12.5
    assert canonical["payment_currency"] == "EUR"
    iban = TYPED_RECORD["debtor_account_iban"]
    assert canonical["debtor_account_IBAN"] == iban
    assert canonical["batch_booking"] is True
    assert "payment_amount" not in TYPED_RECORD, "input must not change"
    print("Canonical keys: amount -> payment_amount, *_iban -> *_IBAN")


def show_typed_record_normalisation() -> None:
    """Normalise a typed record: amount, boolean and date lexical forms."""
    (normalized,) = normalize_payment_records([TYPED_RECORD])
    assert normalized["payment_amount"] == "12.50"
    assert normalized["batch_booking"] == "true"
    assert normalized["date"] == "2026-01-02T00:00:00"
    assert normalized["requested_execution_date"] == "2026-01-03"
    assert (normalized["nb_of_txs"], normalized["ctrl_sum"]) == (1, 12.5)
    print("Typed record: 12.5 -> '12.50', True -> 'true', dates per XSD")


def main() -> None:
    """Stream XML from the sample CSV and inspect the normalised rows."""
    rows = load_csv_data(str(DATA_FILE))
    print(f"Loaded {len(rows)} payment rows from {DATA_FILE.name}")
    streamed = show_chunk_parity(rows)
    show_file_streaming(rows, streamed)
    show_csv_normalisation(rows)
    show_key_canonicalisation()
    show_typed_record_normalisation()


if __name__ == "__main__":
    main()
