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

"""Tests for scheme-rulebook validation (SEPA Credit Transfer)."""

import pytest

from pain001.validation.schemes import (
    PROFILES,
    SchemeValidationResult,
    SepaCreditTransferProfile,
    SepaDirectDebitProfile,
    remediation_for,
    validate_scheme,
)


def _valid_sdd_row() -> dict[str, object]:
    """Return a payment row that is fully SEPA SDD compliant."""
    return _valid_row() | {
        "mandate_id": "MNDT-0001",
        "sequence_type": "RCUR",
    }


def _valid_row() -> dict[str, object]:
    """Return a payment row that is fully SEPA SCT compliant."""
    return {
        "payment_currency": "EUR",
        "debtor_account_IBAN": "DE89370400440532013000",
        "creditor_account_IBAN": "FR1420041010050500013M02606",
        "creditor_agent_BIC": "DEUTDEFF",
        "service_level_code": "SEPA",
        "payment_amount": "100.00",
        "debtor_name": "John Doe",
        "creditor_name": "Acme Corp",
        "remittance_information": "Invoice 12345",
    }


class TestSepaCreditTransferProfile:
    """Rule-by-rule tests for the SEPA SCT profile."""

    def test_valid_row_passes(self) -> None:
        """A compliant row produces no violations."""
        result = validate_scheme([_valid_row()])
        assert result.is_valid
        assert result.violations == []
        assert bool(result) is True

    def test_non_eur_currency_flagged(self) -> None:
        """A non-EUR currency raises SEPA-CCY."""
        row = _valid_row() | {"payment_currency": "USD"}
        result = validate_scheme([row])
        assert not result.is_valid
        assert any(v.rule == "SEPA-CCY" for v in result.violations)

    def test_invalid_ibans_flagged(self) -> None:
        """Bad debtor and creditor IBANs raise their rules."""
        row = _valid_row() | {
            "debtor_account_IBAN": "NOTANIBAN",
            "creditor_account_IBAN": "",
        }
        rules = {v.rule for v in validate_scheme([row]).violations}
        assert "SEPA-DBTR-IBAN" in rules
        assert "SEPA-CDTR-IBAN" in rules

    def test_invalid_bic_flagged(self) -> None:
        """A malformed BIC raises SEPA-BIC."""
        row = _valid_row() | {"creditor_agent_BIC": "BADBIC"}
        assert any(
            v.rule == "SEPA-BIC" for v in validate_scheme([row]).violations
        )

    def test_missing_bic_is_allowed(self) -> None:
        """BIC is optional under SEPA (IBAN-only)."""
        row = _valid_row() | {"creditor_agent_BIC": ""}
        assert validate_scheme([row]).is_valid

    def test_non_sepa_service_level_is_warning(self) -> None:
        """A non-SEPA service level warns but stays valid."""
        row = _valid_row() | {"service_level_code": "URGP"}
        result = validate_scheme([row])
        assert result.is_valid  # warning only
        assert any(
            v.rule == "SEPA-SVCLVL" and v.severity == "warning"
            for v in result.violations
        )

    def test_amount_over_ceiling_flagged(self) -> None:
        """An amount above the SEPA ceiling raises SEPA-AMT."""
        row = _valid_row() | {"payment_amount": "1000000000.00"}
        assert any(
            v.rule == "SEPA-AMT" for v in validate_scheme([row]).violations
        )

    def test_amount_too_many_decimals_flagged(self) -> None:
        """More than two decimal places raises SEPA-AMT."""
        row = _valid_row() | {"payment_amount": "100.001"}
        assert any(
            v.rule == "SEPA-AMT" for v in validate_scheme([row]).violations
        )

    def test_non_numeric_amount_flagged(self) -> None:
        """A non-numeric amount raises SEPA-AMT."""
        row = _valid_row() | {"payment_amount": "abc"}
        assert any(
            v.rule == "SEPA-AMT" for v in validate_scheme([row]).violations
        )

    def test_charset_violation_flagged(self) -> None:
        """Disallowed characters in a name raise SEPA-CHARSET."""
        row = _valid_row() | {"creditor_name": "Café & Co"}
        violation = next(
            v
            for v in validate_scheme([row]).violations
            if v.rule == "SEPA-CHARSET"
        )
        assert violation.field == "creditor_name"
        assert violation.index == 0

    def test_overlong_field_flagged(self) -> None:
        """A name beyond 70 characters raises SEPA-LEN."""
        row = _valid_row() | {"creditor_name": "A" * 71}
        assert any(
            v.rule == "SEPA-LEN" for v in validate_scheme([row]).violations
        )

    def test_violation_carries_row_index(self) -> None:
        """Violations are addressable to the offending row."""
        rows = [_valid_row(), _valid_row() | {"payment_currency": "GBP"}]
        result = validate_scheme(rows)
        ccy = next(v for v in result.violations if v.rule == "SEPA-CCY")
        assert ccy.index == 1


