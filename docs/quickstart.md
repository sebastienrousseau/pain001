<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Quickstart: from CSV to validated ISO 20022 in 10 minutes

This guide walks you from "I have payment data in a spreadsheet" to
"I have a validated `pain.001.001.03` XML the bank will accept" in
five short steps. No prior ISO 20022 knowledge required.

If you already know what pain.001 is and just want the CLI flags,
skip to the [README](../README.md#quick-start).

---

## Prerequisites

- Python 3.10 or later
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
# -> pain001 0.0.53
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

You'll see a command suite — `generate`, `validate`, `versions`,
`inspect`, `init`, `serve`, `mcp`. We'll use four of them.

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
  pain.001.001.12
  pain.008.001.02
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

Open `my-payments.csv` in your editor. You'll see a single sample
row with every column the schema needs (debtor IBAN, creditor IBAN,
amount, etc.). Replace the values with your own.

> **Editor tip.** Install [`pain001-lsp`](https://pypi.org/project/pain001-lsp/)
> if your editor speaks LSP — you'll get real-time IBAN / BIC
> validation as you type. Or open the CSV in pain001's [REST API
> Scalar viewer](https://sebastienrousseau.github.io/pain001/api-reference.html).

## Step 4: Validate before generating

The single most useful command in the suite. Tells you *whether* the
file would generate, *without* generating it. Use this in CI:

```bash
pain001 validate -t pain.001.001.03 -d my-payments.csv
```

Output (success):

```text
✓ Data validation passed (1 payment records)
```

Output (failure):

```text
✗ Data validation failed: invalid IBAN at row 1, column
  debtor_account_IBAN: DE89370400440532013ABC
```

Want to check it'll pass the SEPA Credit Transfer rulebook *as
well as* the schema? Add `--scheme`:

```bash
pain001 validate -t pain.001.001.03 -d my-payments.csv --scheme sepa-sct
```

Output:

```text
✓ Data validation passed (1 payment records)
✓ Scheme 'sepa-sct' passed
```

Five scheme profiles ship today (v0.0.53): `sepa-sct`, `sepa-sdd`,
`sepa-inst`, `sepa-b2b`, `xborder-ct`. Use the one that matches the
clearing system your bank will route this through.

## Step 5: Generate the XML

```bash
pain001 generate -t pain.001.001.03 -d my-payments.csv -o ./outbox
```

Output:

```text
✓ Schema validation passed
✓ Data validation passed (1 payment records)
✓ XML generated and validated: outbox/pain.001.001.03.xml
```

That file is **XSD-validated** — it conforms to the official ISO
20022 schema. The amounts in it flow through `decimal.Decimal` end
to end (no float rounding), and the `NbOfTxs` + `CtrlSum` control
totals are computed from the data (not echoed from input).

Quick sanity-check the file:

```bash
head -5 ./outbox/pain.001.001.03.xml
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
  <CstmrCdtTrfInitn>
    <GrpHdr>
      <MsgId>MSG-0001</MsgId>
```

That XML is ready to send to your bank via whatever transport they
prefer (SFTP, EBICS, web portal upload, etc.). pain001 does not
transmit it — pair it with your bank channel of choice.

## What you just learned

- `pain001 versions` — see what's supported
- `pain001 init <type>` — scaffold a starter CSV
- `pain001 validate` — CI pre-flight (use this every time)
- `pain001 generate` — write the XML

That's 80% of the surface for 90% of users.

## Where to go next

| If you want to... | Read |
| :--- | :--- |
| Load data from JSON / SQLite / Parquet instead of CSV | [Input formats](../README.md#input-formats) |
| Run pain001 as a REST service | [REST API](../README.md#usage) (collapsed section) |
| Stream large batches (millions of rows) | [`examples/09_streaming_large_batch.py`](../examples/09_streaming_large_batch.py) |
| Pass an Excel `.xlsx` directly | `pip install pain001-loader-xlsx` |
| Wire pain001 into an AI assistant (Claude Desktop, etc.) | `pip install pain001-mcp` |
| Migrate data between pain.001 versions (e.g. 03 → 09) | [`examples/08_version_migration.py`](../examples/08_version_migration.py) |
| Read the full scheme rulebook catalogue | [SCHEMES.md](../SCHEMES.md) |
| Deploy the REST API to production | [OPERATIONS.md](../OPERATIONS.md) |

## Troubleshooting

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| `pain001: command not found` | Install went to a directory not on `PATH` | Re-install in a venv (see Step 1) |
| `Invalid XML message type` | Typo in the `-t` flag | Run `pain001 versions` and copy-paste exactly |
| `invalid IBAN` for a known-good IBAN | Hidden whitespace or smart quotes | Re-type by hand, or pipe through `pain001 sanitize-to-charset` |
| `validation failed` but the schema is the one pain001 ships | Stale `pyproject.toml`-installed pain001 vs CLI-installed one | `pip install --upgrade pain001` |
| `pain.008.xxxx` only generates SEPA Direct Debits, not Credit Transfers | Different message type | pain.001 = Credit Transfer, pain.008 = Direct Debit. See [Supported messages](../README.md#supported-messages) |

## Stuck?

- [Open a GitHub Discussion](https://github.com/sebastienrousseau/pain001/discussions)
  with the CLI invocation that failed + the error output.
- [Open an issue](https://github.com/sebastienrousseau/pain001/issues/new/choose)
  if you've found a bug.
- See [SUPPORT.md](../SUPPORT.md) for the full support matrix.

---

*Found a confusing bit in this tutorial? PRs to
[`docs/quickstart.md`](https://github.com/sebastienrousseau/pain001/blob/main/docs/quickstart.md)
are the most useful thing a new user can contribute — you spot the
sharp edges that long-time users no longer see.*
