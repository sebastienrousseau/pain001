[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/sebastienrousseau-pain001-badge.png)](https://mseep.ai/app/sebastienrousseau-pain001)

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
  <a href="#license"><img src="https://img.shields.io/pypi/l/pain001?style=for-the-badge" alt="Licence" /></a>
</p>

---

## Contents

**Getting started**

- [What is Pain001?](#what-is-pain001) — the problem it solves and how
- [Install](#install) — PyPI, extras, and source builds
- [Quick start](#quick-start) — one command from CSV to validated XML

**Library reference**

- [Supported messages](#supported-messages) — every bundled ISO 20022 message type
- [Input formats](#input-formats) — CSV, SQLite, JSON, JSONL, Parquet
- [Usage](#usage) — CLI, dry-run, streaming, REST API, Python API
- [When not to use Pain001](#when-not-to-use-pain001) — honest boundaries

**Operational**

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
| Large batches | Streaming mode chunks input and emits one file per chunk |

Templates and schemas for every supported message type ship inside the
package — point Pain001 at your data and it resolves the rest.

---

## Install

| Channel | Command | Notes |
| :--- | :--- | :--- |
| PyPI | `pip install pain001` | Core library and CLI |
| PyPI + REST API | `pip install "pain001[api]"` | Adds FastAPI + Uvicorn server |
| PyPI + Parquet | `pip install "pain001[parquet]"` | Adds PyArrow for Parquet input |
| PyPI + MCP | `pip install "pain001[mcp]"` | Adds the MCP server for LLM clients |
| PyPI + LSP | `pip install "pain001[lsp]"` | Adds the `pain001-lsp` language server for editor diagnostics |
| Source | `git clone https://github.com/sebastienrousseau/pain001 && cd pain001 && poetry install` | For development |

Requires Python 3.10 or later.

---

## Quick start

```bash
pain001 -t pain.001.001.03 -m template.xml -s schema.xsd -d payments.csv
```

The generated XML is validated against the XSD schema and written
to the current directory (override with `-o`). Grab a template and
schema for any supported
version from the
[bundled templates](https://github.com/sebastienrousseau/pain001/tree/main/pain001/templates),
or point `-m`/`-s` at your own.

Validate without generating anything (CI pre-flight) — here the
template and schema are auto-resolved from the bundled registry:

```bash
pain001 -t pain.001.001.03 -d payments.csv --dry-run
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
| `pain001 mcp` | Launch the MCP server over stdio (requires `pain001[mcp]`) |

```bash
pain001 init pain.001.001.03 -o my-payments.csv   # scaffold
pain001 validate -t pain.001.001.03 -d my-payments.csv   # pre-flight
pain001 generate -t pain.001.001.03 -d my-payments.csv   # ship it
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
pain001 --list-templates
pain001 --show-template pain.001.001.12
```

Related tooling included in the package:

- **Version migration** — map payment data between pain.001 versions
  (`python -m pain001.migrate`).
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
      --list-templates     List bundled templates and exit
      --show-template      Show metadata for one bundled template and exit
      --emit-metrics       Emit timing and lifecycle metrics to stdout
      --scheme             Validate rows against a scheme rulebook
                           (sepa-sct, sepa-sdd)
      --explain            With --scheme, print a remediation hint per finding
      --scheme-format      Scheme output format: text (default) or json
  -v, --verbose            Detailed logging output
  -h, --help               Show help and exit
```

</details>

<details>
<summary><b>Scheme-aware validation (SEPA)</b></summary>

XSD validation proves a file is *well-formed*; it does not prove the
payment obeys the rules of the scheme it will clear through. `--scheme`
layers a rulebook on top of XSD validation and reports structured,
per-row violations:

```bash
pain001 -t pain.001.001.03 -d payments.csv --scheme sepa-sct --dry-run
```

Four profiles ship today — `sepa-sct` (SEPA Credit Transfer, pain.001),
`sepa-sdd` (SEPA Direct Debit, pain.008), `sepa-inst` (SEPA Instant Credit
Transfer, pain.001), and `xborder-ct` (generic cross-border, multi-currency,
BIC-mandatory) — checking currency, valid debtor/creditor IBANs (ISO 13616 /
mod-97), BICs, the amount ceiling (the 100,000 EUR instant cap for
`sepa-inst`), ISO 20022 character-set and field-length limits, and (for SDD)
mandate id and sequence type. Add `--explain` for
remediation hints, or `--scheme-format json` for machine-readable output.
The REST API accepts a `scheme` field on `/api/v1/validate` and
`/api/v1/generate` too. See [SCHEMES.md](SCHEMES.md) for the full rule
catalogue. From Python:

```python
from pain001 import validate_scheme

rows = [{
    "payment_currency": "USD",                       # not EUR -> SEPA-CCY
    "debtor_account_IBAN": "DE89370400440532013000",
    "creditor_account_IBAN": "FR1420041010050500013M02606",
    "payment_amount": "100.00",
}]

result = validate_scheme(rows, profile="sepa-sct")
print(result.is_valid)             # False
for v in result.violations:
    print(v.rule, v.field, v.message)  # SEPA-CCY payment_currency ...
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
| `PAIN001_RATE_LIMIT` | Per-client request cap, e.g. `100/minute` (in-process; use a gateway/Redis when scaled out) |
| `PAIN001_JOB_STORE_DIR` | Persist async jobs to disk so they survive restarts |

**Documentation surfaces:** Swagger UI at `/api/docs`, ReDoc at
`/api/redoc`, an interactive [Scalar](https://scalar.com) reference at
`/api/reference`, and the raw OpenAPI document at `/openapi.json`.

**Operability:** a liveness probe at `/api/v1/health` and Prometheus metrics
at `/metrics` (build info, supported-type/scheme gauges, per-status job
gauges, and HTTP request counters). See [OPERATIONS.md](OPERATIONS.md) for
the runbook — config, scrape config, alerts, scaling, and incident playbook.

**Client SDKs** — generate a typed client in any language from the OpenAPI
document:

```bash
python scripts/export_openapi.py openapi.json      # dump the schema
npx @openapitools/openapi-generator-cli generate \
    -i openapi.json -g python -o ./pain001-client   # or -g typescript-axios, go, ...
```

</details>

<details>
<summary><b>Python API — generate in memory (serverless)</b></summary>

For Lambdas, APIs, and queues, `generate_xml_string` returns the validated
XML as a string instead of writing to disk. This snippet is fully
self-contained — it uses the template, schema, and sample data that ship
*inside* the package, so it runs as-is with no external files:

```python
from pain001 import generate_xml_string
from pain001.constants import TEMPLATES_DIR
from pain001.csv.load_csv_data import load_csv_data

message_type = "pain.001.001.03"
bundled = TEMPLATES_DIR / message_type  # templates ship inside the package

# Load the bundled sample dataset; swap in your own list[dict] of rows
payments = load_csv_data(str(bundled / "template.csv"))

xml = generate_xml_string(
    payments,
    message_type,
    str(bundled / "template.xml"),
    str(bundled / f"{message_type}.xsd"),
)

# `xml` is validated ISO 20022 XML, ready to return from a handler
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

print(output_path)  # e.g. "pain.001.001.03.xml" — validated and on disk
```

</details>

<details>
<summary><b>MCP server (LLM clients)</b></summary>

Expose Pain001 to MCP-aware LLM clients (Claude Desktop, etc.) over
stdio. Install the `mcp` extra and run the server:

```bash
pip install "pain001[mcp]"
pain001-mcp
```

It exposes **tools** (`generate_payment_file`, `validate_payment_data`,
`validate_payment_scheme`, `list_supported_versions`, `inspect_template`),
a read-only **resource** (`pain001://schema/{message_type}` for the XSD),
and a guided **prompt** (`build_payment_batch`). Tools take inline rows
(a `list[dict]`) and return XML as a string — no shared filesystem
needed. Example client config:

```json
{
  "mcpServers": {
    "pain001": { "command": "pain001-mcp" }
  }
}
```

</details>

<details>
<summary><b>Editor diagnostics (LSP)</b></summary>

Get live, in-editor feedback on payment CSVs — invalid IBAN/BIC/currency
cells, characters outside the ISO 20022 Latin set, and missing required
columns — from a Language Server that reuses the same validators as the
generator:

```bash
pip install "pain001[lsp]"
pain001-lsp        # stdio language server, point your editor at this
```

A thin VS Code client lives in [`editors/vscode/`](editors/vscode/). The
diagnostic engine is dependency-free and reusable on its own (e.g. in a
pre-commit hook):

```python
from pain001.lsp import diagnostics_for_csv

for d in diagnostics_for_csv(open("payments.csv").read()):
    print(f"line {d.line + 1}: {d.code} — {d.message}")
```

</details>

---

## When not to use Pain001

- **You need message types beyond pain.001 / pain.008 generation.** The
  camt.053 and pain.002 modules are parsers, not generators; other ISO
  20022 families (camt.052, pacs.*) are out of scope.
- **You need bank connectivity.** Pain001 produces and validates files; it
  does not transmit them. Pair it with your EBICS/SFTP/API channel.
- **Your data model is wildly non-tabular.** The loaders expect row-shaped
  payment records. Deeply nested custom structures need flattening first.

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
| `make lint` | Ruff lint + format check |
| `make type` | mypy in `--strict` mode |
| `make test` | Full pytest suite with branch-coverage gate |
| `make sec` | Bandit + Safety dependency audit |
| `make perf` | pytest-benchmark performance suite |
| `make mutate` | Mutation testing via mutmut |
| `make check` | lint + coverage + security in one pass |
| `make tollgates` | Dependency, XSD, idempotency, and env-parity gates |

CI workflows:

| Workflow | Purpose |
| :--- | :--- |
| `ci.yml` | Test matrix on Python 3.10 / 3.11 / 3.12 |
| `quality.yml` | Lint, types, complexity |
| `security.yml` | Bandit, Safety, dependency review |
| `codeql.yml` | Static analysis |
| `nightly.yml` | Extended nightly suite |
| `pr.yml` | Pull-request gate |
| `docs.yml` | Build and deploy documentation |

Current state: 1,020+ tests passing, ~100% branch coverage against a **98%
enforced floor**, mypy `--strict` clean. Coverage excludes only
entry-point guards and genuinely-defensive barriers via
`# pragma: no cover`; the 98% floor leaves headroom so routine changes
don't fail CI on a single line.

---

## Security

Pain001 treats payment data as hostile until proven otherwise:

- **XML parsing** is routed through `defusedxml`; XXE, billion-laughs, and
  external entity resolution are rejected.
- **Path handling** goes through a path validator that blocks traversal
  outside permitted directories.
- **Schema validation** is mandatory — output that does not validate
  against the official XSD is never written as a success.
- **Amounts** are `Decimal` throughout; control sums are recomputed, not
  echoed from input.
- **Dependencies** are pinned via `poetry.lock` and audited by Safety,
  Bandit, and CodeQL in CI.

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
[architecture map](ARCHITECTURE.md), and where the project is headed in the
[ROADMAP.md](ROADMAP.md). Need help? See [SUPPORT.md](SUPPORT.md). Unless you
explicitly state otherwise, any contribution you submit is dual-licensed as
below, without additional terms or conditions.

**Maintainers wanted.** Pain001 has a single maintainer today; that is the
project's main risk. If you rely on it and can help review, triage, or
co-maintain an area, see [becoming a maintainer](GOVERNANCE.md#becoming-a-maintainer).

Thanks to all the [contributors](https://github.com/sebastienrousseau/pain001/graphs/contributors)
who have helped build Pain001.

---

## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](https://opensource.org/license/apache-2-0/))
- MIT license ([LICENSE-MIT](http://opensource.org/licenses/MIT))

at your option. See [CHANGELOG.md](https://github.com/sebastienrousseau/pain001/blob/main/CHANGELOG.md)
for release history.

---

<p align="center">
  <a href="https://pain001.com">pain001.com</a> ·
  <a href="https://docs.pain001.com">docs.pain001.com</a> ·
  <a href="https://pypi.org/project/pain001/">PyPI</a>
</p>
