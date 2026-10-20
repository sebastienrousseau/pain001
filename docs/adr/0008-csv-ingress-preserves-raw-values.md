<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0008. Preserve raw CSV values on ingress; formula neutralisation is opt-in

- **Status:** Proposed
- **Date:** 2026-10-20
- **Deciders:** maintainer (pending review)

## Context

v0.0.72 added CWE-1236 "formula injection shielding" to
`load_csv_data` and `load_csv_data_streaming`: every string cell that
starts with `=`, `+`, `-`, `@`, tab, CR or LF gets a single-quote
prefix.

That shield guards against a spreadsheet evaluating a cell when a CSV
is opened in Excel or similar. pain001 reads CSV and writes ISO 20022
XML, which no spreadsheet evaluates. So the prefix protected nothing
on the XML path, and it changed the payment data. `+44 20 7946 0000`
became `'+44 20 7946 0000` and `-INV-0042` became `'-INV-0042` in the
generated message. Both are valid pain.001 content, and the bank
received something other than what the user supplied.

Commit `7d851ee` (on `feat/v0.0.73`) reverted the default.

## Options considered

1. **Keep sanitising by default.** No change in behaviour since v0.0.72,
   but legitimate payment data keeps being corrupted in the XML, a
   format where the threat does not apply.
2. **Sanitise only the fields that can never start with these
   characters.** Narrower, but it needs a per-field allow-list for
   every message type and still guesses at user intent.
3. **Preserve raw values by default and make neutralisation opt-in**
   (`sanitize_formula=True`). The XML carries exactly what was supplied.
   A caller that re-exports rows to a spreadsheet can opt in.

## Decision

Option 3. Ingress keeps the raw value. Formula neutralisation is a
concern for whoever writes a spreadsheet, not for the XML generator,
so it belongs where a spreadsheet is produced.

## Consequences

- Generated XML for inputs whose cells start with `+`, `-`, `=` or `@`
  differs from v0.0.72's output. This reverts the v0.0.72 output to the
  v0.0.71 output for those inputs. Record it in the release notes.
- `sanitize_formula_injection` stays public in `pain001.security` for
  callers that write CSV or XLSX.
- The opt-in is only a Python keyword argument today. The CLI, the
  REST API and the built-in `csv` loader plugin (`plugins/_builtins.py`)
  do not expose it. If a spreadsheet *output* path is ever added, it
  must apply `sanitize_formula_injection` at that sink.
- `tests/test_csv_loader.py` covers both the default (raw) and the
  opt-in (neutralised) behaviour.
