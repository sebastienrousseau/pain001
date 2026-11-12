<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# CHAPS enhanced data: purpose codes and LEIs

This page records what the Bank of England requires of CHAPS payments
under its ISO 20022 enhanced-data policy, which of those requirements
reach a corporate's `pain.001`, and what pain001 checks as a result.
Each rule names the public document it rests on. Where a document is
ambiguous, pain001 implements the narrower reading and says so here.

## Sources

| Ref | Document | Read |
| :--- | :--- | :--- |
| BoE-2024 | Bank of England, *Mandating ISO 20022 enhanced data in CHAPS*, policy statement (2024): <https://www.bankofengland.co.uk/paper/2024/policy-statement/mandating-iso-20022-enhanced-data-in-chaps> | 2026-11-11 |
| BoE-2025 | Bank of England, *Expanding mandatory ISO 20022 enhanced data in CHAPS from 2027*, policy statement (22 September 2025, updated July 2026): <https://www.bankofengland.co.uk/paper/2025/ps/expanding-mandatory-iso-20022-enhanced-data-in-chaps-from-2027> | 2026-11-11 |
| ISO-17442 | ISO 17442:2012, *Financial services: Legal entity identifier (LEI)*, clauses 4 and 5 and Annex A (public preview: <https://cdn.standards.iteh.ai/samples/59771/b4526b6c9dc04897b014c659ed70ad27/ISO-17442-2012.pdf>) | 2026-11-11 |
| LEI-ROC | LEI Regulatory Oversight Committee, *The LEI*: <https://www.leiroc.org/lei.htm> | 2026-11-11 |

## What the Bank of England requires

**Purpose codes.**

- From 1 May 2025, purpose codes are mandatory for all payments between
  financial institutions and for property transactions (BoE-2024,
  sections 1.1 and 4.1.5). The property codes it mandates are HLRP,
  HLST, PLDS, PDEP, PCOM and PLRF; all six are in the ISO
  `ExternalPurpose1Code` set pain001 bundles.
- "From November 2027, we are expanding mandatory requirements for
  Purpose Codes to all CHAPS payments" (BoE-2025, section 2). The
  requirement is set through the CHAPS rulebook for payment initiation
  channels within the CHAPS direct participants' control; the Bank
  "will not be expanding mandatory enhanced data requirements to
  payment initiation channels outside" that control in 2027 (BoE-2025,
  section 3). BoE-2024 (section 6.1) counts "direct file submission
  from a corporate client" among the data a participant receives, and
  says "In a file upload, DPs must validate that the enhanced data
  fields are populated for (at least) the payments in scope".
- "CHAPS will continue to accept all Purpose Codes on the international
  External Code Set", and the Bank encourages the UK recommended
  purpose code list for UK-originated payments (BoE-2024, sections
  4.1.1 and 4.1.2).
- The Bank "will not reject CHAPS payments solely due to incomplete or
  incorrect enhanced data before end-2028 at the earliest" (BoE-2025,
  section 2.4); compliance is through the rulebook, not message
  rejection.

**LEIs.**

- From May 2025, LEIs are mandatory in payments between financial
  institutions: in `pacs.009` and, for `pacs.008`, where the effective
  ultimate debtor and creditor are financial institutions (BoE-2024,
  section 7.2, Table B). For the initiating party, debtor agent and ultimate
  parties of a `pacs.008`, the LEI is mandatory where one is provided.
- From November 2027, LEIs are also mandatory in `pacs.004` returns
  and `pacs.009 COV` payments between financial institutions
  (BoE-2025, Box A).

## What reaches a corporate's pain.001

A corporate's CHAPS payment travels as a `pacs.008` customer credit
transfer. Of the rules above:

| Rule | Reaches a pain.001? | pain001 element |
| :--- | :--- | :--- |
| Purpose code on every CHAPS payment (from November 2027) | Yes, for files submitted to a participant | `CdtTrfTxInf/Purp/Cd` (`purpose_code`) |
| Property purpose codes (from May 2025) | Yes, but a file does not say a payment is a property payment | `Purp/Cd` |
| LEIs between financial institutions | No: a corporate's payment is not one | none |
| LEI where one is provided (initiating party, debtor, agents) | Yes, it is carried on | `InitgPty/Id/OrgId/LEI`, `Dbtr/Id/OrgId/LEI` |
| `pacs.004`, `pacs.009 COV` LEIs | No: interbank messages | none |

