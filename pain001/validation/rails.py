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

"""Rail profiles: the public scheme rules of eighteen payment rails.

Each :class:`Rail` is a declarative rulebook for one rail in one market,
drawn from the public scheme and bank documents the corpus plan cites
(ADR-0003, workstream 4): the currency and per-item ceiling, the
service level and local instrument the rail expects, the shape of a
domestic account and clearing member, reference lengths, purpose and
regulatory-reporting mandates, address and UETR requirements, and for
direct debits the mandate, sequence and creditor-identifier rules.
One engine, :class:`RailProfile`, turns a rail into a
:class:`~pain001.validation.schemes.ValidationProfile`, so every rail
composes with the SEPA profiles and ``anti-duplicate`` through the
comma syntax (``--scheme uk-chaps,anti-duplicate``) and reaches the
CLI, REST and MCP surfaces through the plugin registry unchanged.

Rules a public document states are errors; rules the plan marks as
typical bank practice or an assumption are warnings and say so.
:class:`PurposeMandate` adds the five country purpose-code mandates
(AE, QA, MY, GB, HK) the plan names, as their own profiles.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from pain001.validation.bic_validator import validate_bic_safe
from pain001.validation.iban_validator import validate_iban_safe
from pain001.validation.schemes import (
    PROFILES,
    REMEDIATIONS,
    SchemeValidationResult,
    SchemeViolation,
    ValidationProfile,
)

#: Nacha Standard Entry Class codes a pain.001 may carry in LclInstrm/Cd.
SEC_CODES: frozenset[str] = frozenset(
    {"ACK", "ADV", "ARC", "ATX", "BOC", "CCD", "CIE", "COR", "CTX", "DNE",
     "ENR", "IAT", "MTE", "POP", "POS", "PPD", "RCK", "SHR", "TEL", "TRC",
     "TRX", "WEB", "XCK"}
)  # fmt: skip
#: Bacs transaction codes the plan maps sequence types to (an assumption).
BACS_DD_CODES: frozenset[str] = frozenset({"01", "17", "18", "19"})
UAE_REGULATORY = re.compile(r"^/(BENEFRES|ORDERRES)/AE//[A-Z]{3}$")


@dataclass(frozen=True)
class Domestic:
    """A domestic routing-and-account shape.

    Attributes:
        clearing_systems: Accepted ``ClrSysId`` codes (``GBDSC``, ``USABA``).
        member_digits: Length of the member id (sort code, routing number).
        account_digits: Inclusive length range of the domestic account id.
        member_check: ``aba`` to verify the ABA check digit, else ``None``.
    """

    clearing_systems: tuple[str, ...]
    member_digits: int
    account_digits: tuple[int, int]
    member_check: str | None = None


@dataclass(frozen=True)
class Rail:
    """One rail's rulebook. Every field is optional; unset means unchecked.

    Attributes:
        name: Profile id, e.g. ``uk-fps``.
        title: Human title.
        prefix: Rule-id prefix, e.g. ``UK-FPS``.
        messages: Message families the rail carries.
        sources: The public documents the rules come from.
        currencies: Accepted currencies; empty means any ISO 4217 code.
        max_amount: Per-item ceiling.
        max_amount_severity: ``error`` for a scheme limit, ``warning`` for
            a typical bank limit.
        service_levels: Expected ``SvcLvl/Cd`` values (warning when other).
        local_instruments: Accepted ``LclInstrm/Cd`` (empty tuple means the
            rail carries none; ``None`` means unchecked).
        local_instrument_proprietary: Accepted ``LclInstrm/Prtry`` values.
        local_instrument_severity: Severity of the local-instrument rule.
        bic_required: The creditor agent (pain.008: debtor agent) needs a BIC.
        both_bics_required: Both agents need a BIC.
        iban_countries: The counterparty IBAN must start with one of these.
        domestic: Domestic routing shape, accepted instead of an IBAN.
        end_to_end_max: Ceiling on the end-to-end id length.
        remittance_max: Ceiling on unstructured remittance length.
        remittance_severity: Severity of the remittance rule.
        purpose: ``require``, ``warn`` or ``None``; a present purpose code
            must be in the ISO external list either way.
        regulatory: ``require`` or ``warn`` for a regulatory-reporting code.
        regulatory_pattern: Regex the regulatory info must match.
        charge_bearers: Accepted ``ChrgBr`` values.
        charge_bearer_severity: Severity of the charge-bearer rule.
        address_required: Counterparty needs town and country.
        address_severity: Severity of the address rule.
        uetr_required: The transaction needs a UETR (warning: .03 has none).
        sequence_types: Accepted ``SeqTp`` values (pain.008).
        mandate_max: Ceiling on the mandate id length (pain.008).
        creditor_id_pattern: Regex the creditor identifier must match.
        creditor_reference: ``ch`` (QRR/SCOR rules) or ``ocr`` (2 to 25 digits).
        batch_booking: Expected ``BtchBookg`` value (warning).
    """

    name: str
    title: str
    prefix: str
    messages: tuple[str, ...]
    sources: tuple[str, ...]
    currencies: tuple[str, ...] = ()
    max_amount: Decimal | None = None
    max_amount_severity: str = "error"
    service_levels: tuple[str, ...] = ()
    local_instruments: tuple[str, ...] | None = None
    local_instrument_proprietary: tuple[str, ...] = ()
    local_instrument_severity: str = "warning"
    bic_required: bool = False
    both_bics_required: bool = False
    iban_countries: tuple[str, ...] = ()
    domestic: Domestic | None = None
    end_to_end_max: int | None = None
    remittance_max: int | None = None
    remittance_severity: str = "warning"
    purpose: str | None = None
    regulatory: str | None = None
    regulatory_pattern: re.Pattern[str] | None = None
    charge_bearers: tuple[str, ...] = ()
    charge_bearer_severity: str = "error"
    address_required: bool = False
    address_severity: str = "error"
    uetr_required: bool = False
    sequence_types: tuple[str, ...] = ()
    mandate_max: int | None = None
    creditor_id_pattern: re.Pattern[str] | None = None
    creditor_reference: str | None = None
    batch_booking: str | None = None


# --- small check-digit helpers (kept local to avoid a package cycle) ---------


def _mod97_alpha(text: str) -> int:
    """MOD 97-10 over a string with letters mapped A=10 ... Z=35."""
    digits = "".join(str(int(ch, 36)) for ch in text)
    remainder = 0
    for ch in digits:
        remainder = (remainder * 10 + int(ch)) % 97
    return remainder


def _luhn_ok(digits: str) -> bool:
    """True when ``digits`` pass the Luhn mod-10 check."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        value = int(ch) * (2 if i % 2 == 1 else 1)
        total += value - 9 if value > 9 else value
    return total % 10 == 0


