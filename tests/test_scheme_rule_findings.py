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

"""The SEPA and cross-border profiles' findings in full.

Each profile validates a compliant row followed by a row that breaks
every rule the profile owns, called directly rather than through the
composing ``validate_scheme``, so the profile name, the order of the
checks, and each finding's rule id, column, row index, severity and
message are all pinned.
"""

from __future__ import annotations

from typing import Any

from pain001.validation._scheme_rules import (
    AntiDuplicateProfile,
    CrossBorderCreditTransferProfile,
    SepaB2BDirectDebitProfile,
    SepaCreditTransferProfile,
    SepaDirectDebitProfile,
    SepaInstantCreditTransferProfile,
    ValidationProfile,
)

Finding = tuple[str, str | None, int, str, str]

GOOD = {
    "payment_currency": "EUR",
    "debtor_account_IBAN": "DE89370400440532013000",
    "creditor_account_IBAN": "FR1420041010050500013M02606",
    "creditor_agent_BIC": "BNPAFRPP",
    "service_level_code": "SEPA",
    "payment_amount": "100.00",
    "debtor_name": "Acme",
    "creditor_name": "Beta",
    "remittance_information": "R" * 140,
    "charge_bearer": "SLEV",
    "mandate_id": "MNDT-1",
    "sequence_type": "RCUR",
    "creditor_id": "DE98ZZZ09999999999",
}
BAD = {
    "payment_currency": "usd",
    "creditor_account_IBAN": "FR00",
    "creditor_agent_BIC": "BAD!",
    "service_level_code": "urgp",
    "payment_amount": "1.001",
    "debtor_name": "A{B}",
    "creditor_name": "N" * 71,
    "initiator_name": "I" * 70,
    "charge_bearer": "SHAR",
}
IBAN_RULE = "must be a valid IBAN (ISO 13616 / mod-97)"
SHARED_SEPA: list[Finding] = [
    (
        "SEPA-CCY",
        "payment_currency",
        1,
        "error",
        "SEPA requires EUR currency (got USD)",
    ),
    (
        "SEPA-DBTR-IBAN",
        "debtor_account_IBAN",
        1,
        "error",
        f"debtor_account_IBAN {IBAN_RULE}",
    ),
    (
        "SEPA-CDTR-IBAN",
        "creditor_account_IBAN",
        1,
        "error",
        f"creditor_account_IBAN {IBAN_RULE}",
    ),
    (
        "SEPA-BIC",
        "creditor_agent_BIC",
        1,
        "error",
        "creditor_agent_BIC 'BAD!' is not a valid BIC",
    ),
    (
        "SEPA-CHRGBR",
        "charge_bearer",
        1,
        "error",
        "SEPA allows only charge_bearer SLEV (got SHAR)",
    ),
    (
        "SEPA-SVCLVL",
        "service_level_code",
        1,
        "warning",
        "service_level_code should be 'SEPA' (got URGP)",
    ),
    (
        "SEPA-AMT",
        "payment_amount",
        1,
        "error",
        "payment_amount must have at most 2 decimal places (got 1.001)",
    ),
]
TEXT: list[Finding] = [
    (
        "SEPA-CHARSET",
        "debtor_name",
        1,
        "error",
        "debtor_name contains characters outside the ISO 20022 set: { }",
    ),
    (
        "SEPA-LEN",
        "creditor_name",
        1,
        "error",
        "creditor_name exceeds 70 characters (got 71)",
    ),
]


def _findings(
    profile: ValidationProfile, rows: list[dict[str, Any]]
) -> list[Finding]:
    """Run one profile directly and flatten its findings."""
    result = profile.validate(rows)
    assert result.profile == profile.name
    return [
        (v.rule, v.field, v.index, v.severity, v.message)
        for v in result.violations
    ]


def test_sct_reports_every_shared_rule_in_order() -> None:
    """SCT: currency, IBANs, BIC, charge bearer, level, amount, text."""
    profile = SepaCreditTransferProfile()
    assert _findings(profile, [GOOD, BAD]) == SHARED_SEPA + TEXT


