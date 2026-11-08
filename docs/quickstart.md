<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Quickstart: from CSV to validated ISO 20022 in 10 minutes

This guide walks you from "I have payment data in a spreadsheet" to
"I have an XSD-validated `pain.001.001.03` XML file" in
five short steps. No prior ISO 20022 knowledge required.

If you already know what pain.001 is and just want the CLI flags,
skip to the [README](https://github.com/sebastienrousseau/pain001/blob/main/README.md#quick-start).

---

## Prerequisites

- Python 3.11 or later
- 10 minutes
- A terminal

That's it. You won't need a bank account, a sandbox, or an
ISO 20022 spec PDF. Everything the tutorial needs ships inside the
package.

## Step 1: Install

```bash
pip install pain001
```

Verify:

```bash
pain001 --version
# -> pain001, version <installed version>
```

If you'd rather not pollute your global Python environment:

```bash
python -m venv venv
source venv/bin/activate          # macOS/Linux
venv\Scripts\activate             # Windows
pip install pain001
```

## Step 2: See what pain001 can do

```bash
pain001 --help
```

You'll see the command suite (`generate`, `validate`, `versions`,
`inspect`, `init` and the rest, each with its own `--help`). We'll use
four of them.

List the message types the library can generate:

```bash
pain001 versions
```

Output:

```text
Supported message types
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Message Type
 ─────────────────────────────────
  pain.001.001.03  ← we'll use this one
  pain.001.001.04
  pain.001.001.05
  ...
  pain.001.001.13
  pain.008.001.02
  pain.008.001.08
```

`pain.001.001.03` is the most widely supported version — most
European banks accept it, and SEPA SCT clears on it. Start there;
upgrade later if your bank wants a newer version.

## Step 3: Scaffold a starter CSV

You don't need to write a CSV from scratch — pain001 ships a
template you can edit:

```bash
pain001 init pain.001.001.03 -o my-payments.csv
```

Output:

```text
✓ Wrote starter CSV: my-payments.csv
Edit it, then run: pain001 generate -t pain.001.001.03 -d my-payments.csv
```

Open `my-payments.csv` in your editor. You'll see a few synthetic
sample rows with every column the schema needs (debtor IBAN, creditor
IBAN, amount, etc.). Replace the values with your own.