def _aba_ok(routing: str) -> bool:
    """True when ``routing`` is nine digits with a valid ABA check digit."""
    if len(routing) != 9 or not routing.isdigit():
        return False
    d = [int(c) for c in routing]
    total = (
        3 * (d[0] + d[3] + d[6])
        + 7 * (d[1] + d[4] + d[7])
        + (d[2] + d[5] + d[8])
    )
    return total % 10 == 0


def _qrr_ok(reference: str) -> bool:
    """Swiss QR reference: 27 digits, recursive mod-10 check digit."""
    if len(reference) != 27 or not reference.isdigit():
        return False
    table = [0, 9, 4, 6, 8, 2, 7, 1, 3, 5]
    carry = 0
    for ch in reference[:-1]:
        carry = table[(carry + int(ch)) % 10]
    return (10 - carry) % 10 == int(reference[-1])


def _rf_ok(reference: str) -> bool:
    """ISO 11649 creditor reference: RF + 2 check digits + up to 21 chars."""
    compact = reference.replace(" ", "").upper()
    if not (5 <= len(compact) <= 25) or not compact.startswith("RF"):
        return False
    return _mod97_alpha(compact[4:] + compact[:4]) == 1


def _is_qr_iban(iban: str) -> bool:
    """A Swiss or Liechtenstein IBAN whose IID is in the QR range."""
    compact = iban.replace(" ", "")
    if compact[:2] not in ("CH", "LI") or len(compact) < 9:
        return False
    return 30000 <= int(compact[4:9]) <= 31999


def _text(row: dict[str, Any], *keys: str) -> str | None:
    """The first non-blank value among ``keys``, stripped, else ``None``."""
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


# --- the engine ----------------------------------------------------------------


