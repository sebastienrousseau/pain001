<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Request-local payment policies

Install `pain001[rules]` to add CEL predicates to the existing schema and
scheme checks. Policies report findings; they never repair payment data.
A true predicate produces a finding. Only `error` severity blocks generation.

```yaml
- id: FRIDAY-HIGH-VALUE
  where: payment_amount > 50000 && day_of_week(requested_execution_date) == "Friday"
  severity: error
  message: "High-value Friday payments require a different execution date."
```

Save this as `rules.yaml` and run:

```sh
pain001 validate -t pain.001.001.03 -d payments.csv \
  --scheme sepa-sct,custom --rules rules.yaml
```

`generate` accepts the same policy file. REST validation, synchronous
generation and background generation accept the YAML text in the `rules`
request field. Paths are accepted only by the CLI, not by inline REST rules.
Each request owns its policy instance; it does not modify the plugin registry.
Schema validation still runs, and custom rules compose with built-in or
registered scheme profiles.

Predicates use flat record field names. Numeric schema fields are exact
decimals. Use `decimal("12.34")` for fractional thresholds; floating-point
literals are rejected. Available helpers are `day_of_week(iso_date)`,
`country_of_iban(valid_iban)`, `is_business_day(iso_date, country_code)` and
`decimal(text)`. Weekday names are English. Business days mean weekdays
excluding national public holidays, not a bank's settlement calendar.
Calendar years are limited to 1900–2100.

An IBAN does not identify the account currency. `currency_of_iban` is
therefore deliberately unsupported: use the explicit `currency` or
`payment_currency` field. No external service or bank data is queried.

Limits: 64 KiB policy text, 64 rules, 2,048 characters and 512 AST nodes per
expression, and 4,096 characters per referenced string field. YAML aliases,
anchors and tags, CEL collection macros and non-whitelisted calls are
rejected. Syntax, missing-field and evaluation errors fail closed. Diagnostics
identify the rule without returning an interpreter traceback containing rows.
Policies are bounded synchronous computations, not a general-purpose script
runtime. See [ADR-0006](adr/0006-local-policies-and-safe-corrections.md).

For review-only repair candidates, the MCP `suggest_record_fix` tool accepts
a record and an error with `field` and `rule` keys. Supported rules are
`CHARSET`, `FIELD-LENGTH`, `DATE-FORMAT` and `MISSING-REQUIRED`. Length limits
come from bundled schemas, ambiguous dates are refused, and missing fields
receive visibly marked placeholders. Every patch requires review and full
revalidation. IBANs, BICs, account identifiers, amounts and currencies are
always refused, even for whitespace-only changes. Nothing is applied to the
record automatically.
