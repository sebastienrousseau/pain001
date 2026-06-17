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

"""Payment-scheme rulebook validation, layered on top of XSD validation.

XSD validation proves a message is *well-formed*; it does not prove the
payment obeys the rules of the scheme it will be cleared through. A SEPA
Credit Transfer, for example, must be in EUR, carry valid IBANs, and keep
text inside the ISO 20022 character set — none of which the XSD enforces.

This module adds that layer. A :class:`ValidationProfile` inspects the
loaded payment rows and returns structured :class:`SchemeViolation`
objects, so callers get machine-readable, row-addressable diagnostics
instead of an opaque pass/fail. Each rule id maps to a remediation hint
in :data:`REMEDIATIONS`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from pain001.validation.bic_validator import validate_bic_safe
from pain001.validation.charset import find_invalid_characters
from pain001.validation.iban_validator import validate_iban_safe

# Shared SEPA rulebook limits.
_SEPA_MAX_AMOUNT = Decimal("999999999.99")
# SEPA Instant Credit Transfer (SCT Inst) per-transaction ceiling.
_SCT_INST_MAX_AMOUNT = Decimal("100000.00")
_SEPA_NAME_MAX_LEN = 70
_SEPA_REMITTANCE_MAX_LEN = 140
_SEPA_TEXT_FIELDS = (
    "initiator_name",
    "debtor_name",
    "creditor_name",
    "remittance_information",
)
_SDD_SEQUENCE_TYPES = frozenset({"FRST", "RCUR", "OOFF", "FNAL"})

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
    "SEPA-CHARSET": "Limit text to the ISO 20022 Latin set; use "
    "sanitize_to_charset() to transliterate accents and symbols.",
    "SEPA-LEN": "Shorten the field to its scheme maximum (70 for names, "
    "140 for remittance information).",
    "SEPA-SVCLVL": "Set service_level_code to 'SEPA' for a SEPA payment.",
    "SDD-MNDT": "Provide mandate_id; a SEPA Direct Debit requires the "
    "mandate reference agreed with the debtor.",
    "SDD-SEQTP": "Set sequence_type to one of FRST, RCUR, OOFF, or FNAL.",
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


def _check_currency(
    row: dict[str, Any], index: int, result: SchemeValidationResult
) -> None:
    """Require the payment currency to be EUR.

    Args:
        row: The payment row.
        index: Zero-based row index.
        result: The result accumulator to append violations to.
    """
    currency = str(row.get("payment_currency", "")).upper()
    if currency != "EUR":
        result.violations.append(
            SchemeViolation(
                rule="SEPA-CCY",
                message=(
                    f"SEPA requires EUR currency (got {currency or 'empty'})"
                ),
                index=index,
                field="payment_currency",
            )
        )


def _check_ibans(
    row: dict[str, Any], index: int, result: SchemeValidationResult
) -> None:
    """Require valid debtor and creditor IBANs.

    Args:
        row: The payment row.
        index: Zero-based row index.
        result: The result accumulator to append violations to.
    """
    for field_name, rule in (
        ("debtor_account_IBAN", "SEPA-DBTR-IBAN"),
        ("creditor_account_IBAN", "SEPA-CDTR-IBAN"),
    ):
        iban = str(row.get(field_name, "")).strip()
        if not iban or not validate_iban_safe(iban):
            result.violations.append(
                SchemeViolation(
                    rule=rule,
                    message=(
                        f"{field_name} must be a valid IBAN "
                        "(ISO 13616 / mod-97)"
                    ),
                    index=index,
                    field=field_name,
                )
            )


def _check_bic(
    row: dict[str, Any], index: int, result: SchemeValidationResult
) -> None:
    """Validate the creditor agent BIC when one is supplied.

    Args:
        row: The payment row.
        index: Zero-based row index.
        result: The result accumulator to append violations to.
    """
    bic = str(row.get("creditor_agent_BIC", "")).strip()
    if bic and not validate_bic_safe(bic):
        result.violations.append(
            SchemeViolation(
                rule="SEPA-BIC",
                message=f"creditor_agent_BIC '{bic}' is not a valid BIC",
                index=index,
                field="creditor_agent_BIC",
            )
        )


def _check_currency_iso(
    row: dict[str, Any], index: int, result: SchemeValidationResult
) -> None:
    """Require a well-formed ISO 4217 currency (any currency, not just EUR).

    Args:
        row: The payment row.
        index: Zero-based row index.
        result: The result accumulator to append violations to.
    """
    currency = str(row.get("payment_currency", "")).strip()
    if not (len(currency) == 3 and currency.isalpha()):
        result.violations.append(
            SchemeViolation(
                rule="XB-CCY",
                message=(
                    "payment_currency must be a 3-letter ISO 4217 code "
                    f"(got {currency or 'empty'})"
                ),
                index=index,
                field="payment_currency",
            )
        )


def _check_bic_required(
    row: dict[str, Any], index: int, result: SchemeValidationResult
) -> None:
    """Require a valid creditor agent BIC (mandatory for cross-border).

    Args:
        row: The payment row.
        index: Zero-based row index.
        result: The result accumulator to append violations to.
    """
    bic = str(row.get("creditor_agent_BIC", "")).strip()
    if not bic or not validate_bic_safe(bic):
        result.violations.append(
            SchemeViolation(
                rule="XB-BIC",
                message=(
                    "creditor_agent_BIC is required and must be a valid BIC "
                    "for a cross-border transfer"
                ),
                index=index,
                field="creditor_agent_BIC",
            )
        )


def _check_service_level(
    row: dict[str, Any], index: int, result: SchemeValidationResult
) -> None:
    """Warn when the service level is not declared as SEPA.

    Args:
        row: The payment row.
        index: Zero-based row index.
        result: The result accumulator to append violations to.
    """
    svc = str(row.get("service_level_code", "SEPA")).upper()
    if svc != "SEPA":
        result.violations.append(
            SchemeViolation(
                rule="SEPA-SVCLVL",
                message=(f"service_level_code should be 'SEPA' (got {svc})"),
                index=index,
                field="service_level_code",
                severity="warning",
            )
        )


def _check_amount(
    row: dict[str, Any],
    index: int,
    result: SchemeValidationResult,
    max_amount: Decimal = _SEPA_MAX_AMOUNT,
    cap_rule: str = "SEPA-AMT",
) -> None:
    """Enforce a positive amount within a scheme's per-transaction ceiling.

    Args:
        row: The payment row.
        index: Zero-based row index.
        result: The result accumulator to append violations to.
        max_amount: The inclusive per-transaction ceiling for this scheme.
        cap_rule: Rule id raised when the amount exceeds ``max_amount``
            (lets stricter schemes, e.g. SCT Inst, flag their own cap).
    """
    raw = row.get("payment_amount")
    amount: Decimal | None
    try:
        amount = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        amount = None
    if amount is None or not amount.is_finite():
        result.violations.append(
            SchemeViolation(
                rule="SEPA-AMT",
                message=f"payment_amount '{raw}' is not a valid amount",
                index=index,
                field="payment_amount",
            )
        )
        return
    if amount <= 0:
        result.violations.append(
            SchemeViolation(
                rule="SEPA-AMT",
                message=f"payment_amount must be > 0 (got {amount})",
                index=index,
                field="payment_amount",
            )
        )
        return
    if amount > max_amount:
        result.violations.append(
            SchemeViolation(
                rule=cap_rule,
                message=(
                    f"payment_amount must be <= {max_amount} EUR "
                    f"(got {amount})"
                ),
                index=index,
                field="payment_amount",
            )
        )
        return
    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        result.violations.append(
            SchemeViolation(
                rule="SEPA-AMT",
                message=(
                    "payment_amount must have at most 2 decimal places "
                    f"(got {amount})"
                ),
                index=index,
                field="payment_amount",
            )
        )


def _check_text_fields(
    row: dict[str, Any], index: int, result: SchemeValidationResult
) -> None:
    """Enforce ISO 20022 charset and length on text fields.

    Args:
        row: The payment row.
        index: Zero-based row index.
        result: The result accumulator to append violations to.
    """
    for field_name in _SEPA_TEXT_FIELDS:
        value = str(row.get(field_name, ""))
        if not value:
            continue
        invalid = find_invalid_characters(value)
        if invalid:
            result.violations.append(
                SchemeViolation(
                    rule="SEPA-CHARSET",
                    message=(
                        f"{field_name} contains characters outside the "
                        f"ISO 20022 set: {' '.join(invalid)}"
                    ),
                    index=index,
                    field=field_name,
                )
            )
        max_len = (
            _SEPA_REMITTANCE_MAX_LEN
            if field_name == "remittance_information"
            else _SEPA_NAME_MAX_LEN
        )
        if len(value) > max_len:
            result.violations.append(
                SchemeViolation(
                    rule="SEPA-LEN",
                    message=(
                        f"{field_name} exceeds {max_len} characters "
                        f"(got {len(value)})"
                    ),
                    index=index,
                    field=field_name,
                )
            )


def _check_mandate(
    row: dict[str, Any], index: int, result: SchemeValidationResult
) -> None:
    """Require a mandate id for a direct debit.

    Args:
        row: The payment row.
        index: Zero-based row index.
        result: The result accumulator to append violations to.
    """
    if not str(row.get("mandate_id", "")).strip():
        result.violations.append(
            SchemeViolation(
                rule="SDD-MNDT",
                message="mandate_id is required for a SEPA Direct Debit",
                index=index,
                field="mandate_id",
            )
        )


def _check_sequence_type(
    row: dict[str, Any], index: int, result: SchemeValidationResult
) -> None:
    """Require a valid direct-debit sequence type.

    Args:
        row: The payment row.
        index: Zero-based row index.
        result: The result accumulator to append violations to.
    """
    seq = str(row.get("sequence_type", "")).upper()
    if seq not in _SDD_SEQUENCE_TYPES:
        result.violations.append(
            SchemeViolation(
                rule="SDD-SEQTP",
                message=(
                    "sequence_type must be one of "
                    f"{', '.join(sorted(_SDD_SEQUENCE_TYPES))} (got "
                    f"{seq or 'empty'})"
                ),
                index=index,
                field="sequence_type",
            )
        )


class ValidationProfile(ABC):
    """Base class for a payment-scheme rulebook validator."""

    #: Stable, lowercase profile identifier (e.g. ``"sepa-sct"``).
    name: str = ""

    @abstractmethod
    def validate(self, data: list[dict[str, Any]]) -> SchemeValidationResult:
        """Validate payment rows against this scheme's rulebook.

        Args:
            data: Loaded payment rows (the normalised internal form).

        Returns:
            A :class:`SchemeValidationResult` listing every violation.
        """


class SepaCreditTransferProfile(ValidationProfile):
    """SEPA Credit Transfer (SCT) rulebook checks.

    Enforces the core, machine-checkable SCT constraints that the XSD
    cannot: EUR currency, valid debtor/creditor IBANs, optional but
    well-formed BIC, the EUR amount ceiling, and ISO 20022 character-set
    and length limits on text fields.
    """

    name = "sepa-sct"

    def validate(self, data: list[dict[str, Any]]) -> SchemeValidationResult:
        """Validate payment rows against the SEPA SCT rulebook.

        Args:
            data: Loaded payment rows (the normalised internal form).

        Returns:
            A :class:`SchemeValidationResult` listing every violation.
        """
        result = SchemeValidationResult(profile=self.name)
        for index, row in enumerate(data):
            _check_currency(row, index, result)
            _check_ibans(row, index, result)
            _check_bic(row, index, result)
            _check_service_level(row, index, result)
            _check_amount(row, index, result)
            _check_text_fields(row, index, result)
        return result


class SepaDirectDebitProfile(ValidationProfile):
    """SEPA Direct Debit (SDD) rulebook checks.

    Adds the direct-debit-specific constraints — a mandate reference and a
    valid sequence type — on top of the shared SEPA rules (EUR currency,
    IBANs, BIC, amount ceiling, charset, and length).
    """

    name = "sepa-sdd"

    def validate(self, data: list[dict[str, Any]]) -> SchemeValidationResult:
        """Validate payment rows against the SEPA SDD rulebook.

        Args:
            data: Loaded payment rows (the normalised internal form).

        Returns:
            A :class:`SchemeValidationResult` listing every violation.
        """
        result = SchemeValidationResult(profile=self.name)
        for index, row in enumerate(data):
            _check_currency(row, index, result)
            _check_ibans(row, index, result)
            _check_bic(row, index, result)
            _check_service_level(row, index, result)
            _check_amount(row, index, result)
            _check_text_fields(row, index, result)
            _check_mandate(row, index, result)
            _check_sequence_type(row, index, result)
        return result


class SepaInstantCreditTransferProfile(ValidationProfile):
    """SEPA Instant Credit Transfer (SCT Inst) rulebook checks.

    Identical to SEPA SCT but enforces the instant scheme's stricter
    per-transaction ceiling of 100,000.00 EUR (rule ``SEPA-INST-AMT``).
    """

    name = "sepa-inst"

    def validate(self, data: list[dict[str, Any]]) -> SchemeValidationResult:
        """Validate payment rows against the SEPA SCT Inst rulebook.

        Args:
            data: Loaded payment rows (the normalised internal form).

        Returns:
            A :class:`SchemeValidationResult` listing every violation.
        """
        result = SchemeValidationResult(profile=self.name)
        for index, row in enumerate(data):
            _check_currency(row, index, result)
            _check_ibans(row, index, result)
            _check_bic(row, index, result)
            _check_service_level(row, index, result)
            _check_amount(
                row,
                index,
                result,
                max_amount=_SCT_INST_MAX_AMOUNT,
                cap_rule="SEPA-INST-AMT",
            )
            _check_text_fields(row, index, result)
        return result


class CrossBorderCreditTransferProfile(ValidationProfile):
    """Generic cross-border credit transfer checks (beyond SEPA).

    A pragmatic, multi-currency rulebook for international credit transfers:
    valid debtor/creditor IBANs, a well-formed ISO 4217 currency (any
    currency, not only EUR), a **mandatory** creditor agent BIC (cross-border
    routing needs it), a positive amount within the ISO ceiling, and ISO
    20022 charset/length limits. It is intentionally generic rather than a
    full CBPR+ implementation.
    """

    name = "xborder-ct"

    def validate(self, data: list[dict[str, Any]]) -> SchemeValidationResult:
        """Validate payment rows against the cross-border rulebook.

        Args:
            data: Loaded payment rows (the normalised internal form).

        Returns:
            A :class:`SchemeValidationResult` listing every violation.
        """
        result = SchemeValidationResult(profile=self.name)
        for index, row in enumerate(data):
            _check_currency_iso(row, index, result)
            _check_ibans(row, index, result)
            _check_bic_required(row, index, result)
            _check_amount(row, index, result)
            _check_text_fields(row, index, result)
        return result


#: Registry of available scheme profiles, keyed by their ``name``.
PROFILES: dict[str, ValidationProfile] = {
    SepaCreditTransferProfile.name: SepaCreditTransferProfile(),
    SepaDirectDebitProfile.name: SepaDirectDebitProfile(),
    SepaInstantCreditTransferProfile.name: (
        SepaInstantCreditTransferProfile()
    ),
    CrossBorderCreditTransferProfile.name: (
        CrossBorderCreditTransferProfile()
    ),
}


def validate_scheme(
    data: list[dict[str, Any]], profile: str = "sepa-sct"
) -> SchemeValidationResult:
    """Validate payment rows against a named scheme profile.

    Args:
        data: Loaded payment rows (the normalised internal form).
        profile: Profile name to apply (default: ``"sepa-sct"``).

    Returns:
        A :class:`SchemeValidationResult` listing every violation.

    Raises:
        ValueError: If ``profile`` is not a registered profile name.

    Example:
        >>> rows = [{
        ...     "payment_currency": "USD",
        ...     "debtor_account_IBAN": "DE89370400440532013000",
        ...     "creditor_account_IBAN": "FR1420041010050500013M02606",
        ...     "payment_amount": "100.00",
        ... }]
        >>> result = validate_scheme(rows, profile="sepa-sct")
        >>> result.is_valid
        False
        >>> result.violations[0].rule
        'SEPA-CCY'
    """
    try:
        chosen = PROFILES[profile]
    except KeyError as exc:
        available = ", ".join(sorted(PROFILES))
        raise ValueError(
            f"Unknown scheme profile '{profile}'. Available: {available}"
        ) from exc
    return chosen.validate(data)