> **Editor tip.** Install [`pain001-lsp`](https://pypi.org/project/pain001-lsp/)
> if your editor speaks LSP — you'll get real-time IBAN / BIC
> validation as you type. Or run `pain001 serve` (needs `pain001[api]`)
> and use the browser dashboard at `/api/v1/ui` to validate a file.

## Step 4: Validate before generating

The single most useful command in the suite. Tells you *whether* the
file would generate, *without* generating it. Use this in CI:

```bash
pain001 validate -t pain.001.001.03 -d my-payments.csv
```

Output (success; the record count is the number of rows in your file):

```text
✓ Data validation passed (4 payment records)

✓ All validations passed (--dry-run: no XML generated)
```

Every IBAN and BIC column is checked on the way in, with or without a
scheme: an IBAN must have the right length for its country and valid
mod-97 check digits, and a BIC must be ISO 9362. Output (failure, here a
debtor IBAN with a broken check digit):

```text
✗ Data validation failed: Invalid account identifiers (1):
  row 0, column debtor_account_IBAN: not a valid IBAN (IBAN checksum validation
failed (mod 97 = 2, expected 1))
Fix the values, or skip these checks with --no-identifier-checks
(identifier_checks=False).
```

Rows count from 0 and the message never repeats the IBAN itself. Pass
`--no-identifier-checks` only for test data you know is synthetic.

Want to check it'll pass the SEPA Credit Transfer rulebook *as
well as* the schema? Add `--scheme`. The scheme profiles are where
currency, amount limits and the rest of the rulebook are enforced:

```bash
pain001 validate -t pain.001.001.03 -d my-payments.csv --scheme sepa-sct
```

Output:

```text
✓ Data validation passed (4 payment records)
→ Validating against scheme 'sepa-sct'...
✓ Scheme 'sepa-sct' passed
```

Output (failure, here a debtor IBAN with a broken check digit):

```text
  row 0 [SEPA-DBTR-IBAN] debtor_account_IBAN: debtor_account_IBAN must be a
valid IBAN (ISO 13616 / mod-97)
✗ Scheme 'sepa-sct' validation failed
```

Every scheme profile, from the SEPA rulebooks to domestic rails and the
cross-record `anti-duplicate`, is listed in
[SCHEMES.md](https://github.com/sebastienrousseau/pain001/blob/main/SCHEMES.md).
Use the one that matches the clearing system your bank will route this through
(`xborder-ct` accepts any ISO currency but one per file, since every row goes
into a single payment block),
and add `anti-duplicate` (comma-separated: `--scheme sepa-sct,anti-duplicate`)
to catch a payment keyed in twice before it reaches the bank.

## Step 5: Generate the XML

```bash
pain001 generate -t pain.001.001.03 -d my-payments.csv -o ./outbox
```

Output:

```text
✓ Schema validation passed
→ Generating XML payment files...

✓ Success! XML files generated successfully.
Message Type: pain.001.001.03
Output Location: <your directory>/outbox
```

The file is written as `outbox/pain.001.001.03.xml`.

That file is **XSD-validated** — it conforms to the official ISO
20022 schema. The amounts in it flow through `decimal.Decimal` end
to end (no float rounding), and the `NbOfTxs` + `CtrlSum` control
totals are computed from the data (not echoed from input).

Quick sanity-check the file:

```bash
head -7 ./outbox/pain.001.001.03.xml
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03 pain.001.001.03.xsd">
    <CstmrCdtTrfInitn>
        <GrpHdr>
            <MsgId>1</MsgId>
```

XSD validity is not a guarantee that your bank will accept the file;
check it against your bank's own rules. Generation never transmits the
file. Send it through your bank's channel (SFTP, EBICS, web portal
upload, etc.), or use `pain001 upload` (needs `pain001[upload]`) for an
explicit SFTP delivery; see the
[SFTP upload guide](https://github.com/sebastienrousseau/pain001/blob/main/docs/sftp-upload.md).

## What you just learned

- `pain001 versions` — see what's supported
- `pain001 init <type>` — scaffold a starter CSV
- `pain001 validate` — CI pre-flight (use this every time)
- `pain001 generate` — write the XML

That's 80% of the surface for 90% of users.

## Where to go next

| If you want to... | Read |
| :--- | :--- |
| Load data from JSON / SQLite / Parquet instead of CSV | [User guide](https://github.com/sebastienrousseau/pain001/blob/main/docs/usage.rst) and [input columns](https://github.com/sebastienrousseau/pain001/blob/main/docs/input-columns.md) |
| Run pain001 as a REST service | [OPERATIONS.md](https://github.com/sebastienrousseau/pain001/blob/main/OPERATIONS.md) |
| Stream large batches (millions of rows) | [`examples/09_streaming_large_batch.py`](https://github.com/sebastienrousseau/pain001/blob/main/examples/09_streaming_large_batch.py) |
| Pass an Excel `.xlsx` directly | `pip install pain001-loader-xlsx` |
| Wire pain001 into an AI assistant (Claude Desktop, etc.) | `pip install pain001-mcp` |
| Migrate data between pain.001 versions (e.g. 03 → 09) | [`examples/08_version_migration.py`](https://github.com/sebastienrousseau/pain001/blob/main/examples/08_version_migration.py) |
| Read the full scheme rulebook catalogue | [SCHEMES.md](https://github.com/sebastienrousseau/pain001/blob/main/SCHEMES.md) |
| Deploy the REST API to production | [OPERATIONS.md](https://github.com/sebastienrousseau/pain001/blob/main/OPERATIONS.md) |

## Troubleshooting

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| `pain001: command not found` | Install went to a directory not on `PATH` | Re-install in a venv (see Step 1) |
| `Invalid value for '-t' / '--xml-message-type'` | Typo in the `-t` flag | Run `pain001 versions` and copy-paste exactly |
| `must be a valid IBAN` for a known-good IBAN | Hidden whitespace or smart quotes | Re-type by hand, or clean the text with the `pain001.sanitize_to_charset` Python function |
| `validation failed` but the schema is the one pain001 ships | Stale `pyproject.toml`-installed pain001 vs CLI-installed one | `pip install --upgrade pain001` |
| `pain.008.xxxx` only generates SEPA Direct Debits, not Credit Transfers | Different message type | pain.001 = Credit Transfer, pain.008 = Direct Debit. Run `pain001 versions` for the bundled message types |

## Stuck?

- [Open an issue](https://github.com/sebastienrousseau/pain001/issues/new/choose)
  with the CLI invocation that failed and the error output, whether
  it is a question or a bug.
- See [SUPPORT.md](https://github.com/sebastienrousseau/pain001/blob/main/SUPPORT.md) for the full support matrix.

---

*Found a confusing bit in this tutorial? PRs to
[`docs/quickstart.md`](https://github.com/sebastienrousseau/pain001/blob/main/docs/quickstart.md)
are the most useful thing a new user can contribute — you spot the
sharp edges that long-time users no longer see.*