class RailProfile(ValidationProfile):
    """Validate rows against one :class:`Rail`."""

    def __init__(self, rail: Rail) -> None:
        self.rail = rail
        self.name = rail.name

    def _flag(
        self,
        result: SchemeValidationResult,
        aspect: str,
        message: str,
        index: int,
        field_name: str | None = None,
        severity: str = "error",
    ) -> None:
        """Append one violation with the rail's rule-id prefix."""
        result.violations.append(
            SchemeViolation(
                rule=f"{self.rail.prefix}-{aspect}",
                message=message,
                index=index,
                field=field_name,
                severity=severity,
            )
        )

    def validate(self, data: list[dict[str, Any]]) -> SchemeValidationResult:
        """Validate payment rows against the rail's rulebook.

        Args:
            data: Loaded payment rows (the normalised internal form, or
                the projection of a corpus file).

        Returns:
            A :class:`SchemeValidationResult` listing every violation.
        """
        result = SchemeValidationResult(profile=self.name)
        for index, row in enumerate(data):
            self._check_row(row, index, result)
        return result

    def _check_row(
        self, row: dict[str, Any], index: int, result: SchemeValidationResult
    ) -> None:
        """Apply every configured rule to one row."""
        rail = self.rail
        direct_debit = (
            _text(row, "payment_method") == "DD" or "mandate_id" in row
        )
        side = "debtor" if direct_debit else "creditor"
        currency = _text(row, "payment_currency", "currency")
        if rail.currencies and currency not in rail.currencies:
            self._flag(
                result,
                "CCY",
                f"{rail.title} carries {'/'.join(rail.currencies)} only (got {currency})",
                index,
                "payment_currency",
            )
        elif (
            not rail.currencies
            and currency is not None
            and not re.fullmatch(r"[A-Z]{3}", currency)
        ):
            self._flag(
                result,
                "CCY",
                f"currency must be an ISO 4217 code (got {currency})",
                index,
                "payment_currency",
            )
        amount = _text(row, "payment_amount")
        if rail.max_amount is not None and amount is not None:
            try:
                over = Decimal(amount) > rail.max_amount
            except InvalidOperation:
                over = False
            if over:
                self._flag(
                    result,
                    "AMT",
                    f"{rail.title} items are capped at {rail.max_amount:,} {currency or ''}".rstrip()
                    + f" (got {amount})",
                    index,
                    "payment_amount",
                    rail.max_amount_severity,
                )
        service = _text(row, "service_level_code")
        if rail.service_levels and service not in rail.service_levels:
            self._flag(
                result,
                "SVCLVL",
                f"{rail.title} expects service level {'/'.join(rail.service_levels)} (got {service})",
                index,
                "service_level_code",
                "warning",
            )
        code = _text(row, "local_instrument_code")
        proprietary = _text(row, "local_instrument_proprietary")
        if rail.local_instruments is not None:
            if rail.local_instruments == () and (code or proprietary):
                self._flag(
                    result,
                    "LCLINSTRM",
                    f"{rail.title} carries no local instrument (got {code or proprietary})",
                    index,
                    "local_instrument_code",
                    rail.local_instrument_severity,
                )
            elif (
                code
                and rail.local_instruments
                and code not in rail.local_instruments
            ):
                self._flag(
                    result,
                    "LCLINSTRM",
                    f"local instrument {code} is not one of {', '.join(sorted(rail.local_instruments))}",
                    index,
                    "local_instrument_code",
                    rail.local_instrument_severity,
                )
        if (
            rail.local_instrument_proprietary
            and proprietary
            and proprietary not in rail.local_instrument_proprietary
        ):
            self._flag(
                result,
                "LCLINSTRM",
                f"local instrument {proprietary} is not one of {'/'.join(rail.local_instrument_proprietary)}",
                index,
                "local_instrument_proprietary",
                rail.local_instrument_severity,
            )
        agent_bic = _text(row, f"{side}_agent_BIC")
        member = _text(row, f"{side}_agent_member_id")
        clearing = _text(row, f"{side}_agent_clearing_system")
        if rail.bic_required and not agent_bic:
            self._flag(
                result,
                "BIC",
                f"{rail.title} requires the {side} agent BIC",
                index,
                f"{side}_agent_BIC",
            )
        if rail.both_bics_required:
            for party in ("debtor", "creditor"):
                if not _text(row, f"{party}_agent_BIC"):
                    self._flag(
                        result,
                        "BIC",
                        f"{rail.title} requires the {party} agent BIC",
                        index,
                        f"{party}_agent_BIC",
                    )
        if agent_bic and not validate_bic_safe(agent_bic):
            self._flag(
                result,
                "BIC",
                f"{side} agent BIC {agent_bic} is not well-formed",
                index,
                f"{side}_agent_BIC",
            )
        iban = _text(row, f"{side}_account_IBAN")
        other = _text(row, f"{side}_account_id")
        if rail.iban_countries:
            if not iban:
                self._flag(
                    result,
                    "IBAN",
                    f"{rail.title} requires a {'/'.join(rail.iban_countries)} IBAN for the {side}",
                    index,
                    f"{side}_account_IBAN",
                )
            elif iban[:2] not in rail.iban_countries or not validate_iban_safe(
                iban
            ):
                self._flag(
                    result,
                    "IBAN",
                    f"{side} IBAN {iban} is not a valid {'/'.join(rail.iban_countries)} IBAN",
                    index,
                    f"{side}_account_IBAN",
                )
        if rail.domestic is not None:
            shape = rail.domestic
            if iban:
                if not validate_iban_safe(iban):
                    self._flag(
                        result,
                        "IBAN",
                        f"{side} IBAN {iban} is not valid",
                        index,
                        f"{side}_account_IBAN",
                    )
            else:
                if clearing and clearing not in shape.clearing_systems:
                    self._flag(
                        result,
                        "MMBID",
                        f"clearing system {clearing} is not {'/'.join(shape.clearing_systems)}",
                        index,
                        f"{side}_agent_clearing_system",
                    )
                if member is None and not agent_bic:
                    self._flag(
                        result,
                        "MMBID",
                        f"{rail.title} needs the {side} agent's {shape.member_digits}-digit member id or a BIC",
                        index,
                        f"{side}_agent_member_id",
                    )
                elif member is not None and (
                    len(member) != shape.member_digits or not member.isdigit()
                ):
                    self._flag(
                        result,
                        "MMBID",
                        f"member id {member} must be {shape.member_digits} digits",
                        index,
                        f"{side}_agent_member_id",
                    )
                elif (
                    member is not None
                    and shape.member_check == "aba"
                    and not _aba_ok(member)
                ):
                    self._flag(
                        result,
                        "MMBID",
                        f"routing number {member} fails the ABA check digit",
                        index,
                        f"{side}_agent_member_id",
                    )
                low, high = shape.account_digits
                if other is None:
                    self._flag(
                        result,
                        "ACCT",
                        f"{rail.title} needs the {side} account number ({low}-{high} digits) or an IBAN",
                        index,
                        f"{side}_account_id",
                    )
                elif not other.isdigit() or not low <= len(other) <= high:
                    self._flag(
                        result,
                        "ACCT",
                        f"account number {other} must be {low}-{high} digits",
                        index,
                        f"{side}_account_id",
                    )
        e2e = _text(row, "end_to_end_id", "payment_id")
        if (
            rail.end_to_end_max is not None
            and e2e is not None
            and len(e2e) > rail.end_to_end_max
        ):
            self._flag(
                result,
                "REF",
                f"end-to-end id exceeds {rail.end_to_end_max} characters ({len(e2e)})",
                index,
                "end_to_end_id",
            )
        remittance = _text(row, "remittance_information")
        if (
            rail.remittance_max is not None
            and remittance is not None
            and len(remittance) > rail.remittance_max
        ):
            self._flag(
                result,
                "RMT",
                f"remittance exceeds {rail.remittance_max} characters ({len(remittance)})",
                index,
                "remittance_information",
                rail.remittance_severity,
            )
        purpose = _text(row, "purpose_code")
        if (
            rail.purpose
            and not purpose
            and not _text(row, "purpose_proprietary")
        ):
            self._flag(
                result,
                "PURP",
                f"{rail.title} expects a purpose code",
                index,
                "purpose_code",
                "error" if rail.purpose == "require" else "warning",
            )
        if purpose and not _purpose_known(purpose):
            self._flag(
                result,
                "PURP",
                f"purpose code {purpose} is not in the ISO external purpose list",
                index,
                "purpose_code",
            )
        regulatory = _text(
            row, "regulatory_reporting_code", "regulatory_reporting_info"
        )
        if rail.regulatory and not regulatory:
            self._flag(
                result,
                "RGLTRY",
                f"{rail.title} expects a regulatory reporting code",
                index,
                "regulatory_reporting_code",
                "error" if rail.regulatory == "require" else "warning",
            )
        if rail.regulatory_pattern is not None and regulatory:
            info = _text(row, "regulatory_reporting_info") or regulatory
            if not rail.regulatory_pattern.match(info) and not re.fullmatch(
                r"[A-Z]{3}", regulatory
            ):
                self._flag(
                    result,
                    "RGLTRY",
                    f"regulatory reporting {info} does not follow the required form",
                    index,
                    "regulatory_reporting_code",
                )
        bearer = _text(row, "charge_bearer")
        if rail.charge_bearers and bearer not in rail.charge_bearers:
            self._flag(
                result,
                "CHRGBR",
                f"{rail.title} expects charge bearer {'/'.join(rail.charge_bearers)} (got {bearer})",
                index,
                "charge_bearer",
                rail.charge_bearer_severity,
            )
        if rail.address_required:
            parties = (
                ("debtor", "creditor") if rail.both_bics_required else (side,)
            )
            for party in parties:
                if not (
                    _text(row, f"{party}_town")
                    and _text(row, f"{party}_country")
                ):
                    self._flag(
                        result,
                        "ADDR",
                        f"{rail.title} requires the {party} address with town and country (structured or hybrid)",
                        index,
                        f"{party}_town",
                        rail.address_severity,
                    )
        if rail.uetr_required and not _text(row, "uetr"):
            self._flag(
                result,
                "UETR",
                f"{rail.title} expects a UETR on every transaction",
                index,
                "uetr",
                "warning",
            )
        if rail.sequence_types:
            sequence = _text(row, "sequence_type")
            if sequence not in rail.sequence_types:
                self._flag(
                    result,
                    "SEQTP",
                    f"sequence type must be one of {'/'.join(rail.sequence_types)} (got {sequence})",
                    index,
                    "sequence_type",
                )
        if rail.mandate_max is not None:
            mandate = _text(row, "mandate_id")
            if not mandate:
                self._flag(
                    result,
                    "MNDT",
                    "mandate id is required",
                    index,
                    "mandate_id",
                )
            elif len(mandate) > rail.mandate_max:
                self._flag(
                    result,
                    "MNDT",
                    f"mandate id exceeds {rail.mandate_max} characters",
                    index,
                    "mandate_id",
                )
        if rail.creditor_id_pattern is not None:
            creditor_id = _text(row, "creditor_id")
            if not creditor_id or not rail.creditor_id_pattern.fullmatch(
                creditor_id
            ):
                self._flag(
                    result,
                    "CDTRID",
                    f"creditor identifier {creditor_id or '(missing)'} does not match {rail.creditor_id_pattern.pattern}",
                    index,
                    "creditor_id",
                )
        if rail.creditor_reference:
            self._check_creditor_reference(row, index, result, iban)
        if rail.batch_booking is not None:
            booking = _text(row, "batch_booking")
            if booking is not None and booking != rail.batch_booking:
                self._flag(
                    result,
                    "BATCH",
                    f"{rail.title} is normally batch-booked {rail.batch_booking} (got {booking})",
                    index,
                    "batch_booking",
                    "warning",
                )

    def _check_creditor_reference(
        self,
        row: dict[str, Any],
        index: int,
        result: SchemeValidationResult,
        iban: str | None,
    ) -> None:
        """Swiss QRR/SCOR pairing, or Swedish OCR length."""
        reference = _text(row, "creditor_reference")
        kind = _text(row, "creditor_reference_type")
        if reference is None:
            return
        if self.rail.creditor_reference == "ch":
            if kind == "QRR":
                if not _qrr_ok(reference):
                    self._flag(
                        result,
                        "CDTRREF",
                        f"QRR reference {reference} is not 27 digits with a valid mod-10 check",
                        index,
                        "creditor_reference",
                    )
                if iban and not _is_qr_iban(iban):
                    self._flag(
                        result,
                        "CDTRREF",
                        "a QRR reference requires a QR-IBAN (IID 30000-31999)",
                        index,
                        "creditor_account_IBAN",
                    )
            elif kind == "SCOR":
                if not _rf_ok(reference):
                    self._flag(
                        result,
                        "CDTRREF",
                        f"SCOR reference {reference} is not a valid ISO 11649 RF reference",
                        index,
                        "creditor_reference",
                    )
                if iban and _is_qr_iban(iban):
                    self._flag(
                        result,
                        "CDTRREF",
                        "a QR-IBAN takes a QRR reference, not SCOR",
                        index,
                        "creditor_account_IBAN",
                    )
            else:
                self._flag(
                    result,
                    "CDTRREF",
                    f"Swiss structured references are QRR or SCOR (got {kind})",
                    index,
                    "creditor_reference_type",
                )
        else:  # "ocr"
            if (
                not reference.isdigit()
                or not 2 <= len(reference) <= 25
                or not _luhn_ok(reference)
            ):
                self._flag(
                    result,
                    "CDTRREF",
                    f"OCR reference {reference} must be 2-25 digits with a valid check digit",
                    index,
                    "creditor_reference",
                )