The policy says nothing about category purpose (`PmtTpInf/CtgyPurp`);
it is not a purpose code for these rules.

## What pain001 checks

On the `uk-chaps` rail (`--scheme uk-chaps`):

- **`UK-CHAPS-PURP`**: a payment with neither `purpose_code` nor
  `purpose_proprietary` is a warning when its requested execution date
  is before the cut-over, and an error from it. A `purpose_code` must
  be in the bundled ISO `ExternalPurpose1Code` list whatever the date
  (an error).
- **`UK-CHAPS-LEI`**: any `*_lei` value present must be a well-formed
  ISO 17442 LEI (an error). No LEI is required.

The load-time identifier checks also verify every `*_lei` column on
every load, rail or not (code `P001-E022`; see
[troubleshooting](troubleshooting.rst)).

### Readings where the sources are ambiguous

- **The cut-over day.** BoE-2025 says "November 2027" and names no day.
  pain001 applies the mandate to payments whose requested execution
  date is on or after **1 December 2027**
  (`pain001.validation.rails.CHAPS_PURPOSE_ALL_PAYMENTS_FROM`), the
  first date certainly in force; during November 2027 a missing code
  stays a warning. The rule reads the execution date in the file
  (`requested_execution_date`, or the date part of
  `requested_execution_datetime`, inherited from the first row as the
  `PmtInf` header is), never the clock. A row with no readable date is
  treated as before the cut-over. To apply another day, replace the
  rail:

  ```python
  import dataclasses
  from datetime import date

  from pain001.validation import rails
  from pain001.validation.rails import RailProfile

  chaps = dataclasses.replace(
      rails.rail("uk-chaps"), purpose_required_from=date(2027, 11, 1)
  )
  result = RailProfile(chaps).validate(rows)
  ```

- **Property payments before the cut-over.** A pain.001 does not mark a
  payment as a property transaction, so pain001 cannot tell when the
  May 2025 property mandate applies. A missing code stays a warning,
  not an error, until the all-payments mandate.
- **Proprietary purposes.** The policy speaks of codes from the
  External Code Set and does not say a proprietary purpose is refused.
  A `purpose_proprietary` value satisfies presence; only a
  `purpose_code` is checked against the ISO list.
- **Which LEIs.** No LEI requirement in the policy falls on a
  corporate's own payment, so none is required. An LEI the file does
  carry is passed on in the `pacs.008` (BoE-2024, Table B), so it must
  verify.
- **Profile `purpose-mandate-gb`** is unchanged: it is an opt-in
  profile that requires a purpose code on every row whatever the date.

## LEI structure (ISO 17442)

An LEI is twenty characters: eighteen alphanumerics (`18!an`) then two
check digits (`2!n`) (ISO-17442, clause 4); the ISO 20022 schemas
restrict letters to upper case (`[A-Z0-9]{18}[0-9]{2}`). The check
digits use ISO/IEC 7064 MOD 97-10 with letters converted A=10 to Z=35:
to generate them, append `00`, convert and take 98 minus the
remainder; an LEI is valid when the whole twenty-character string
leaves remainder 1 (ISO-17442, clause 5; Annex A.1 gives `A1234567`
the check digits `02`, a test pain001 runs).

LEI-ROC describes characters 1 to 4 as the issuing LOU's prefix and 5
and 6 as two reserved zeros. That is an allocation rule for issuers,
not part of the ISO check digits, so pain001 does not enforce it. The
check proves an LEI is well formed, not that it is registered or
current: only the GLEIF index says that.

## The corpus overlay

The public overlay `scenarios/overlays/gb.boe.chaps-enhanced-data.yaml`
holds the same purpose rule for the corpus scenarios. Its property-code
rule lists the six codes BoE-2024 mandates.
