<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

<p align="center">
  <img
    src="https://cloudcdn.pro/pain001/v1/logos/pain001.svg"
    alt="Pain001 logo"
    width="120"
    height="120"
  />
</p>

<h1 align="center">Pain001</h1>

<p align="center">
  <b>Generate ISO 20022-compliant payment files from CSV, SQLite, JSON, or Parquet data.</b>
</p>

<p align="center">
  <a href="https://pypi.org/project/pain001/"><img src="https://img.shields.io/pypi/v/pain001?style=for-the-badge" alt="PyPI version" /></a>
  <a href="https://pypi.org/project/pain001/"><img src="https://img.shields.io/pypi/pyversions/pain001.svg?style=for-the-badge" alt="Python versions" /></a>
  <a href="https://pypi.org/project/pain001/"><img src="https://img.shields.io/pypi/dm/pain001.svg?style=for-the-badge" alt="PyPI downloads" /></a>
  <a href="https://github.com/sebastienrousseau/pain001/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/sebastienrousseau/pain001/ci.yml?branch=main&label=Tests&style=for-the-badge" alt="Tests" /></a>
  <a href="https://codecov.io/github/sebastienrousseau/pain001?branch=main"><img src="https://img.shields.io/codecov/c/github/sebastienrousseau/pain001?style=for-the-badge" alt="Coverage" /></a>
  <a href="#license"><img src="https://img.shields.io/pypi/l/pain001?style=for-the-badge" alt="License" /></a>
  <a href="https://www.bestpractices.dev/projects/13858"><img src="https://img.shields.io/cii/level/13858?style=for-the-badge&label=OpenSSF" alt="OpenSSF Best Practices" /></a>
</p>

---

## Contents

**Getting started**