def _purpose_known(code: str) -> bool:
    """True when ``code`` is in the vendored ISO external purpose list."""
    from pain001.corpus.rules.external_codes import is_valid  # noqa: PLC0415

    return is_valid("ExternalPurpose1Code", code)


class PurposeMandate(ValidationProfile):
    """A country's purpose-code mandate, as its own profile.

    Args:
        country: ISO 3166 alpha-2 code.
        title: Human title.
        where: ``purpose`` (Purp/Cd or Prtry) or ``regulatory``
            (RgltryRptg/Dtls), where the country expects the code.
        pattern: Regex the code must match, if the country prescribes one.
        currency: Only when the payment currency is this (HK RMB).
        sources: The public documents the mandate comes from.
    """

    def __init__(
        self,
        country: str,
        title: str,
        where: str,
        pattern: str | None = None,
        currency: str | None = None,
        sources: tuple[str, ...] = (),
    ) -> None:
        self.country = country
        self.title = title
        self.where = where
        self.pattern = re.compile(pattern) if pattern else None
        self.currency = currency
        self.sources = sources
        self.name = f"purpose-mandate-{country.lower()}"

    def validate(self, data: list[dict[str, Any]]) -> SchemeValidationResult:
        """Validate payment rows against the country's purpose mandate.

        Args:
            data: Loaded payment rows.

        Returns:
            A :class:`SchemeValidationResult` listing every violation.
        """
        result = SchemeValidationResult(profile=self.name)
        rule = f"PURP-{self.country}"
        for index, row in enumerate(data):
            if (
                self.currency
                and _text(row, "payment_currency", "currency") != self.currency
            ):
                continue
            if self.where == "regulatory":
                code = _text(
                    row,
                    "regulatory_reporting_code",
                    "regulatory_reporting_info",
                )
                field_name = "regulatory_reporting_code"
            else:
                code = _text(row, "purpose_code", "purpose_proprietary")
                field_name = "purpose_code"
            if not code:
                result.violations.append(
                    SchemeViolation(
                        rule,
                        f"{self.title}: a purpose code is mandatory",
                        index,
                        field_name,
                    )
                )
            elif self.pattern is not None and not self.pattern.fullmatch(code):
                result.violations.append(
                    SchemeViolation(
                        rule,
                        f"{self.title}: purpose code {code} does not match {self.pattern.pattern}",
                        index,
                        field_name,
                    )
                )
            elif (
                self.where == "purpose"
                and _text(row, "purpose_code")
                and not _purpose_known(str(_text(row, "purpose_code")))
            ):
                result.violations.append(
                    SchemeViolation(
                        rule,
                        f"{self.title}: purpose code {code} is not in the ISO external purpose list",
                        index,
                        field_name,
                    )
                )
        return result


