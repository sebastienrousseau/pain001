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

"""Scheme validation results: violations, results and remediation hints.

Shared by the built-in rulebook in :mod:`pain001.validation._scheme_rules`
and the batch-level checks, so neither has to import the other.
"""

from dataclasses import dataclass, field
from typing import Any

#: Remediation hint for each rule id, surfaced by the CLI ``--explain`` flag.
REMEDIATIONS: dict[str, str] = {
    "SEPA-CCY": "Set payment_currency to 'EUR'; SEPA clears euro only.",
    "SEPA-DBTR-IBAN": "Provide a valid debtor IBAN (correct length and "
    "mod-97 check digits for the country).",
    "SEPA-CDTR-IBAN": "Provide a valid creditor IBAN (correct length and "
    "mod-97 check digits for the country).",
    "SEPA-BIC": "Supply a valid 8- or 11-character BIC, or omit it "
    "entirely (SEPA is IBAN-only since 2016).",
    "SEPA-AMT": "Use a positive amount with at most 2 decimal places, "
    "not exceeding 999,999,999.99 EUR.",
    "SEPA-INST-AMT": "SEPA Instant caps a single transfer at 100,000.00 "
    "EUR; split larger amounts or use a standard SCT.",
    "XB-CCY": "Provide a 3-letter ISO 4217 currency code (any currency).",
    "XB-BIC": "Cross-border transfers require a valid creditor agent BIC "
    "for routing.",
    "XB-CCY-MIX": "Generate one file per currency; every row is written "
    "into a single PmtInf, whose CtrlSum would add the currencies together.",
    "SEPA-CHARSET": "Limit text to the ISO 20022 Latin set; use "
    "sanitize_to_charset() to transliterate accents and symbols.",
    "SEPA-LEN": "Shorten the field to its scheme maximum (70 for names, "
    "140 for remittance information).",
    "SEPA-SVCLVL": "Set service_level_code to 'SEPA' for a SEPA payment.",
    "SDD-MNDT": "Provide mandate_id; a SEPA Direct Debit requires the "
    "mandate reference agreed with the debtor.",
    "SDD-SEQTP": "Set sequence_type to one of FRST, RCUR, OOFF, or FNAL.",
    "B2B-SEQTP": (
        "SEPA B2B accepts only FRST or RCUR sequence types "
        "(OOFF and FNAL are CORE-only)."
    ),
    "B2B-CDTR-ID": (
        "Provide creditor_id; the SEPA B2B rulebook requires the "
        "Creditor Identifier (CI) issued in the creditor's country."
    ),
    "DUP-CREDITOR-DATE": (
        "Remove or merge the duplicate rows. If both payments are "
        "intended, give them distinct amounts or execution dates, or "
        "split them across batches."
    ),
}


def remediation_for(rule: str) -> str:
    """Return the remediation hint for a rule id.

    Args:
        rule: The rule identifier (e.g. ``"SEPA-CCY"``).

    Returns:
        The remediation hint, or an empty string if the rule is unknown.
    """
    return REMEDIATIONS.get(rule, "")


@dataclass(frozen=True)
class SchemeViolation:
    """A single scheme-rule breach found in a payment row.

    Attributes:
        rule: Stable identifier of the rule (e.g. ``"SEPA-CCY"``).
        message: Human-readable description of the breach.
        index: Zero-based index of the offending payment row.
        field: Name of the offending field, when applicable.
        severity: ``"error"`` (scheme would reject) or ``"warning"``.
    """

    rule: str
    message: str
    index: int
    field: str | None = None
    severity: str = "error"

    @property
    def remediation(self) -> str:
        """Return the remediation hint for this violation's rule.

        Returns:
            The remediation hint, or an empty string if none is defined.
        """
        return remediation_for(self.rule)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the violation.

        Returns:
            A dict with the rule, message, index, field, severity, and
            remediation hint.
        """
        return {
            "rule": self.rule,
            "message": self.message,
            "index": self.index,
            "field": self.field,
            "severity": self.severity,
            "remediation": self.remediation,
        }


@dataclass
class SchemeValidationResult:
    """Outcome of validating payment rows against a scheme profile.

    Attributes:
        profile: Name of the profile that produced this result.
        violations: All violations found, in row order.
    """

    profile: str
    violations: list[SchemeViolation] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Whether the rows are free of error-severity violations.

        Returns:
            ``True`` when no ``"error"`` violations were found (warnings
            are allowed), ``False`` otherwise.
        """
        return not any(v.severity == "error" for v in self.violations)

    def __bool__(self) -> bool:
        """Allow truthiness checks to mirror :attr:`is_valid`.

        Returns:
            The value of :attr:`is_valid`.
        """
        return self.is_valid
