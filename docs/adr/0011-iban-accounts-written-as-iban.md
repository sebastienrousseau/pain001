<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0011. Write an IBAN account as `<IBAN>` in every pain.001 version

- **Status:** Accepted
- **Date:** 2026-11-08
- **Deciders:** Sebastien Rousseau (release 0.0.82)

## Context

The input columns `debtor_account_IBAN` and `creditor_account_IBAN` hold
IBANs. The pain.001.001.03 and .09 to .13 templates write them as
`<Id><IBAN>…</IBAN></Id>`. The .04 to .08 templates wrote the same value
as `<Id><Othr><Id>…</Id></Othr></Id>`, an account number with no scheme
name. A bank or a validator reading that cannot tell the value is an
IBAN: pain001's own SEPA checks (the `sepa-sct` profile's
`SEPA-DBTR-IBAN` and `SEPA-CDTR-IBAN`, Schematron EPC-PMT-001 and
EPC-SCT-003) found no IBAN in the bundled .05 to .08 samples, and a SEPA
bank may reject such a payment or repair it by hand.

## Options considered

1. Leave .04 to .08 as they are and document it. No output change, but
   five versions stay wrong and out of line with the other six.
2. Always write `<IBAN>` in .04 to .08. Simple, but a non-IBAN account
   number put in the column (possible with `--no-identifier-checks`)
   would then fail the XSD, which it passes today.
3. Write `<IBAN>` when the value is an IBAN and keep `<Othr><Id>`
   otherwise, the switch .03 and .09 already make.

## Decision

Option 3. The templates' sandbox gains an `iban` test
(`pain001.xml._jinja.is_iban`): true for text in the XSD's IBAN shape
(`[A-Z]{2}[0-9]{2}[a-zA-Z0-9]{1,30}`, no spaces) whose check digits pass
mod-97. The .04 to .08 templates write the debtor and creditor accounts
with `{% if … is iban %}<IBAN>…{% else %}<Othr><Id>…{% endif %}`; those
templates write no other account (no charges or ultimate-party account).

## Consequences

- Breaking for output: for the same input, a valid IBAN in either column
  of a .04 to .08 message moves from `<Othr><Id>` to `<IBAN>`. The golden
  files and bundled examples for .04 to .08 are regenerated with
  `scripts/generate_golden_files.py` and
  `scripts/generate_xml_examples.py`; they change only in those
  elements.
- Any other value (an account number, an IBAN written with spaces, one
  with bad check digits) renders byte-identically to 0.0.81.
- `tests/test_account_iban_element.py` generates every version from .03
  to .13 with IBAN input and requires `<IBAN>` for both accounts, so the
  versions cannot drift apart again.
- Not addressed here: the .04 to .08 templates write no `PmtTpInf`
  service level although the input has `service_level_code`, so SEPA
  Schematron rule EPC-PMT-002 still fails on their samples.