# --- the rails -----------------------------------------------------------------

_SEPA_COUNTRIES: tuple[str, ...] = (
    "AD", "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GB", "GI", "GR", "HR", "HU", "IE", "IS", "IT", "LI", "LT", "LU",
    "LV", "MC", "MT", "NL", "NO", "PL", "PT", "RO", "SE", "SI", "SK", "SM",
    "VA",
)  # fmt: skip
GB_DOMESTIC = Domestic(("GBDSC",), 6, (8, 8))
US_DOMESTIC = Domestic(("USABA",), 9, (4, 17), member_check="aba")
HK_DOMESTIC = Domestic(("HKNCC",), 3, (6, 12))
SG_DOMESTIC = Domestic(("SGIBG",), 7, (6, 14))

RAILS: tuple[Rail, ...] = (
    Rail(
        "uk-bacs",
        "UK Bacs Direct Credit",
        "UK-BACS",
        ("pain.001",),
        (
            "Bacs ISO 20022 / Standard 18 translation guide v1.1",
            "Bacs service description: originator name and reference lengths",
        ),
        currencies=("GBP",),
        service_levels=("NURG",),
        local_instruments=(),
        domestic=GB_DOMESTIC,
        end_to_end_max=18,
        remittance_max=18,
    ),
    Rail(
        "uk-fps",
        "UK Faster Payments",
        "UK-FPS",
        ("pain.001",),
        (
            "Pay.UK Faster Payments scheme limits",
            "Pay.UK Faster Payments ISO 20022 usage: service levels URGP and URNS both in use by UK channels",
        ),
        currencies=("GBP",),
        max_amount=Decimal("1000000.00"),
        service_levels=("URGP", "URNS"),
        domestic=GB_DOMESTIC,
        end_to_end_max=18,
    ),
    Rail(
        "uk-chaps",
        "UK CHAPS",
        "UK-CHAPS",
        ("pain.001",),
        (
            "Bank of England: ISO 20022 enhanced data in CHAPS (purpose codes from 1 May 2025, structured or hybrid addresses)",
            "NatWest Bankline XML import guide (Jan 2025)",
        ),
        currencies=("GBP",),
        service_levels=("SDVA",),
        domestic=GB_DOMESTIC,
        end_to_end_max=35,
        purpose="warn",
        address_required=True,
    ),
    Rail(
        "uk-bacs-dd",
        "UK Bacs Direct Debit",
        "UK-BACSDD",
        ("pain.008",),
        (
            "Bacs AUDDIS service guide",
            "Bacs ISO 20022 translation guide v1.1 (sequence-type to transaction-code mapping is an assumption)",
        ),
        currencies=("GBP",),
        local_instrument_proprietary=tuple(sorted(BACS_DD_CODES)),
        domestic=GB_DOMESTIC,
        sequence_types=("FRST", "RCUR", "FNAL", "OOFF"),
        mandate_max=18,
        creditor_id_pattern=re.compile(r"[0-9]{6}"),
    ),
    Rail(
        "de-ccu",
        "Germany urgent euro (DK CCU)",
        "DE-CCU",
        ("pain.001",),
        (
            "DK DFÜ-Abkommen Anlage 3 V26.11, order type CCU",
            "DZ BANK CCU product description",
        ),
        currencies=("EUR",),
        service_levels=("URGP",),
        bic_required=True,
        iban_countries=_SEPA_COUNTRIES,
        charge_bearers=("SHAR",),
    ),
    Rail(
        "de-axz",
        "Germany foreign payment (DK AXZ)",
        "DE-AXZ",
        ("pain.001",),
        (
            "DK DFÜ-Abkommen Anlage 3 V3.8, order type AXZ",
            "DZ BANK AXZ product description (regulatory reporting for AWV)",
        ),
        bic_required=True,
        charge_bearers=("DEBT", "CRED", "SHAR"),
        regulatory="warn",
    ),
    Rail(
        "ch-domestic",
        "Switzerland domestic (SPS type D)",
        "CH-DOM",
        ("pain.001",),
        (
            "SIX Swiss Payment Standards, IG Credit Transfer SPS 2025 v2.2 and SPS 2026 v2.3",
            "SIX Business Rules 3.2",
        ),
        currencies=("CHF", "EUR"),
        iban_countries=("CH", "LI"),
        creditor_reference="ch",
    ),
    Rail(
        "ch-sepa",
        "Switzerland SEPA (SPS type S)",
        "CH-SEPA",
        ("pain.001",),
        ("SIX Swiss Payment Standards, IG Credit Transfer, payment type S",),
        currencies=("EUR",),
        service_levels=("SEPA",),
        charge_bearers=("SLEV",),
        iban_countries=_SEPA_COUNTRIES,
    ),
    Rail(
        "se-bankgiro",
        "Sweden Bankgiro",
        "SE-BG",
        ("pain.001",),
        (
            "Nordea pain.001 examples v2.6 (Jun 2026)",
            "Swedbank MIG 2.0",
            "Bankgirot OCR reference rules",
        ),
        currencies=("SEK",),
        service_levels=("NURG",),
        creditor_reference="ocr",
        batch_booking="true",
    ),
    Rail(
        "us-ach",
        "US ACH",
        "US-ACH",
        ("pain.001", "pain.008"),
        (
            "Nacha Operating Rules (Standard Entry Class codes)",
            "Huntington pain.001 developer documentation",
            "Cross River pain.001.001.03 input specification",
        ),
        currencies=("USD",),
        service_levels=("NURG", "SDVA"),
        local_instruments=tuple(sorted(SEC_CODES)),
        local_instrument_severity="error",
        domestic=US_DOMESTIC,
        remittance_max=80,
    ),
    Rail(
        "us-wire",
        "US Fedwire",
        "US-WIRE",
        ("pain.001",),
        (
            "Federal Reserve Fedwire Funds Service ISO 20022 quick reference",
            "Citi ISO 20022 FAQs (Feb 2026)",
        ),
        currencies=("USD",),
        service_levels=("URGP",),
        local_instruments=(),
        domestic=US_DOMESTIC,
        charge_bearers=("DEBT", "SHAR"),
        charge_bearer_severity="warning",
        address_required=True,
    ),
    Rail(
        "us-rtp",
        "US RTP and FedNow",
        "US-RTP",
        ("pain.001",),
        (
            "The Clearing House RTP network (per-item limit)",
            "Cross River RTP input specification",
        ),
        currencies=("USD",),
        max_amount=Decimal("10000000.00"),
        service_levels=("URNS",),
        domestic=US_DOMESTIC,
    ),
    Rail(
        "hk-fps",
        "Hong Kong FPS",
        "HK-FPS",
        ("pain.001",),
        (
            "HKICL Faster Payment System rules and clearing-code list",
            "East West Bank HK ISO 20022 FPS file specification",
        ),
        currencies=("HKD", "CNY"),
        max_amount=Decimal("1000000.00"),
        max_amount_severity="warning",
        service_levels=("URGP",),
        domestic=HK_DOMESTIC,
    ),
    Rail(
        "sg-fast",
        "Singapore FAST",
        "SG-FAST",
        ("pain.001",),
        (
            "Association of Banks in Singapore, FAST (S$200,000 per transaction)",
            "UOB, OCBC and DBS ISO 20022 pages",
        ),
        currencies=("SGD",),
        max_amount=Decimal("200000.00"),
        service_levels=("URGP", "NURG"),
        domestic=SG_DOMESTIC,
        address_required=True,
        address_severity="warning",
    ),
    Rail(
        "my-duitnow",
        "Malaysia DuitNow",
        "MY-DUITNOW",
        ("pain.001",),
        (
            "PayNet DuitNow developer documentation",
            "BNM purpose-code lists as published by Deutsche Bank, HSBC and CIMB Malaysia",
        ),
        currencies=("MYR",),
        max_amount=Decimal("10000000.00"),
        max_amount_severity="warning",
        bic_required=True,
        purpose="warn",
    ),
    Rail(
        "qa-qatch",
        "Qatar QATCH credit",
        "QA-QATCH",
        ("pain.001",),
        (
            "Qatar Central Bank retail payment pages",
            "ClearingPost QA-RTGS guide",
            "HSBC Qatar purpose-of-payment page",
        ),
        currencies=("QAR",),
        max_amount=Decimal("250000.00"),
        iban_countries=("QA",),
        bic_required=True,
        purpose="require",
    ),
    Rail(
        "ae-uaefts",
        "UAE UAEFTS",
        "AE-UAEFTS",
        ("pain.001",),
        (
            "CBUAE technical notes on transaction codes for balance-of-payments reporting (AUX700)",
            "HSBC UAE purpose-of-payment notes",
        ),
        currencies=("AED",),
        iban_countries=("AE",),
        regulatory="require",
        regulatory_pattern=UAE_REGULATORY,
    ),
    Rail(
        "cbpr-cross-border",
        "Swift CBPR+ cross-border",
        "CBPR",
        ("pain.001",),
        (
            "Swift CBPR+ usage guidelines SR2025 (pain.001.001.09)",
            "CGI-MP pain.001 V09 implementation guide",
        ),
        both_bics_required=True,
        address_required=True,
        uetr_required=True,
        charge_bearers=("DEBT", "CRED", "SHAR"),
    ),
)