def test_sct_inst_reports_its_own_ceiling() -> None:
    """SCT Inst: the shared rules, with the instant amount ceiling."""
    profile = SepaInstantCreditTransferProfile()
    assert _findings(profile, [GOOD, BAD]) == SHARED_SEPA + TEXT
    over = {**GOOD, "payment_amount": "100000.01"}
    assert _findings(profile, [GOOD, over]) == [
        (
            "SEPA-INST-AMT",
            "payment_amount",
            1,
            "error",
            "payment_amount must be <= 100000.00 EUR (got 100000.01)",
        ),
    ]


def test_sdd_adds_mandate_and_sequence_type() -> None:
    """SDD: the shared rules, then mandate id and sequence type."""
    profile = SepaDirectDebitProfile()
    assert _findings(profile, [GOOD, {**BAD, "sequence_type": "rpre"}]) == [
        *SHARED_SEPA,
        *TEXT,
        (
            "SDD-MNDT",
            "mandate_id",
            1,
            "error",
            "mandate_id is required for a SEPA Direct Debit",
        ),
        (
            "SDD-SEQTP",
            "sequence_type",
            1,
            "error",
            "sequence_type must be one of FNAL, FRST, OOFF, RCUR (got RPRE)",
        ),
    ]
    missing = {k: v for k, v in GOOD.items() if k != "sequence_type"}
    assert _findings(profile, [GOOD, missing]) == [
        (
            "SDD-SEQTP",
            "sequence_type",
            1,
            "error",
            "sequence_type must be one of FNAL, FRST, OOFF, RCUR (got empty)",
        ),
    ]


def test_b2b_adds_its_sequence_types_and_creditor_identifier() -> None:
    """B2B: the shared rules, mandate, FRST/RCUR only, creditor id."""
    profile = SepaB2BDirectDebitProfile()
    assert _findings(profile, [GOOD, {**BAD, "sequence_type": "ooff"}]) == [
        *SHARED_SEPA,
        *TEXT,
        (
            "SDD-MNDT",
            "mandate_id",
            1,
            "error",
            "mandate_id is required for a SEPA Direct Debit",
        ),
        (
            "B2B-SEQTP",
            "sequence_type",
            1,
            "error",
            "sequence_type must be one of FRST, RCUR for SEPA B2B (got OOFF)",
        ),
        (
            "B2B-CDTR-ID",
            "creditor_id",
            1,
            "error",
            "creditor_id is required for a SEPA B2B Direct Debit; provide "
            "the Creditor Identifier issued in the creditor's country",
        ),
    ]
    missing = {k: v for k, v in GOOD.items() if k != "sequence_type"}
    assert _findings(profile, [GOOD, missing]) == [
        (
            "B2B-SEQTP",
            "sequence_type",
            1,
            "error",
            "sequence_type must be one of FRST, RCUR for SEPA B2B (got empty)",
        ),
    ]


def test_cross_border_reports_its_own_rules() -> None:
    """Cross-border: ISO currency, IBANs, required BIC, amount, text, mix."""
    profile = CrossBorderCreditTransferProfile()
    usd = {**GOOD, "payment_currency": "USD"}
    bad = {**BAD, "payment_currency": "US1", "payment_amount": "0.5"}
    del bad["creditor_agent_BIC"]
    assert _findings(profile, [usd, bad, GOOD]) == [
        (
            "XB-CCY",
            "payment_currency",
            1,
            "error",
            "payment_currency must be a 3-letter ISO 4217 code (got US1)",
        ),
        (
            "SEPA-DBTR-IBAN",
            "debtor_account_IBAN",
            1,
            "error",
            f"debtor_account_IBAN {IBAN_RULE}",
        ),
        (
            "SEPA-CDTR-IBAN",
            "creditor_account_IBAN",
            1,
            "error",
            f"creditor_account_IBAN {IBAN_RULE}",
        ),
        (
            "XB-BIC",
            "creditor_agent_BIC",
            1,
            "error",
            "creditor_agent_BIC is required and must be a valid BIC for a "
            "cross-border transfer",
        ),
        *[(r, f, 1, s, m) for (r, f, _, s, m) in TEXT],
        (
            "XB-CCY-MIX",
            "payment_currency",
            2,
            "error",
            "payment_currency EUR differs from the batch currency USD; one "
            "PmtInf cannot mix currencies",
        ),
    ]


