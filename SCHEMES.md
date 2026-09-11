<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Scheme-aware validation

XSD validation proves a payment file is *well-formed*. It does **not** prove
the payment obeys the rulebook of the scheme it will clear through — currency,
IBAN validity, character set, amount ceilings. A file can pass the XSD and
still be rejected by the bank.

Pain001 adds that layer. Point it at a **profile** and it returns structured,
per-row violations on top of XSD validation.

## Usage

CLI (gates both dry-run and generation):

```bash
pain001 -t pain.001.001.03 -d payments.csv --scheme sepa-sct --dry-run
pain001 -t pain.001.001.03 -d payments.csv --scheme sepa-sct --explain
pain001 -t pain.001.001.03 -d payments.csv --scheme sepa-sct --scheme-format json
```

Python:

```python
from pain001 import validate_scheme

result = validate_scheme(rows, profile="sepa-sct")
for v in result.violations:
    print(v.index, v.rule, v.field, v.message, v.remediation)
```

REST API — add `"scheme"` to the request body of `POST /api/validate` or
`POST /api/generate`; violations come back in `scheme_violations`.

Exit codes (CLI): `0` pass · `1` violations found · `2` unknown profile.

### Composing profiles

Profiles compose. Name several, comma-separated, and every rulebook runs
over the same rows; the result carries the union of their findings,
ordered by row:

```bash
pain001 -t pain.001.001.03 -d batch.csv --scheme sepa-sct,anti-duplicate --dry-run
```

```python
result = validate_scheme(rows, profile="sepa-sct,anti-duplicate")
result.profile  # -> "sepa-sct,anti-duplicate"
```

The same spelling works in the `scheme` field of the REST API and the
`profile` argument of the MCP `validate_payment_scheme` tool. An unknown
name anywhere in the list is rejected as a whole (exit code `2`, HTTP 400).

## Profiles

| Profile | Scheme | Message types |
| :--- | :--- | :--- |
| `sepa-sct` | SEPA Credit Transfer | pain.001 |
| `sepa-sdd` | SEPA Direct Debit (CORE / consumer) | pain.008 |
| `sepa-b2b` | SEPA Direct Debit (Business-to-Business) | pain.008 |
| `sepa-inst` | SEPA Instant Credit Transfer (SCT Inst) | pain.001 |
| `xborder-ct` | Cross-border credit transfer (generic, multi-currency) | pain.001 |
| `anti-duplicate` | Cross-record duplicate detection (composes with any of the above) | pain.001, pain.008 |
| `uk-bacs` | UK Bacs Direct Credit | pain.001 |
| `uk-fps` | UK Faster Payments | pain.001 |
| `uk-chaps` | UK CHAPS | pain.001 |
| `uk-bacs-dd` | UK Bacs Direct Debit | pain.008 |
| `de-ccu` | Germany urgent euro (DK CCU) | pain.001 |
| `de-axz` | Germany foreign payment (DK AXZ) | pain.001 |
| `ch-domestic` | Switzerland domestic (SPS type D) | pain.001 |
| `ch-sepa` | Switzerland SEPA (SPS type S) | pain.001 |
| `se-bankgiro` | Sweden Bankgiro | pain.001 |
| `us-ach` | US ACH | pain.001, pain.008 |
| `us-wire` | US Fedwire | pain.001 |
| `us-rtp` | US RTP and FedNow | pain.001 |
| `hk-fps` | Hong Kong FPS | pain.001 |
| `sg-fast` | Singapore FAST | pain.001 |
| `my-duitnow` | Malaysia DuitNow | pain.001 |
| `qa-qatch` | Qatar QATCH credit | pain.001 |
| `ae-uaefts` | UAE UAEFTS | pain.001 |
| `cbpr-cross-border` | Swift CBPR+ cross-border | pain.001 |
| `purpose-mandate-ae` | UAE CBUAE purpose of payment (purpose code mandatory) | pain.001 |
| `purpose-mandate-qa` | Qatar QCB purpose of payment (purpose code mandatory) | pain.001 |
| `purpose-mandate-my` | Malaysia BNM purpose code (purpose code mandatory) | pain.001 |
| `purpose-mandate-gb` | UK CHAPS purpose code (purpose code mandatory) | pain.001 |
| `purpose-mandate-hk` | Hong Kong RMB cross-border purpose code (purpose code mandatory, CNY only) | pain.001 |

### Rail profiles: the public rules of eighteen rails

Each rail profile is a declarative rulebook drawn from the public scheme
and bank documents the corpus plan cites, in `pain001/validation/rails.py`:
currency and per-item ceiling, expected service level and local
instrument, the domestic account shape (sort code and account, ABA
routing number with its check digit, HKICL or SGIBG bank codes),
reference lengths, purpose and regulatory-reporting mandates, address
and UETR requirements, and for direct debits the mandate, sequence and
creditor-identifier rules. What a scheme document states is an error;
what the plan records as typical bank practice or an assumption is a
warning. Rule ids are `<RAIL>-<ASPECT>` (`UK-FPS-AMT`, `CH-DOM-CDTRREF`)
and every remediation hint names the source document.