class TestSepaDirectDebitProfile:
    """Tests for the SEPA SDD profile (shared rules + SDD specifics)."""

    def test_valid_sdd_row_passes(self) -> None:
        """A compliant direct-debit row produces no violations."""
        result = validate_scheme([_valid_sdd_row()], profile="sepa-sdd")
        assert result.is_valid
        assert result.violations == []

    def test_missing_mandate_flagged(self) -> None:
        """A missing mandate id raises SDD-MNDT."""
        row = _valid_sdd_row() | {"mandate_id": ""}
        assert any(
            v.rule == "SDD-MNDT"
            for v in validate_scheme([row], profile="sepa-sdd").violations
        )

    def test_invalid_sequence_type_flagged(self) -> None:
        """An unknown sequence type raises SDD-SEQTP."""
        row = _valid_sdd_row() | {"sequence_type": "WEEKLY"}
        assert any(
            v.rule == "SDD-SEQTP"
            for v in validate_scheme([row], profile="sepa-sdd").violations
        )

    def test_shared_sepa_rules_apply(self) -> None:
        """Shared SEPA rules (e.g. currency) also fire for SDD."""
        row = _valid_sdd_row() | {"payment_currency": "USD"}
        assert any(
            v.rule == "SEPA-CCY"
            for v in validate_scheme([row], profile="sepa-sdd").violations
        )


class TestRemediations:
    """Tests for the remediation catalogue."""

    def test_violation_exposes_remediation(self) -> None:
        """Each violation carries a non-empty remediation hint."""
        row = _valid_row() | {"payment_currency": "USD"}
        violation = validate_scheme([row]).violations[0]
        assert violation.rule == "SEPA-CCY"
        assert "EUR" in violation.remediation

    def test_remediation_for_known_and_unknown(self) -> None:
        """remediation_for returns text for known, '' for unknown rules."""
        assert remediation_for("SDD-MNDT")
        assert remediation_for("NO-SUCH-RULE") == ""

    def test_violation_as_dict_is_json_ready(self) -> None:
        """as_dict exposes all fields including the remediation."""
        row = _valid_row() | {"payment_currency": "USD"}
        payload = validate_scheme([row]).violations[0].as_dict()
        assert payload["rule"] == "SEPA-CCY"
        assert set(payload) == {
            "rule",
            "message",
            "index",
            "field",
            "severity",
            "remediation",
        }


class TestProfileRegistry:
    """Tests for the profile registry and convenience function."""

    def test_registry_contains_both_profiles(self) -> None:
        """Both SEPA profiles are registered under their names."""
        assert isinstance(PROFILES["sepa-sct"], SepaCreditTransferProfile)
        assert isinstance(PROFILES["sepa-sdd"], SepaDirectDebitProfile)

    def test_unknown_profile_raises(self) -> None:
        """Requesting an unknown profile raises ValueError."""
        with pytest.raises(ValueError, match="Unknown scheme profile"):
            validate_scheme([_valid_row()], profile="nope")

    def test_result_is_dataclass(self) -> None:
        """validate_scheme returns a SchemeValidationResult."""
        result = validate_scheme([_valid_row()])
        assert isinstance(result, SchemeValidationResult)
        assert result.profile == "sepa-sct"

    def test_top_level_import(self) -> None:
        """validate_scheme is exposed at the package top level."""
        from pain001 import validate_scheme as top_level

        assert top_level([_valid_row()]).is_valid
