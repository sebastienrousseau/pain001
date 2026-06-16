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
instead of an opaque pass/fail.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from pain001.validation.bic_validator import validate_bic_safe
from pain001.validation.charset import find_invalid_characters
from pain001.validation.iban_validator import validate_iban_safe

# SEPA Credit Transfer rulebook limits.
_SEPA_MAX_AMOUNT = Decimal("999999999.99")
_SEPA_NAME_MAX_LEN = 70
_SEPA_REMITTANCE_MAX_LEN = 140
_SEPA_TEXT_FIELDS = (
    "initiator_name",
    "debtor_name",
    "creditor_name",
    "remittance_information",
)


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
            self._check_currency(row, index, result)
            self._check_ibans(row, index, result)
            self._check_bic(row, index, result)
            self._check_service_level(row, index, result)
            self._check_amount(row, index, result)
            self._check_text_fields(row, index, result)
        return result

    @staticmethod
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
                        "SEPA Credit Transfer requires EUR currency "
                        f"(got {currency or 'empty'})"
                    ),
                    index=index,
                    field="payment_currency",
                )
            )

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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
                    message=(
                        "service_level_code should be 'SEPA' for an SCT "
                        f"(got {svc})"
                    ),
                    index=index,
                    field="service_level_code",
                    severity="warning",
                )
            )

    @staticmethod
    def _check_amount(
        row: dict[str, Any], index: int, result: SchemeValidationResult
    ) -> None:
        """Enforce a positive amount within the SEPA ceiling.

        Args:
            row: The payment row.
            index: Zero-based row index.
            result: The result accumulator to append violations to.
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
        if amount <= 0 or amount > _SEPA_MAX_AMOUNT:
            result.violations.append(
                SchemeViolation(
                    rule="SEPA-AMT",
                    message=(
                        "payment_amount must be > 0 and "
                        f"<= {_SEPA_MAX_AMOUNT} EUR (got {amount})"
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

    @staticmethod
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


#: Registry of available scheme profiles, keyed by their ``name``.
PROFILES: dict[str, ValidationProfile] = {
    SepaCreditTransferProfile.name: SepaCreditTransferProfile(),
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
