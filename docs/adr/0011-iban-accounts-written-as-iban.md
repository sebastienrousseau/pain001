<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0011. Write IBAN accounts and the service level in .04 to .08

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

The same templates had no `PmtTpInf` at all, so `service_level_code`
was dropped from the input, and a SEPA file built from them failed the
bundled Schematron rule EPC-PMT-002. The .03 and .09 to .13 templates
write `PmtTpInf/SvcLvl/Cd` on the payment batch when the column has a
value.

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

For the service level, the same reasoning: copy the switch .03 and .09
make. The .04 to .08 templates write
`{%- if service_level_code %}<PmtTpInf><SvcLvl><Cd>…</Cd></SvcLvl></PmtTpInf>`
after `BtchBookg`, where the XSD puts it. The .05 to .08 data preparer
used to default the value to `SEPA`, unused until now; it passes the
column as given, so the element appears only for input that sets it.
The charge bearer stays on each transaction, where these templates
already write it; the SEPA rulebook's EPC-PMT-003 now accepts it there.

## Consequences

- Breaking for output: for the same input, a valid IBAN in either column
  of a .04 to .08 message moves from `<Othr><Id>` to `<IBAN>`, and a
  non-empty `service_level_code` adds `PmtTpInf/SvcLvl/Cd` to the batch.
  The golden files and bundled examples for .04 to .08 are regenerated
  once for both, with `scripts/generate_golden_files.py` and
  `scripts/generate_xml_examples.py`; they change only in those
  elements.
- Any other account value (an account number, an IBAN written with
  spaces, one with bad check digits) and input without a service level
  render byte-identically to 0.0.81.
- `tests/test_account_iban_element.py` generates every version from .03
  to .13 with IBAN input and requires `<IBAN>` for both accounts, and
  `tests/test_service_level_element.py` requires the service level in
  .04 to .08 and its absence without one, so the versions cannot drift
  apart again.
- The bundled .05 to .08 samples pass the SEPA Schematron rulebook. The
  .04 sample still does not: it uses charge bearer `SHAR` and service
  level `INST` on purpose.

## Notice

The README's stability policy makes a change to generated XML breaking
and asks for it to be announced one release ahead. This one was not: it
was decided and shipped in 0.0.82. The old output was not conformant
(an IBAN with no scheme, a service level dropped), and SEPA files built
from .04 to .08 failed pain001's own checks, but that argues for a
quick announcement, not for none. The policy is unchanged. From 0.0.83
the release preflight refuses a release whose golden files changed
unless the previous release's CHANGELOG has an `### Announced` section
or the release records its exception, as this one now does.
