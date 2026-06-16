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

"""Scheme-aware validation: SEPA Credit Transfer, Direct Debit, charset.

XSD validation proves a file is well-formed; scheme validation proves the
payment obeys the rulebook of the scheme it will clear through. This shows
the ``sepa-sct`` and ``sepa-sdd`` profiles, structured violations with
remediation hints, and the ISO 20022 character-set guard.

Run from the repository root::

    python examples/06_scheme_validation.py
"""

from pain001 import sanitize_to_charset, validate_scheme

COMPLIANT_SCT = {
    "payment_currency": "EUR",
    "debtor_account_IBAN": "DE89370400440532013000",
    "creditor_account_IBAN": "FR1420041010050500013M02606",
    "creditor_agent_BIC": "DEUTDEFF",
    "service_level_code": "SEPA",
    "payment_amount": "100.00",
    "debtor_name": "John Doe",
    "creditor_name": "Acme Corp",
}


def main() -> None:
    """Validate compliant and non-compliant rows against SEPA profiles."""
    # A compliant Credit Transfer passes.
    ok = validate_scheme([COMPLIANT_SCT], profile="sepa-sct")
    assert ok.is_valid
    print("SEPA SCT (compliant): valid")

    # A USD payment breaks the EUR rule; violations are structured.
    bad = COMPLIANT_SCT | {"payment_currency": "USD"}
    result = validate_scheme([bad], profile="sepa-sct")
    assert not result.is_valid
    print("SEPA SCT (USD): invalid")
    for violation in result.violations:
        print(f"  [{violation.rule}] {violation.message}")
        print(f"    fix: {violation.remediation}")

    # Direct Debit adds mandate and sequence-type rules.
    sdd_row = COMPLIANT_SCT | {"mandate_id": "", "sequence_type": "RCUR"}
    sdd = validate_scheme([sdd_row], profile="sepa-sdd")
    assert any(v.rule == "SDD-MNDT" for v in sdd.violations)
    print("SEPA SDD (no mandate): flagged SDD-MNDT")

    # The charset guard transliterates accented text to the ISO 20022 set.
    cleaned = sanitize_to_charset("Café Zürich & Co")
    print(f"Charset: 'Café Zürich & Co' -> '{cleaned}'")
    assert cleaned == "Cafe Zurich   Co"

    print("Scheme validation example completed.")


if __name__ == "__main__":
    main()