def test_amounts_at_and_below_the_bounds() -> None:
    """Below one is still positive; zero and garbage are rejected."""
    profile = SepaCreditTransferProfile()
    rows = [
        {**GOOD, "payment_amount": "0.01"},
        {**GOOD, "payment_amount": "0"},
        {**GOOD, "payment_amount": "abc"},
        {**GOOD, "payment_amount": "999999999.99"},
        {**GOOD, "payment_amount": "1000000000.00"},
    ]
    assert _findings(profile, rows) == [
        (
            "SEPA-AMT",
            "payment_amount",
            1,
            "error",
            "payment_amount must be > 0 (got 0)",
        ),
        (
            "SEPA-AMT",
            "payment_amount",
            2,
            "error",
            "payment_amount 'abc' is not a valid amount",
        ),
        (
            "SEPA-AMT",
            "payment_amount",
            4,
            "error",
            "payment_amount must be <= 999999999.99 EUR (got 1000000000.00)",
        ),
    ]


def test_duplicates_show_the_upper_case_iban_and_partners() -> None:
    """A lone row first does not stop later groups being reported."""
    lone = {
        "creditor_account_IBAN": "DE89370400440532013000",
        "payment_amount": "5",
        "payment_currency": "EUR",
        "requested_execution_date": "2026-01-02",
    }
    pair = {
        **lone,
        "creditor_account_IBAN": "fr14 2004 1010 0505 0001 3m02 606",
    }
    found = _findings(AntiDuplicateProfile(), [lone, pair, pair])
    message = (
        "same creditor IBAN FR1420041010050500013M02606, amount 5.00 EUR "
        "and execution date 2026-01-02"
    )
    assert found == [
        (
            "DUP-CREDITOR-DATE",
            "creditor_account_IBAN",
            1,
            "error",
            f"duplicate of row(s) 2: {message}",
        ),
        (
            "DUP-CREDITOR-DATE",
            "creditor_account_IBAN",
            2,
            "error",
            f"duplicate of row(s) 1: {message}",
        ),
    ]


def test_duplicate_amounts_round_half_up_to_the_minor_unit() -> None:
    """100.005 EUR buckets to 100.01 (half up), colliding with 100.01."""
    base = {
        "creditor_account_IBAN": "DE89370400440532013000",
        "payment_currency": "EUR",
        "requested_execution_date": "2026-01-02",
    }
    rows = [
        {**base, "payment_amount": "100.005"},
        {**base, "payment_amount": "100.01"},
    ]
    assert [f[2] for f in _findings(AntiDuplicateProfile(), rows)] == [0, 1]


def test_a_missing_currency_is_reported_as_empty() -> None:
    """SEPA and cross-border both say ``empty`` for an absent currency."""
    missing = {k: v for k, v in GOOD.items() if k != "payment_currency"}
    assert _findings(SepaCreditTransferProfile(), [missing]) == [
        (
            "SEPA-CCY",
            "payment_currency",
            0,
            "error",
            "SEPA requires EUR currency (got empty)",
        ),
    ]
    assert _findings(CrossBorderCreditTransferProfile(), [missing]) == [
        (
            "XB-CCY",
            "payment_currency",
            0,
            "error",
            "payment_currency must be a 3-letter ISO 4217 code (got empty)",
        ),
    ]


def test_cross_border_currency_shape_and_mix_after_a_malformed_row() -> None:
    """Four letters is not ISO 4217; a malformed first row sets no batch."""
    profile = CrossBorderCreditTransferProfile()
    rows = [
        {**GOOD, "payment_currency": "USDX"},
        {**GOOD, "payment_currency": "USD"},
        {**GOOD, "payment_currency": "EUR"},
    ]
    assert _findings(profile, rows) == [
        (
            "XB-CCY",
            "payment_currency",
            0,
            "error",
            "payment_currency must be a 3-letter ISO 4217 code (got USDX)",
        ),
        (
            "XB-CCY-MIX",
            "payment_currency",
            2,
            "error",
            "payment_currency EUR differs from the batch currency USD; one "
            "PmtInf cannot mix currencies",
        ),
    ]


def test_cross_border_amount_findings_carry_their_row() -> None:
    """The cross-border amount check reports on the row that breaks it."""
    profile = CrossBorderCreditTransferProfile()
    assert _findings(profile, [GOOD, {**GOOD, "payment_amount": "0"}]) == [
        (
            "SEPA-AMT",
            "payment_amount",
            1,
            "error",
            "payment_amount must be > 0 (got 0)",
        ),
    ]
