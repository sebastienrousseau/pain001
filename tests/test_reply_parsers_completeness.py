# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The reply parsers return every transaction and statement.

pain.002: only the first TxInfAndSts of each OrgnlPmtInfAndSts was read,
so in a partially accepted report the other transactions, including
rejections, were dropped. camt.053: only the first Stmt was read, the
camt.053.001.08 status (Sts/Cd) came back empty, and no entry exposed
its EndToEndId.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pain001.camt053 import parse_camt053_statement
from pain001.pain002 import parse_pain002_report

PAIN002 = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.002.001.03">
<CstmrPmtStsRpt><GrpHdr><MsgId>R1</MsgId>
<CreDtTm>2026-11-07T10:00:00</CreDtTm></GrpHdr>
<OrgnlGrpInfAndSts><OrgnlMsgId>M1</OrgnlMsgId>
<OrgnlMsgNmId>pain.001.001.03</OrgnlMsgNmId><GrpSts>PART</GrpSts>
</OrgnlGrpInfAndSts>
<OrgnlPmtInfAndSts><OrgnlPmtInfId>P1</OrgnlPmtInfId><PmtInfSts>PART</PmtInfSts>
<TxInfAndSts><OrgnlEndToEndId>E1</OrgnlEndToEndId><TxSts>ACCP</TxSts>
</TxInfAndSts>
<TxInfAndSts><OrgnlEndToEndId>E2</OrgnlEndToEndId><TxSts>RJCT</TxSts>
<StsRsnInf><Rsn><Cd>AC01</Cd></Rsn></StsRsnInf></TxInfAndSts>
</OrgnlPmtInfAndSts>
<OrgnlPmtInfAndSts><OrgnlPmtInfId>P2</OrgnlPmtInfId><PmtInfSts>ACCP</PmtInfSts>
</OrgnlPmtInfAndSts>
</CstmrPmtStsRpt></Document>
"""

CAMT053_V08 = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.08">
<BkToCstmrStmt><GrpHdr><MsgId>S</MsgId>
<CreDtTm>2026-11-07T10:00:00</CreDtTm></GrpHdr>
<Stmt><Id>ST1</Id><Acct><Id><IBAN>DE89370400440532013000</IBAN></Id>
<Ccy>EUR</Ccy></Acct>
<Ntry><Amt Ccy="EUR">10.00</Amt><CdtDbtInd>DBIT</CdtDbtInd>
<Sts><Cd>BOOK</Cd></Sts><BookgDt><Dt>2026-11-07</Dt></BookgDt>
<ValDt><Dt>2026-11-07</Dt></ValDt><BkTxCd/>
<NtryDtls><TxDtls><Refs><EndToEndId>E1</EndToEndId></Refs></TxDtls>
<TxDtls><Refs><EndToEndId>E2</EndToEndId></Refs></TxDtls></NtryDtls>
</Ntry></Stmt>
<Stmt><Id>ST2</Id><Acct><Id><IBAN>DE89370400440532013000</IBAN></Id>
<Ccy>USD</Ccy></Acct></Stmt>
</BkToCstmrStmt></Document>
"""


@pytest.fixture
def write(tmp_path, monkeypatch):
    """Write a document under the working directory and return its path."""
    monkeypatch.chdir(tmp_path)

    def _write(name: str, text: str) -> str:
        path = Path(name)
        path.write_text(text, encoding="utf-8")
        return str(path)

    return _write


def test_pain002_keeps_every_transaction(write):
    """A partially accepted block reports both transactions."""
    report = parse_pain002_report(write("r.xml", PAIN002))
    first, second = report["payment_statuses"]
    assert first["original_end_to_end_id"] == "E1"  # unchanged key
    transactions = first["transactions"]
    assert [t["original_end_to_end_id"] for t in transactions] == [
        "E1",
        "E2",
    ]
    assert transactions[1]["transaction_status"] == "RJCT"
    assert transactions[1]["status_reason"] == "AC01"
    assert second["transactions"] == []


def test_camt053_keeps_every_statement_and_reference(write):
    """Both statements, the coded status and EndToEndIds are returned."""
    report = parse_camt053_statement(write("s.xml", CAMT053_V08))
    assert report["statement_id"] == "ST1"  # unchanged key
    statements = report["statements"]
    assert [s["statement_id"] for s in statements] == ["ST1", "ST2"]
    assert statements[1]["currency"] == "USD"
    entry = report["entries"][0]
    assert entry["status"] == "BOOK"
    assert entry["end_to_end_ids"] == ["E1", "E2"]
    assert statements[1]["entries"] == []
