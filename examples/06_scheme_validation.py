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

"""Scheme-aware validation: every bundled profile, end-to-end.

XSD validation proves a file is well-formed; scheme validation proves
the payment obeys the rulebook of the scheme it will clear through.
Six profiles ship today, all exercised here:

* ``sepa-sct``    - SEPA Credit Transfer (EUR-only, SEPA service level)
* ``sepa-sdd``    - SEPA Direct Debit (mandate + sequence-type rules)
* ``sepa-inst``   - SEPA Instant Credit Transfer (100,000 EUR cap)
* ``sepa-b2b``    - SEPA Business-to-Business Direct Debit
                    (FRST/RCUR sequence only, mandatory creditor id)
* ``xborder-ct``  - Generic cross-border Credit Transfer
                    (multi-currency, BIC mandatory)
* ``anti-duplicate`` - Cross-record duplicate detection (same creditor
                    IBAN, amount and execution date in one batch);
                    composes with any of the above

Plus the ISO 20022 charset guard (``sanitize_to_charset``), and the
**rail profiles** that joined the same registry in 0.0.67 (``uk-chaps``,
``us-ach``, ``ch-domestic``, ``se-bankgiro`` and more, plus the country
purpose mandates), shown on rows projected from a shipped corpus file.

Run from the repository root::

    python examples/06_scheme_validation.py
"""

from pain001 import sanitize_to_charset, validate_scheme
from pain001.corpus import get_file
from pain001.corpus.rules.projection import rows_from_xml
from pain001.validation.schemes import PROFILES

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


def _sepa_sct() -> None:
    """Profile 1/5: SEPA Credit Transfer."""
    ok = validate_scheme([COMPLIANT_SCT], profile="sepa-sct")
    assert ok.is_valid
    print("SEPA SCT (compliant): valid")
    bad = COMPLIANT_SCT | {"payment_currency": "USD"}
    result = validate_scheme([bad], profile="sepa-sct")
    assert not result.is_valid
    print("SEPA SCT (USD): invalid")
    for violation in result.violations:
        print(f"  [{violation.rule}] {violation.message}")
        print(f"    fix: {violation.remediation}")


def _sepa_sdd() -> None:
    """Profile 2/5: SEPA Direct Debit (consumer)."""
    sdd_row = COMPLIANT_SCT | {"mandate_id": "", "sequence_type": "RCUR"}
    sdd = validate_scheme([sdd_row], profile="sepa-sdd")
    assert any(v.rule == "SDD-MNDT" for v in sdd.violations)
    print("SEPA SDD (no mandate): flagged SDD-MNDT")


def _sepa_inst() -> None:
    """Profile 3/5: SEPA Instant Credit Transfer (100,000 EUR cap)."""
    big_row = COMPLIANT_SCT | {"payment_amount": "150000.00"}
    inst = validate_scheme([big_row], profile="sepa-inst")
    assert any(
        v.rule.startswith("INST-AMOUNT") or "100000" in v.message
        for v in inst.violations
    )
    print("SEPA INST (150k EUR): flagged amount-cap violation")


def _sepa_b2b() -> None:
    """Profile 4/5: SEPA Business-to-Business Direct Debit (v0.0.53 NEW).

    B2B is stricter than the consumer SDD profile: only FRST and RCUR
    sequence types are allowed (no OOFF / FNAL), and a creditor
    identifier is mandatory.
    """
    # Missing creditor_id triggers B2B-CDTR-ID.
    b2b_row = COMPLIANT_SCT | {
        "mandate_id": "MND-001",
        "sequence_type": "RCUR",
        "service_level_code": "B2B",
    }
    b2b = validate_scheme([b2b_row], profile="sepa-b2b")
    assert any(v.rule == "B2B-CDTR-ID" for v in b2b.violations)
    print("SEPA B2B (no creditor_id): flagged B2B-CDTR-ID")
    # OOFF sequence type is forbidden in B2B -> B2B-SEQTP.
    bad_seq = b2b_row | {
        "creditor_id": "DE98ZZZ09999999999",
        "sequence_type": "OOFF",
    }
    b2b2 = validate_scheme([bad_seq], profile="sepa-b2b")
    assert any(v.rule == "B2B-SEQTP" for v in b2b2.violations)
    print("SEPA B2B (sequence_type=OOFF): flagged B2B-SEQTP")