PURPOSE_MANDATES: tuple[PurposeMandate, ...] = (
    PurposeMandate(
        "AE",
        "UAE CBUAE purpose of payment",
        "regulatory",
        r"(/(BENEFRES|ORDERRES)/AE//)?[A-Z]{3}",
        sources=("CBUAE technical notes on transaction codes (AUX700)",),
    ),
    PurposeMandate(
        "QA",
        "Qatar QCB purpose of payment",
        "purpose",
        sources=("QCB retail payment pages",),
    ),
    PurposeMandate(
        "MY",
        "Malaysia BNM purpose code",
        "purpose",
        sources=("BNM purpose-code lists",),
    ),
    PurposeMandate(
        "GB",
        "UK CHAPS purpose code",
        "purpose",
        sources=("Bank of England ISO 20022 enhanced data in CHAPS",),
    ),
    PurposeMandate(
        "HK",
        "Hong Kong RMB cross-border purpose code",
        "regulatory",
        currency="CNY",
        sources=(
            "HSBC HK RMB purpose-code notices",
            "Bank of America RMB quick guide",
        ),
    ),
)

RAIL_PROFILES: dict[str, ValidationProfile] = {
    **{rail.name: RailProfile(rail) for rail in RAILS},
    **{mandate.name: mandate for mandate in PURPOSE_MANDATES},
}
DESCRIPTIONS: dict[str, str] = {
    **{
        rail.name: f"{rail.title} rulebook ({rail.sources[0]})."
        for rail in RAILS
    },
    **{
        m.name: f"{m.title}: a purpose code is mandatory."
        for m in PURPOSE_MANDATES
    },
}
_ASPECT_HINTS: dict[str, str] = {
    "CCY": "Use the rail's currency.",
    "AMT": "Split the item or use a rail with a higher ceiling.",
    "SVCLVL": "Set PmtTpInf/SvcLvl/Cd to the rail's service level.",
    "LCLINSTRM": "Use the rail's local instrument, or omit it.",
    "BIC": "Supply a well-formed BIC for the agent.",
    "IBAN": "Supply a valid IBAN of the rail's country.",
    "MMBID": "Supply the domestic clearing member id (sort code, routing number, bank code).",
    "ACCT": "Supply the domestic account number in the rail's shape.",
    "REF": "Shorten the end-to-end id.",
    "RMT": "Shorten the remittance text.",
    "PURP": "Add a purpose code from the ISO external purpose list.",
    "RGLTRY": "Add the regulatory reporting code the central bank prescribes.",
    "CHRGBR": "Set ChrgBr to a value the rail accepts.",
    "ADDR": "Give the party a structured or hybrid address with town and country.",
    "UETR": "Add a UETR (v4 UUID) in PmtId/UETR; pain.001.001.09 or later.",
    "SEQTP": "Use a sequence type the scheme accepts.",
    "MNDT": "Supply the mandate id within the scheme's length.",
    "CDTRID": "Supply the creditor identifier in the scheme's format.",
    "CDTRREF": "Pair the reference type with the account and check digits the scheme requires.",
    "BATCH": "Set BtchBookg as the rail expects.",
}
for _rail in RAILS:
    for _aspect, _hint in _ASPECT_HINTS.items():
        REMEDIATIONS.setdefault(
            f"{_rail.prefix}-{_aspect}", f"{_hint} Source: {_rail.sources[0]}."
        )
for _mandate in PURPOSE_MANDATES:
    REMEDIATIONS.setdefault(
        f"PURP-{_mandate.country}",
        f"{_mandate.title}: add the code. Source: {_mandate.sources[0]}.",
    )
PROFILES.update(RAIL_PROFILES)


def rail(name: str) -> Rail:
    """The :class:`Rail` behind a profile name.

    Args:
        name: A rail profile id such as ``uk-fps``.

    Returns:
        The rail.

    Raises:
        KeyError: If the name is not a rail.
    """
    for candidate in RAILS:
        if candidate.name == name:
            return candidate
    raise KeyError(name)


__all__ = [
    "BACS_DD_CODES",
    "DESCRIPTIONS",
    "PURPOSE_MANDATES",
    "RAILS",
    "RAIL_PROFILES",
    "SEC_CODES",
    "Domestic",
    "PurposeMandate",
    "Rail",
    "RailProfile",
    "rail",
]