The five `purpose-mandate-<cc>` profiles carry a country's purpose-code
mandate on its own, so they compose with any rail: `uk-chaps,purpose-mandate-gb`.

Rails judge the same rows the SEPA profiles do; a built corpus file is
projected onto those rows by `pain001.corpus.rules.projection` so the
corpus gate can run them (the plan's L2).

| Rail | Sources |
| :--- | :--- |
| `uk-bacs` | Bacs ISO 20022 / Standard 18 translation guide v1.1; Bacs service description (originator name and reference lengths) |
| `uk-fps` | Pay.UK Faster Payments scheme limits; Pay.UK ISO 20022 usage (service levels URGP and URNS) |
| `uk-chaps` | Bank of England: ISO 20022 enhanced data in CHAPS (purpose codes from 1 May 2025, structured or hybrid addresses); NatWest Bankline XML import guide (Jan 2025) |
| `uk-bacs-dd` | Bacs AUDDIS service guide; Bacs ISO 20022 translation guide v1.1 (sequence-type to transaction-code mapping is an assumption) |
| `de-ccu` | DK DFÜ-Abkommen Anlage 3 V26.11, order type CCU; DZ BANK CCU product description |
| `de-axz` | DK DFÜ-Abkommen Anlage 3 V3.8, order type AXZ; DZ BANK AXZ product description (regulatory reporting for AWV) |
| `ch-domestic` | SIX Swiss Payment Standards, IG Credit Transfer SPS 2025 v2.2 and SPS 2026 v2.3; SIX Business Rules 3.2 |
| `ch-sepa` | SIX Swiss Payment Standards, IG Credit Transfer, payment type S |
| `se-bankgiro` | Nordea pain.001 examples v2.6 (Jun 2026); Swedbank MIG 2.0; Bankgirot OCR reference rules |
| `us-ach` | Nacha Operating Rules (Standard Entry Class codes); Huntington pain.001 developer documentation; Cross River pain.001.001.03 input specification |
| `us-wire` | Federal Reserve Fedwire Funds Service ISO 20022 quick reference; Citi ISO 20022 FAQs (Feb 2026) |
| `us-rtp` | The Clearing House RTP network (per-item limit); Cross River RTP input specification |
| `hk-fps` | HKICL Faster Payment System rules and clearing-code list; East West Bank HK ISO 20022 FPS file specification |
| `sg-fast` | Association of Banks in Singapore, FAST (S$200,000 per transaction); UOB, OCBC and DBS ISO 20022 pages |
| `my-duitnow` | PayNet DuitNow developer documentation; BNM purpose-code lists as published by Deutsche Bank, HSBC and CIMB Malaysia |
| `qa-qatch` | Qatar Central Bank retail payment pages; ClearingPost QA-RTGS guide; HSBC Qatar purpose-of-payment page |
| `ae-uaefts` | CBUAE technical notes on transaction codes for balance-of-payments reporting (AUX700); HSBC UAE purpose-of-payment notes |
| `cbpr-cross-border` | Swift CBPR+ usage guidelines SR2025 (pain.001.001.09); CGI-MP pain.001 V09 implementation guide |

### `anti-duplicate`: catching a payment keyed in twice

Every profile above checks one row at a time. `anti-duplicate` looks
across the batch: two or more rows with the **same creditor IBAN, the
same amount and the same requested execution date** are the signature
of a payment that was entered or exported twice, and each of them is
flagged with `DUP-CREDITOR-DATE` naming the other rows in the group.

- **Exact-key only.** Amounts are bucketed to the currency's ISO 4217
  minor unit (two places for EUR, none for JPY, three for KWD), so
  `100` and `100.00` collide while `100.00` and `100.01` do not. IBANs
  are compared without whitespace and case-insensitively. Fuzzy name
  matching is deliberately out of scope.
- **Batch-local.** The engine has no memory between runs; cross-batch
  deduplication belongs to the system that holds history.
- **Rows missing a key field are skipped**, since they cannot be a
  duplicate of anything; the intra-record profiles report them.
- **Configurable precision.** `AntiDuplicateProfile(precision_overrides={"EUR": 0})`
  buckets euro amounts to whole units when you want a coarser match.

## Rule catalogue

Each violation carries a stable `rule` id, a `severity`, and a remediation
hint (shown by `--explain`).

| Rule | Severity | Applies to | Checks |
| :--- | :--- | :--- | :--- |
| `SEPA-CCY` | error | both | Currency is `EUR` |
| `SEPA-DBTR-IBAN` | error | both | Debtor IBAN present and valid (ISO 13616 / mod-97) |
| `SEPA-CDTR-IBAN` | error | both | Creditor IBAN present and valid |
| `SEPA-BIC` | error | both | Creditor agent BIC, when supplied, is well-formed (optional under SEPA) |
| `SEPA-AMT` | error | both | Amount > 0, ≤ 999,999,999.99, ≤ 2 decimal places |
| `SEPA-CHARSET` | error | both | Text fields use only the ISO 20022 Latin character set |
| `SEPA-LEN` | error | both | Names ≤ 70 chars, remittance ≤ 140 chars |
| `SEPA-SVCLVL` | warning | both | Service level declared as `SEPA` |
| `SEPA-INST-AMT` | error | `sepa-inst` | Amount ≤ 100,000.00 EUR (SCT Inst per-transaction cap) |
| `XB-CCY` | error | `xborder-ct` | Currency is a valid 3-letter ISO 4217 code (any currency) |
| `XB-BIC` | error | `xborder-ct` | Creditor agent BIC present and valid (mandatory cross-border) |
| `SDD-MNDT` | error | `sepa-sdd`, `sepa-b2b` | Mandate id present |
| `SDD-SEQTP` | error | `sepa-sdd` | Sequence type is one of `FRST`, `RCUR`, `OOFF`, `FNAL` |
| `B2B-SEQTP` | error | `sepa-b2b` | Sequence type is one of `FRST`, `RCUR` (B2B excludes `OOFF` and `FNAL`) |
| `B2B-CDTR-ID` | error | `sepa-b2b` | Creditor Identifier (`creditor_id`) present |
| `DUP-CREDITOR-DATE` | error | `anti-duplicate` | No other row in the batch shares this row's creditor IBAN, amount and requested execution date |
| `<RAIL>-CCY` | error | rail profiles | Currency is the rail's (or any ISO 4217 code for multi-currency rails) |
| `<RAIL>-AMT` | error or warning | rail profiles | Amount within the rail's per-item ceiling |
| `<RAIL>-SVCLVL` | warning | rail profiles | Service level is the one the rail expects |
| `<RAIL>-LCLINSTRM` | warning (error for ACH SEC codes) | rail profiles | Local instrument is one the rail accepts, or absent where the rail carries none |
| `<RAIL>-BIC` | error | rail profiles | Agent BIC present where required, and well-formed |
| `<RAIL>-IBAN` | error | rail profiles | Counterparty IBAN valid and from the rail's countries |
| `<RAIL>-MMBID` | error | rail profiles | Domestic clearing member id in the rail's shape (ABA check digit verified) |
| `<RAIL>-ACCT` | error | rail profiles | Domestic account number in the rail's shape |
| `<RAIL>-REF` | error | rail profiles | End-to-end id within the rail's length |
| `<RAIL>-RMT` | warning | rail profiles | Unstructured remittance within the rail's length |
| `<RAIL>-PURP` | error or warning | rail profiles | Purpose code present where mandated, and in the ISO external purpose list when present |
| `<RAIL>-RGLTRY` | error or warning | rail profiles | Regulatory reporting code present where mandated, in the prescribed form |
| `<RAIL>-CHRGBR` | error or warning | rail profiles | Charge bearer is one the rail accepts |
| `<RAIL>-ADDR` | error or warning | rail profiles | Counterparty address carries town and country |
| `<RAIL>-UETR` | warning | rail profiles | A UETR is present (needs pain.001.001.09 or later) |
| `<RAIL>-SEQTP` | error | rail profiles | Sequence type is one the scheme accepts |
| `<RAIL>-MNDT` | error | rail profiles | Mandate id present and within length |
| `<RAIL>-CDTRID` | error | rail profiles | Creditor identifier in the scheme's format |
| `<RAIL>-CDTRREF` | error | rail profiles | Structured reference paired and check-digit-valid (Swiss QRR with QR-IBAN, SCOR as ISO 11649; Swedish OCR) |
| `<RAIL>-BATCH` | warning | rail profiles | Batch booking as the rail expects |
| `PURP-<CC>` | error | `purpose-mandate-<cc>` | The country's purpose code is present, in the place and form the country prescribes |

## Adding a profile

Subclass `ValidationProfile`, implement `validate(rows) -> SchemeValidationResult`,
and register it in `PROFILES`:

```python
from pain001.validation.schemes import (
    PROFILES,
    SchemeValidationResult,
    SchemeViolation,
    ValidationProfile,
)


class MyProfile(ValidationProfile):
    name = "my-scheme"

    def validate(self, data):
        result = SchemeValidationResult(profile=self.name)
        for index, row in enumerate(data):
            if not row.get("payment_currency"):
                result.violations.append(
                    SchemeViolation(
                        rule="MY-CCY",
                        message="currency is required",
                        index=index,
                        field="payment_currency",
                    )
                )
        return result


PROFILES[MyProfile.name] = MyProfile()
```

Add a remediation hint for each new rule id to `REMEDIATIONS` so `--explain`
can surface it.