def _xborder_ct() -> None:
    """Profile 5/6: generic cross-border Credit Transfer (BIC mandatory)."""
    # Missing BIC trips the BIC-MANDATORY rule even for non-EUR currencies.
    cross_row = COMPLIANT_SCT | {
        "payment_currency": "USD",
        "creditor_agent_BIC": "",
    }
    cross = validate_scheme([cross_row], profile="xborder-ct")
    assert not cross.is_valid
    print(f"XBORDER CT (USD, no BIC): flagged {cross.violations[0].rule}")


def _charset_guard() -> None:
    """ISO 20022 character-set guard transliterates accented text."""
    cleaned = sanitize_to_charset("Cafe Zurich & Co".replace("e", "é"))
    # Original carries é (e+acute); the cleaner reduces to plain ASCII
    # and strips disallowed punctuation.
    assert "é" not in cleaned
    print(f"Charset guard: cleaned text = {cleaned!r}")


def _profile_registry() -> None:
    """The six scheme profiles plus the rail profiles, all advertised."""
    names = sorted(PROFILES)
    schemes = [
        "anti-duplicate",
        "sepa-b2b",
        "sepa-inst",
        "sepa-sct",
        "sepa-sdd",
        "xborder-ct",
    ]
    assert all(name in names for name in schemes)
    rails = [n for n in names if n not in schemes]
    assert "uk-chaps" in rails and "purpose-mandate-gb" in rails
    print(f"PROFILES registry: {len(schemes)} schemes + {len(rails)} rails")


def _rail_profiles() -> None:
    """Rail profiles: national rules on a file projected to flat rows.

    ``rows_from_xml`` reads a built document into the same flat rows a
    CSV gives the validator, so a rail profile judges both alike. The
    shipped CHAPS file passes ``uk-chaps`` and the UK purpose mandate; a
    Swiss QR reference with a broken check digit is caught by
    ``ch-domestic``.
    """
    rows = rows_from_xml(
        get_file("gb.chaps.property-purchase", "pain.001.001.09")
    )
    chaps = validate_scheme(rows, profile="uk-chaps,purpose-mandate-gb")
    assert chaps.is_valid
    print(f"RAIL uk-chaps + purpose-mandate-gb: valid ({len(rows)} row(s))")
    swiss = rows_from_xml(get_file("ch.sps.qr-bill", "pain.001.001.09"))
    assert validate_scheme(swiss, profile="ch-domestic").is_valid
    broken = [
        row | {"creditor_reference": "210000000003139471430009018"}
        for row in swiss
    ]
    bad = validate_scheme(broken, profile="ch-domestic")
    assert any(v.rule.endswith("CDTRREF") for v in bad.violations)
    print("RAIL ch-domestic (bad QRR check digit): flagged CDTRREF")


def _anti_duplicate() -> None:
    """Profile 6/6: the same payment keyed in twice, caught before the bank."""
    keyed_twice = [
        COMPLIANT_SCT | {"requested_execution_date": "2026-09-12"},
        COMPLIANT_SCT | {"requested_execution_date": "2026-09-12"},
        # One cent apart is a different payment: exact-key matching only.
        COMPLIANT_SCT
        | {
            "requested_execution_date": "2026-09-12",
            "payment_amount": "100.01",
        },
    ]
    dupes = validate_scheme(keyed_twice, profile="anti-duplicate")
    assert not dupes.is_valid
    assert [v.index for v in dupes.violations] == [0, 1]
    print(f"ANTI-DUPLICATE: rows 0 and 1 flagged {dupes.violations[0].rule}")

    # Compose with an intra-record rulebook: one call, the union of findings.
    both = validate_scheme(keyed_twice, profile="sepa-sct,anti-duplicate")
    assert both.profile == "sepa-sct,anti-duplicate"
    print(f"COMPOSED ({both.profile}): {len(both.violations)} violation(s)")


def main() -> None:
    """Run every scheme + the charset guard back-to-back."""
    _profile_registry()
    _sepa_sct()
    _sepa_sdd()
    _sepa_inst()
    _sepa_b2b()
    _xborder_ct()
    _anti_duplicate()
    _rail_profiles()
    _charset_guard()
    print("Scheme validation example completed.")


if __name__ == "__main__":
    main()
