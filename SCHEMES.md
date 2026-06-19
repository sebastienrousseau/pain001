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

## Profiles

| Profile | Scheme | Message types |
| :--- | :--- | :--- |
| `sepa-sct` | SEPA Credit Transfer | pain.001 |
| `sepa-sdd` | SEPA Direct Debit (CORE / consumer) | pain.008 |
| `sepa-b2b` | SEPA Direct Debit (Business-to-Business) | pain.008 |
| `sepa-inst` | SEPA Instant Credit Transfer (SCT Inst) | pain.001 |
| `xborder-ct` | Cross-border credit transfer (generic, multi-currency) | pain.001 |

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