- [What is Pain001?](#what-is-pain001) — the problem it solves and how
- [Install](#install) — PyPI, extras, Docker, source
- [Quick start](#quick-start) — one command from CSV to validated XML

**Library reference**

- [Supported messages](#supported-messages) — every bundled ISO 20022 message type
- [Input formats](#input-formats) — CSV, SQLite, JSON, JSONL, Parquet
- [Usage](#usage) — CLI, scheme validation, dry-run, streaming, input normalization, REST API, Python API
- [Companion packages](#companion-packages) — MCP server, Language Server
- [Production users](#production-users) — who's running it, how to be listed

**Operational**

- [When not to use Pain001](#when-not-to-use-pain001) — honest boundaries
- [Deployment cookbook](docs/deployment-cookbook.md) — copy-pasteable docker-compose with TLS + Redis + Prometheus + Grafana
- [Development](#development) — gates, make targets, CI matrix
- [Security](#security) — hardening posture and reporting
- [Documentation](#documentation) — guides, API reference, examples
- [Contributing](#contributing) — how to get changes in
- [License](#license) — dual Apache-2.0 / MIT

---

## What is Pain001?

Banks reject malformed payment files. Pain001 takes the payment data you
already have — a CSV export, a SQLite table, a JSON feed, a Parquet file —
and turns it into ISO 20022 XML that validates against the official XSD
schema before it ever reaches your bank.

It handles the parts that are easy to get wrong:

| Concern | How Pain001 handles it |
| :--- | :--- |
| Schema compliance | Every file is validated against the official XSD before it is written |
| Monetary precision | Amounts flow through `decimal.Decimal` end to end — no float rounding |
| Control totals | `NbOfTxs` and `CtrlSum` are computed from the data, never trusted from input |
| Template drift | Bundled template/XSD pairs are guard-railed; mismatches fail loudly |
| XML attacks | All XML parsing goes through `defusedxml` — XXE and entity expansion are blocked |
| Agent-shaped input | Field aliases (`amount`, `currency`, `execution_date`, lower-case IBAN/BIC keys), date/boolean coercion, and computed totals let naturally-written records validate first try |
| Large batches | Streaming mode chunks input and emits one file per chunk |
| Scheme rules | `--scheme sepa-sct\|sepa-sdd\|sepa-inst\|sepa-b2b\|xborder-ct` layers per-rulebook checks on top of XSD |

Templates and schemas for every supported message type ship inside the
package — point Pain001 at your data and it resolves the rest.

---

## Install

| Channel | Command | Notes |
| :--- | :--- | :--- |
| PyPI | `pip install pain001` | Core library and CLI |
| PyPI + REST API | `pip install "pain001[api]"` | Adds FastAPI + Uvicorn server |
| PyPI + Parquet | `pip install "pain001[parquet]"` | Adds PyArrow for Parquet input |
| PyPI + Redis | `pip install "pain001[redis]"` | Distributed job store + rate limiter |
| PyPI + MCP | `pip install "pain001[mcp]"` | In-tree MCP server for LLM clients |
| PyPI + LSP | `pip install "pain001[lsp]"` | In-tree language server for CSV diagnostics |
| Source | `git clone https://github.com/sebastienrousseau/pain001 && cd pain001 && poetry install` | For development |
| Docker (GHCR) | `docker pull ghcr.io/sebastienrousseau/pain001:latest` | Multi-arch (linux/amd64, linux/arm64); CLI + `api` extra preinstalled |

Requires Python 3.10 or later.

### Docker

The image ships the CLI and the `api` extra so the REST surface works
out of the box:

```bash
# CLI: generate a payment file
docker run --rm -v "$PWD:/data" -w /data \
  ghcr.io/sebastienrousseau/pain001:latest \
  generate -t pain.001.001.03 -d payments.csv -o out.xml

# REST API: launch the server
docker run --rm -p 8000:8000 \
  ghcr.io/sebastienrousseau/pain001:latest \
  serve --host 0.0.0.0 --port 8000
```

The image runs as a non-root `pain001` user; bind-mount the directory
you want the CLI to read or write.

---

## Quick start

`-t` (message type) and `-d` (data file) are the only required flags —
the template and XSD auto-resolve from the bundled registry:

```bash
pain001 -t pain.001.001.03 -d payments.csv
# -> writes pain.001.001.03.xml in the current directory (override with -o)
```

Override the template or schema only when you need a customised one:

```bash
pain001 -t pain.001.001.03 -m my-template.xml -s my-schema.xsd -d payments.csv
```

Validate without generating anything (CI pre-flight) — here the
template and schema are auto-resolved from the bundled registry:

```bash
pain001 -t pain.001.001.03 -d payments.csv --dry-run
# -> exit 0 if the data would generate a valid file, 1 otherwise
```

Exit codes: `0` success, `1` validation or processing error, `2` invalid
arguments.

### One binary, a whole workflow

`pain001` is a command suite. A bare invocation (or `pain001 generate …`)
still produces XML exactly as before — every flag above is unchanged — and
the sibling subcommands cover the rest of the lifecycle:

| Command | Purpose |
| :--- | :--- |
| `pain001 generate …` | Generate payment XML (default; accepts bare flags for backwards compatibility) |
| `pain001 validate -t … -d …` | Validate data without generating XML — a named `--dry-run` for CI pre-flight |
| `pain001 versions [--json]` | List the supported ISO 20022 message types |
| `pain001 inspect <type> [--json]` | Show a bundled template's schema, category, and accepted formats |
| `pain001 init <type> [-o file]` | Scaffold a starter CSV from the bundled example |
| `pain001 serve [--host --port]` | Launch the REST API (requires `pain001[api]`) |
| `pain001 mcp` | Launch the in-tree MCP server over stdio (requires `pain001[mcp]`) |

```bash
pain001 init pain.001.001.03 -o my-payments.csv         # scaffold a starter CSV
pain001 validate -t pain.001.001.03 -d my-payments.csv  # pre-flight in CI
pain001 generate -t pain.001.001.03 -d my-payments.csv  # ship it
```

---

## Supported messages

| Message type | Description |
| :--- | :--- |
| `pain.001.001.03` – `pain.001.001.12` | Customer Credit Transfer Initiation, all ten ISO 20022 versions |
| `pain.008.001.02` | Customer Direct Debit Initiation |

Each bundled message type ships with a Jinja2 template, the official XSD
schema, and registry metadata. List them from the CLI:

```bash
pain001 versions                 # supported message types
pain001 inspect pain.001.001.12  # template + schema + accepted formats
```

Related tooling included in the package:

- **Version migration** — map payment data between pain.001 versions via
  `pain001.migration.VersionMapper().migrate_rows(rows, from_v, to_v)`.
- **pain.002 parser + builder** — read the payment status reports your bank
  sends back, and `build_pain002_report(...)` to generate one (e.g. to
  simulate a bank in tests); the two round-trip.
- **camt.053 parser** — read end-of-day bank statements.

---

## Input formats

| Format | Extension | Notes |
| :--- | :--- | :--- |
| CSV | `.csv` | Header row maps columns to template fields |
| SQLite | `.db`, `.sqlite` | Reads from a named table you specify (set the table via `--config`) |
| JSON | `.json` | Array of payment objects |
| JSON Lines | `.jsonl` | One payment object per line |
| Parquet | `.parquet` | Requires the `parquet` extra |

All loaders normalise into the same internal representation, so the rest
of the pipeline — validation, totals, rendering — is identical regardless
of source.

---

## Usage

<details>
<summary><b>CLI reference</b></summary>

These are the options of the `generate` command (the default), so they
apply equally to `pain001 …` and `pain001 generate …`:

```text
pain001 [generate] [OPTIONS]

  -t, --xml-message-type   ISO 20022 message type (e.g. pain.001.001.03)
  -m, --template           Jinja2 XML template (auto-resolved when omitted)
  -s, --schema             XSD schema for validation (auto-resolved when omitted)
  -d, --data               Payment data file (CSV, SQLite, JSON, JSONL, Parquet)
  -c, --config             Configuration file (YAML, TOML, or INI)
  -o, --output-dir         Output directory (default: current directory)
      --dry-run            Validate inputs without generating XML
      --streaming          Process input in chunks, one XML file per chunk
      --chunk-size         Rows per streaming chunk (default: 1000)
      --profile            Configuration profile or built-in preset
      --show-config        Print the resolved configuration and exit
      --emit-metrics       Emit timing and lifecycle metrics to stdout
      --scheme             Validate rows against a scheme rulebook
                           (sepa-sct, sepa-sdd, sepa-inst, sepa-b2b, xborder-ct)
      --explain            With --scheme, print a remediation hint per finding
      --scheme-format      Scheme output format: text (default) or json
  -v, --verbose            Detailed logging output
  -h, --help               Show help and exit
```

</details>

<details>
<summary><b>Scheme-aware validation (SEPA + cross-border)</b></summary>

XSD validation proves a file is *well-formed*; it does not prove the
payment obeys the rules of the scheme it will clear through. `--scheme`
layers a rulebook on top of XSD validation and reports structured,
per-row violations:

```bash
pain001 -t pain.001.001.03 -d payments.csv --scheme sepa-sct --dry-run
```

Five profiles ship today — `sepa-sct` (SEPA Credit Transfer, pain.001),
`sepa-sdd` (SEPA Direct Debit, pain.008), `sepa-inst` (SEPA Instant
Credit Transfer, pain.001), `sepa-b2b` (SEPA Business-to-Business Direct
Debit, FRST/RCUR-only + mandatory creditor identifier), and `xborder-ct`
(generic cross-border, multi-currency, BIC-mandatory). Each profile
checks currency, valid debtor/creditor IBANs (ISO 13616 / mod-97), BICs,
the amount ceiling (100,000 EUR instant cap for `sepa-inst`), ISO 20022
character-set and field-length limits, and (for SDD/B2B) mandate id and
sequence type. Add `--explain` for remediation hints, or
`--scheme-format json` for machine-readable output. The REST API accepts
a `scheme` field on `/api/v1/validate` and `/api/v1/generate` too. See
[SCHEMES.md](SCHEMES.md) for the full rule catalogue. From Python:

```python
from pain001 import validate_scheme

rows = [{
    "payment_currency": "USD",                       # not EUR -> SEPA-CCY
    "debtor_account_IBAN": "DE89370400440532013000",
    "creditor_account_IBAN": "FR1420041010050500013M02606",
    "payment_amount": "100.00",
}]

result = validate_scheme(rows, profile="sepa-sct")
print(result.is_valid)             # -> False
for v in result.violations:
    print(v.rule, v.field, v.message)
    # -> SEPA-CCY payment_currency Currency must be EUR for sepa-sct
```

Need to clean spreadsheet text first? `sanitize_to_charset` transliterates
to the ISO 20022 set (`Café` → `Cafe`).

</details>

<details>
<summary><b>Dry-run validation in CI</b></summary>

`--dry-run` runs the full validation pipeline — file existence, schema
resolution, data loading, field checks — and stops before XML generation.
It is designed as a pre-flight gate:

```bash
pain001 -t pain.001.001.03 -d payments.csv --dry-run || exit 1
```

Exit code `0` means the data would generate a valid file; `1` means it
would not, with the failures printed.

</details>

<details>
<summary><b>Streaming large batches</b></summary>

For batches too large to hold in memory, streaming mode chunks the input
and writes one XML file per chunk, each with its own computed `NbOfTxs`
and `CtrlSum`:

```bash
pain001 -t pain.001.001.03 -d payments.csv --streaming --chunk-size 500
```

</details>

<details>
<summary><b>Input normalization — records the way agents write them</b></summary>

The generate path accepts payment records the way people (and LLM
agents) naturally write them, and normalizes everything into the
canonical pain.001 shape before rendering:

- **Field aliases** — `amount` / `instructed_amount` map to
  `payment_amount`, `currency` and `payment_currency` mirror each
  other, `execution_date` maps to `requested_execution_date`, and
  lower-case identifier keys (`debtor_account_iban`,
  `creditor_agent_bic`, …) are canonicalized to their upper-case
  spellings. An alias never overwrites an explicitly-provided
  canonical value.
- **Boolean coercion** — Python/JSON booleans and `"True"`/`"FALSE"`
  strings render in XSD form (`"true"`/`"false"`).
- **Date coercion** — each temporal field is coerced to the lexical
  form its XSD type requires: a bare `date` of `2026-07-18` becomes
  `2026-07-18T00:00:00` (xs:dateTime), while a full datetime in
  `requested_execution_date` or `reference_date` is truncated to its
  date part (xs:date).
- **Computed totals** — `nb_of_txs` and `ctrl_sum` are always computed
  from the rows themselves (caller-supplied values are overwritten),
  so the header totals never have to be provided by hand.
- **All-at-once field errors** — missing required fields raise a
  single `PaymentValidationError` that lists every missing header
  field and every missing per-transaction field with its row number,
  so one retry fixes everything instead of one `KeyError` per attempt.
- **XSD errors with element paths** — when generated XML fails schema
  validation, the error reports every violation as element path plus
  reason (capped at 20) instead of an opaque pass/fail.
- **Conditional `SplmtryData`** — the pain.001.001.09–12 templates
  emit a `SplmtryData` block only when a record provides
  `supplementary_data`; nothing is emitted by default.

The same normalization is available standalone:

```python
from pain001 import canonicalize_payment_record, normalize_payment_records

rows = normalize_payment_records([{
    "id": "MSG-1", "date": "2026-07-18",
    "initiator_name": "ACME Corp",
    "payment_id": "PMT-1", "execution_date": "2026-07-21",
    "debtor_name": "ACME Corp",
    "debtor_account_iban": "DE89370400440532013000",
    "debtor_agent_bic": "DEUTDEFF",
    "amount": 1234.5, "currency": "EUR",
    "creditor_name": "Supplier GmbH",
    "creditor_account_iban": "FR1420041010050500013M02606",
    "creditor_agent_bic": "BNPAFRPP",
}])
# rows[0]["payment_amount"] -> "1234.50"; nb_of_txs / ctrl_sum are set.
```

`normalize_payment_records` reformats values (amounts, dates,
booleans) and computes the totals; `canonicalize_payment_record` only
maps alias keys to canonical names, preserving value types — use it
when records must still pass JSON-Schema validation with typed values.

</details>

<details>
<summary><b>REST API</b></summary>

Install the `api` extra and start the server:

```bash
pip install "pain001[api]"
pain001 serve --host 0.0.0.0 --port 8000   # or: uvicorn pain001.api.app:app
```

Endpoints are versioned under `/api/v1`; the unversioned `/api/*` paths
remain as a backwards-compatible alias.

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Liveness check |
| `POST` | `/api/v1/validate` | Validate payment data without generating |
| `POST` | `/api/v1/generate` | Generate a payment file synchronously |
| `POST` | `/api/v1/generate/async` | Queue generation as a background job |
| `GET` | `/api/v1/status/{job_id}` | Poll an async job |
| `GET` | `/api/v1/download/{job_id}` | Download a finished file |
| `DELETE` | `/api/v1/jobs/{job_id}` | Cancel or clean up a job |

**Operational controls** (all environment-driven, all off by default):

| Variable | Effect |
| :--- | :--- |
| `PAIN001_API_KEY` | Require `Authorization: Bearer <key>` on every endpoint |
| `PAIN001_RATE_LIMIT` | Per-client cap (e.g. `100/minute`); pair with `PAIN001_RATE_LIMIT_BACKEND=redis` for cross-replica enforcement |
| `PAIN001_RATE_LIMIT_BACKEND` | `memory` (default, in-process) or `redis` |
| `PAIN001_RATE_LIMIT_REDIS_URL` | Redis URL for the distributed limiter (falls back to `PAIN001_JOB_STORE_URL` if unset) |
| `PAIN001_JOB_STORE_DIR` | Persist async jobs to disk so they survive restarts |
| `PAIN001_JOB_STORE_URL` | Redis URL for a fully distributed job store (use instead of `_DIR`) |

**Documentation surfaces:** Swagger UI at `/api/docs`, ReDoc at
`/api/redoc`, an interactive [Scalar](https://scalar.com) reference at
`/api/reference`, and the raw OpenAPI document at `/openapi.json`. The
same reference is hosted publicly:
<https://sebastienrousseau.github.io/pain001/api-reference.html>.

**Operability:** liveness probe at `/api/v1/health` and Prometheus metrics
at `/metrics` (build info, supported-type/scheme gauges, per-status job
gauges, and HTTP request counters). See [OPERATIONS.md](OPERATIONS.md)
for the runbook — config, scrape config, alerts, scaling, and incident
playbook.

**Client SDKs** — generate a typed client in any language from the
OpenAPI document:

```bash
python scripts/export_openapi.py openapi.json      # dump the schema
npx @openapitools/openapi-generator-cli generate \
    -i openapi.json -g python -o ./pain001-client   # or -g typescript-axios, go, ...
```

</details>

<details>
<summary><b>Python API — generate in memory (serverless)</b></summary>

For Lambdas, APIs, and queues, `generate_xml_string` returns the
validated XML as a string instead of writing to disk. This snippet is
fully self-contained — it uses the template, schema, and sample data
that ship *inside* the package, so it runs as-is with no external files:

```python
from pain001 import generate_xml_string
from pain001.constants import TEMPLATES_DIR
from pain001.csv.load_csv_data import load_csv_data

message_type = "pain.001.001.03"
bundled = TEMPLATES_DIR / message_type  # templates ship inside the package

# Load the bundled sample dataset; swap in your own list[dict] of rows.
payments = load_csv_data(str(bundled / "template.csv"))

xml = generate_xml_string(
    payments,
    message_type,
    str(bundled / "template.xml"),
    str(bundled / f"{message_type}.xsd"),
)

# `xml` is validated ISO 20022 XML, ready to return from a handler.
print(xml[:38])  # -> <?xml version="1.0" encoding="UTF-8"?>
```

</details>

<details>
<summary><b>Python API — generate to a file</b></summary>

`process_files` loads your data, renders the template, validates against
the XSD, and writes the file — returning the path it wrote:

```python
from pain001.core.core import process_files

output_path = process_files(
    xml_message_type="pain.001.001.03",
    xml_template_file_path="template.xml",
    xsd_schema_file_path="schema.xsd",
    data_file_path="payments.csv",  # path, or a list[dict] of payment rows
)

print(output_path)  # -> "pain.001.001.03.xml" — validated and on disk
```

</details>

---

## Companion packages

Pain001 ships **two interchangeable install paths** for both its MCP and
LSP integrations: an *in-tree* implementation that comes with `pain001`
itself (smaller feature set, no extra package), and a *standalone* PyPI
package (richer surface, independently versioned).

### MCP server

A [Model Context Protocol](https://modelcontextprotocol.io) server lets
AI agents call Pain001 as first-class tools.

- **In-tree** (`pip install "pain001[mcp]"`, run `pain001 mcp` or
  `pain001-mcp-builtin`): the original server in `pain001.mcp.server`.
  Tools include `list_supported_versions`, `inspect_template`,
  `generate_payment_file`, `validate_payment_data`, plus a
  `pain001://schema/{message_type}` resource and a `build_payment_batch`
  prompt.
- **Standalone** (`pip install pain001-mcp`, run `pain001-mcp`): the
  [`pain001-mcp`](https://github.com/sebastienrousseau/pain001-mcp)
  companion package — **seventeen tools** including everything in-tree
  plus `validate_records`, `validate_identifier` (IBAN/BIC),
  `generate_message`, `generate_message_async`,
  `generate_message_from_file`, `list_supported_formats`,
  `parse_camt053`, `parse_pain002`, `migrate_records` (cross-version
  pain.001 mapping), `validate_xml_against_schema` (in-memory XSD
  validation), and `sanitize_to_iso20022_charset` (ISO 20022 Latin
  transliteration).

Register either with any MCP client (e.g. Claude Desktop):

```json
{
  "mcpServers": {
    "pain001": { "command": "pain001-mcp" }
  }
}
```

(Use `pain001-mcp-builtin` for the in-tree variant.)

### Language Server (LSP)

A [pygls](https://github.com/openlawlibrary/pygls)-based Language Server
brings real-time help to editors.

- **In-tree** (`pip install "pain001[lsp]"`, run `pain001-lsp-builtin`):
  diagnostics for **payment CSV files** (invalid IBAN/BIC/currency cells,
  characters outside the ISO 20022 Latin set, missing required columns).
- **Standalone** (`pip install pain001-lsp`, run `pain001-lsp`): the
  [`pain001-lsp`](https://github.com/sebastienrousseau/pain001-lsp)
  companion package — **six features** for **payment-data JSON files**:
  diagnostics, completion, hover, a multi-record "add missing required
  fields" code action, two-space JSON formatting
  (`textDocument/formatting`), and a record-outline pane
  (`textDocument/documentSymbol`). Supports startup
  (`initializationOptions.messageType`) and live
  (`workspace/didChangeConfiguration`) message-type overrides.

Point your editor's LSP client at the `pain001-lsp` (standalone) or
`pain001-lsp-builtin` (in-tree) command for the appropriate file type.

---

## Production users

Pain001 is open-source under Apache-2.0 / MIT and used in
production across embedded-finance, treasury-ops, and
SEPA-clearing pipelines.

**Are you using pain001 in production?**
[Open a one-line issue](https://github.com/sebastienrousseau/pain001/issues/new?title=Production+user:+%5BYour+org%5D&body=One-line%20description%20of%20how%20you%20use%20pain001%2C%20plus%20a%20link%20%2F%20logo%20if%20you%27re%20happy%20to%20be%20publicly%20listed.%0A%0AOr%20just%20a%20%2B1%20if%20you%27d%20rather%20stay%20anonymous%20%E2%80%94%20we%27ll%20count%20you%20in%20the%20aggregate%20without%20publishing%20a%20name.)
and we'll add you here. Public listing is opt-in; if you'd prefer
to stay anonymous, a "+1" still counts toward the aggregate metric
below and helps future adopters make their case internally.

**Known integrators** (open an issue to be added):

- _Be the first._ Three logos on this list materially changes how
  later adopters evaluate the project; if pain001 makes your team's
  life easier, your name here is the highest-leverage thanks you
  can give back.

**Aggregate signals** (auto-updating):

- [PyPI downloads](https://pypistats.org/packages/pain001) (`pain001` + companions)
- [GitHub stars](https://github.com/sebastienrousseau/pain001/stargazers) across the suite
- [Awesome-list entries](#) (in flight; tracked in [`scripts/awesome-list-submissions.md`](scripts/awesome-list-submissions.md))

If you'd like to write up your integration as a public case study,
we'd love that — but a logo or a +1 is plenty.

---

## When not to use Pain001

- **You need message types beyond pain.001 / pain.008 generation.** The
  camt.053 and pain.002 modules are parsers, not generators; other ISO
  20022 families (camt.052, pacs.*) are out of scope.
- **You need bank connectivity.** Pain001 produces and validates files;
  it does not transmit them. Pair it with your EBICS/SFTP/API channel.
- **Your data model is wildly non-tabular.** The loaders expect
  row-shaped payment records. Deeply nested custom structures need
  flattening first.

---

## Development

```bash
git clone https://github.com/sebastienrousseau/pain001
cd pain001
poetry install --with dev
```

The quality model is zero-trust: every gate runs locally and in CI, and
the build fails if any regress.

| Target | What it runs |
| :--- | :--- |
| `make lint` | Ruff lint + format check + interrogate + pydoclint |
| `make type` | mypy in `--strict` mode |
| `make test` | Full pytest suite with branch-coverage gate |
| `make sec` | Bandit + pip-audit dependency audit |
| `make perf` | pytest-benchmark performance suite |
| `make mutate` | Mutation testing via mutmut |
| `make check` | lint + coverage + security in one pass |
| `make tollgates` | Dependency, XSD, idempotency, and env-parity gates |

CI workflows:

| Workflow | Purpose |
| :--- | :--- |
| `ci.yml` | Test matrix on Python 3.10 / 3.11 / 3.12 |
| `quality.yml` | Lint, types, complexity |
| `security.yml` | Bandit + pip-audit + dependency review |
| `codeql.yml` | Static analysis |
| `docker.yml` | Multi-arch GHCR image build + smoke test |
| `sdk.yml` | OpenAPI SDK generation + drift guard |
| `nightly.yml` | Extended nightly suite |
| `pr.yml` | Pull-request gate |
| `docs.yml` | Build and deploy documentation |

Current state (v0.0.57): **1,425 tests passing**, **100% line + branch
coverage** against a **100% enforced floor**, mypy `--strict` clean,
100% docstring coverage (interrogate). Coverage excludes only
entry-point guards and genuinely-defensive barriers via
`# pragma: no cover`; everything else is exercised.

---

## Security

Pain001 treats payment data as hostile until proven otherwise:

- **XML parsing** is routed through `defusedxml`; XXE, billion-laughs,
  and external entity resolution are rejected.
- **Path handling** goes through a path validator that blocks traversal
  outside permitted directories.
- **Schema validation** is mandatory — output that does not validate
  against the official XSD is never written as a success.
- **Amounts** are `Decimal` throughout; control sums are recomputed,
  not echoed from input.
- **Dependencies** are pinned via `poetry.lock` and audited by
  `pip-audit`, Bandit, and CodeQL in CI.

To report a vulnerability, please use
[GitHub private vulnerability reporting](https://github.com/sebastienrousseau/pain001/security)
rather than a public issue.

---

## Documentation

- **Guides & API reference:** [docs.pain001.com](https://docs.pain001.com)
- **Runnable examples:** [`examples/`](https://github.com/sebastienrousseau/pain001/tree/main/examples) — one self-checking script per feature (generation, every input format, CLI, REST API, scheme validation, parsers, migration, streaming, observability, MCP), all executed in CI
- **Bundled templates & schemas:** [`pain001/templates/`](https://github.com/sebastienrousseau/pain001/tree/main/pain001/templates)
- **Scheme validation rules:** [SCHEMES.md](https://github.com/sebastienrousseau/pain001/blob/main/SCHEMES.md)
- **Architecture & module map:** [ARCHITECTURE.md](https://github.com/sebastienrousseau/pain001/blob/main/ARCHITECTURE.md)
- **Release process:** [RELEASING.md](https://github.com/sebastienrousseau/pain001/blob/main/RELEASING.md)
- **Release history:** [CHANGELOG.md](https://github.com/sebastienrousseau/pain001/blob/main/CHANGELOG.md)

---

## Contributing

Contributions are welcome — see the
[contributing instructions](https://github.com/sebastienrousseau/pain001/blob/main/CONTRIBUTING.md),
how the project is run in [GOVERNANCE.md](GOVERNANCE.md), the
[architecture map](ARCHITECTURE.md), and where the project is headed in
the [ROADMAP.md](ROADMAP.md). Need help? See [SUPPORT.md](SUPPORT.md).
Unless you explicitly state otherwise, any contribution you submit is
dual-licensed as below, without additional terms or conditions.

**Maintainers wanted.** Pain001 has a single maintainer today; that is
the project's main risk. If you rely on it and can help review, triage,
or co-maintain an area, see
[becoming a maintainer](GOVERNANCE.md#becoming-a-maintainer).

Thanks to all the [contributors](https://github.com/sebastienrousseau/pain001/graphs/contributors)
who have helped build Pain001.

---

## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](https://opensource.org/license/apache-2-0/))
- MIT license ([LICENSE-MIT](http://opensource.org/licenses/MIT))

at your option. See
[CHANGELOG.md](https://github.com/sebastienrousseau/pain001/blob/main/CHANGELOG.md)
for release history.

---

<p align="center">
  <a href="https://pain001.com">pain001.com</a> ·
  <a href="https://docs.pain001.com">docs.pain001.com</a> ·
  <a href="https://pypi.org/project/pain001/">PyPI</a>
</p>
