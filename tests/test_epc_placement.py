# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""EPC-PMT-002 and EPC-PMT-003 accept the batch or every transaction.

EPC allows the service level (``PmtTpInf/SvcLvl``) and the charge
bearer (``ChrgBr``) on the payment batch or on each transaction. Until
0.0.82 the bundled SEPA rulebook required both on the batch, so it
rejected files EPC accepts. Each rule now holds when the batch carries
the SEPA value, or carries nothing and every transaction does, and
still fails when a value is missing from both places.
"""

from __future__ import annotations

import pytest

from pain001.schematron import validate_schematron

#: A test-form BIC and IBANs that pass mod-97; none belongs to a bank.
_TX = """
      <CdtTrfTxInf>
        <PmtId><EndToEndId>E2E-{index}</EndToEndId></PmtId>{tx_type}
        <Amt><InstdAmt Ccy="EUR">10.00</InstdAmt></Amt>{tx_charge}
        <Cdtr><Nm>Creditor {index}</Nm></Cdtr>
        <CdtrAcct><Id><IBAN>FR1420041010050500013M02606</IBAN></Id></CdtrAcct>
      </CdtTrfTxInf>"""

_DOC = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:{message_type}">
  <CstmrCdtTrfInitn>
    <GrpHdr><MsgId>M-1</MsgId><NbOfTxs>{count}</NbOfTxs></GrpHdr>
    <PmtInf>
      <PmtInfId>P-1</PmtInfId>
      <PmtMtd>TRF</PmtMtd>{batch_type}
      <Dbtr><Nm>Debtor</Nm></Dbtr>
      <DbtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></DbtrAcct>{batch_charge}{transactions}
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>
"""


def _service(code: str | None) -> str:
    if code is None:
        return ""
    return f"\n        <PmtTpInf><SvcLvl><Cd>{code}</Cd></SvcLvl></PmtTpInf>"


def _charge(bearer: str | None) -> str:
    return "" if bearer is None else f"\n        <ChrgBr>{bearer}</ChrgBr>"


def _document(
    *,
    batch_charge: str | None = "SLEV",
    tx_charges: tuple[str | None, ...] = (None, None),
    batch_service: str | None = "SEPA",
    tx_services: tuple[str | None, ...] | None = None,
    message_type: str = "pain.001.001.03",
) -> str:
    services = tx_services or (None,) * len(tx_charges)
    transactions = "".join(
        _TX.format(
            index=index,
            tx_type=_service(service),
            tx_charge=_charge(charge),
        )
        for index, (charge, service) in enumerate(
            zip(tx_charges, services, strict=True)
        )
    )
    return _DOC.format(
        message_type=message_type,
        count=len(tx_charges),
        batch_type=_service(batch_service),
        batch_charge=_charge(batch_charge),
        transactions=transactions,
    )


def _failed(xml: str) -> set[str]:
    result = validate_schematron(xml, rulebook="sepa")
    return {violation.rule_id for violation in result.violations}


VERSIONS = ["pain.001.001.03", "pain.001.001.09"]


@pytest.mark.parametrize("message_type", VERSIONS)
class TestChargeBearer:
    """EPC-PMT-003, with EPC-SCT-002 for a transaction's own value."""

    def test_slev_only_on_the_batch_passes(self, message_type: str) -> None:
        xml = _document(batch_charge="SLEV", message_type=message_type)
        assert _failed(xml) == set()

    def test_slev_only_on_each_transaction_passes(
        self, message_type: str
    ) -> None:
        xml = _document(
            batch_charge=None,
            tx_charges=("SLEV", "SLEV"),
            message_type=message_type,
        )
        assert _failed(xml) == set()

    def test_missing_from_the_batch_and_a_transaction_fails(
        self, message_type: str
    ) -> None:
        xml = _document(
            batch_charge=None,
            tx_charges=("SLEV", None),
            message_type=message_type,
        )
        assert _failed(xml) == {"EPC-PMT-003"}

    def test_missing_everywhere_fails(self, message_type: str) -> None:
        xml = _document(batch_charge=None, message_type=message_type)
        assert _failed(xml) == {"EPC-PMT-003"}

    def test_a_transaction_with_shar_fails(self, message_type: str) -> None:
        xml = _document(
            batch_charge=None,
            tx_charges=("SLEV", "SHAR"),
            message_type=message_type,
        )
        assert _failed(xml) == {"EPC-PMT-003", "EPC-SCT-002"}

    def test_shar_on_a_transaction_under_a_slev_batch_fails(
        self, message_type: str
    ) -> None:
        xml = _document(
            batch_charge="SLEV",
            tx_charges=("SHAR", None),
            message_type=message_type,
        )
        assert _failed(xml) == {"EPC-SCT-002"}

    def test_shar_on_the_batch_fails(self, message_type: str) -> None:
        xml = _document(
            batch_charge="SHAR",
            tx_charges=("SLEV", "SLEV"),
            message_type=message_type,
        )
        assert _failed(xml) == {"EPC-PMT-003"}


@pytest.mark.parametrize("message_type", VERSIONS)
class TestServiceLevel:
    """EPC-PMT-002."""

    def test_sepa_only_on_the_batch_passes(self, message_type: str) -> None:
        xml = _document(batch_service="SEPA", message_type=message_type)
        assert _failed(xml) == set()

    def test_sepa_only_on_each_transaction_passes(
        self, message_type: str
    ) -> None:
        xml = _document(
            batch_service=None,
            tx_services=("SEPA", "SEPA"),
            message_type=message_type,
        )
        assert _failed(xml) == set()

    def test_missing_from_the_batch_and_a_transaction_fails(
        self, message_type: str
    ) -> None:
        xml = _document(
            batch_service=None,
            tx_services=("SEPA", None),
            message_type=message_type,
        )
        assert _failed(xml) == {"EPC-PMT-002"}

    def test_missing_everywhere_fails(self, message_type: str) -> None:
        xml = _document(batch_service=None, message_type=message_type)
        assert _failed(xml) == {"EPC-PMT-002"}

    def test_another_code_on_a_transaction_fails(
        self, message_type: str
    ) -> None:
        xml = _document(
            batch_service=None,
            tx_services=("SEPA", "URGP"),
            message_type=message_type,
        )
        assert _failed(xml) == {"EPC-PMT-002"}

    def test_another_code_on_the_batch_fails(self, message_type: str) -> None:
        xml = _document(
            batch_service="URGP",
            tx_services=("SEPA", "SEPA"),
            message_type=message_type,
        )
        assert _failed(xml) == {"EPC-PMT-002"}


def test_a_batch_with_no_transactions_fails_both_rules() -> None:
    xml = _document(batch_charge=None, batch_service=None, tx_charges=())
    assert _failed(xml) == {"EPC-PMT-002", "EPC-PMT-003"}
