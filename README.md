<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

<p align="center">
  <img src="https://cloudcdn.pro/pain001/v1/logos/pain001.svg" alt="Pain001 logo" width="128" />
</p>

<h1 align="center">Pain001</h1>

<p align="center">
  Generate and validate ISO 20022 payment files from tabular data.
</p>

<p align="center">
  <a href="https://github.com/sebastienrousseau/pain001/actions"><img src="https://img.shields.io/github/actions/workflow/status/sebastienrousseau/pain001/ci.yml?style=for-the-badge&logo=github" alt="Build" height="28" /></a>
  <a href="https://pypi.org/project/pain001/"><img src="https://img.shields.io/pypi/v/pain001?style=for-the-badge&color=fc8d62&logo=python" alt="Registry" height="28" /></a>
  <a href="https://sebastienrousseau.github.io/pain001/api-reference.html"><img src="https://img.shields.io/badge/docs-API?style=for-the-badge&labelColor=555555&logo=readthedocs" alt="Docs" height="28" /></a>
  <a href="https://scorecard.dev/viewer/?uri=github.com/sebastienrousseau/pain001"><img src="https://img.shields.io/ossf-scorecard/github.com/sebastienrousseau/pain001?style=for-the-badge&label=OpenSSF%20Scorecard&logo=openssf" alt="OpenSSF Scorecard" height="28" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0%20OR%20MIT-blue.svg?style=for-the-badge" alt="License: Apache-2.0 OR MIT" height="28" /></a>
  <a href="https://github.com/sebastienrousseau/pain001/blob/main/docs/POLICIES.md"><img src="https://img.shields.io/badge/Python-3.11%2B-93450a.svg?style=for-the-badge&logo=python" alt="Python 3.11 or newer" height="28" /></a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/sebastienrousseau/pain001/main/.github/demo.gif" alt="pain001 demo: write the starter payments.csv, validate it, generate an XSD-validated pain.001.001.03 file and show its group header" width="100%" />
</p>

---

## Contents

**Getting started**

- [Install](#install): PyPI, source and Docker
- [Requirements](#requirements): toolchain floor, platforms
- [Quick Start](#quick-start): scaffold, validate and generate synthetic payments

**The Pain001 ecosystem**

- [The Pain001 ecosystem](#the-pain001-ecosystem): core, MCP, LSP, loaders, scaffold, mockbank, native extension and website

**Library reference**

- [Capabilities at a glance](#capabilities-at-a-glance): the current surface by theme
- [Ecosystem comparison](#ecosystem-comparison): short matrix; full table at [`docs/COMPARISON.md`](docs/COMPARISON.md)
- [Benchmarks](#benchmarks): headline numbers; full table at [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md)
- [Features](#features): module-level capability list
- [Configuration](#configuration): core options
- [Examples](#examples): runnable example index

**Operational**

- [When not to use Pain001](#when-not-to-use-pain001): limitations
- [Development](#development): make targets, fuzzing, CI
- [Security](#security): guarantees and compliance
- [Documentation](#documentation): all reference docs
- [Stability guarantees](#stability-guarantees): SemVer axis, output stability, minimum toolchain discipline
- [License](#license)

---

## Install

### As a Python library

```bash
python -m pip install pain001
```

> **Latest release: v0.0.86**: ISO 20022 pain.001 and pain.008 files
> generated from CSV, SQLite, JSON, JSON Lines and Parquet and validated
> against the official XSD, for Python 3.11+. Each companion publication
> is verified separately by the ecosystem audit.

Optional extras: `api`, `parquet`, `redis`, `mcp`, `lsp`, `gpg`, `otel`,
`fast` (libxml2 validation), `upload` (SFTP), `rules` (CEL policies) and `sign`
(XML-DSig signing), for example `python -m pip install "pain001[rules,upload]"`.

```bash
# Development checkout
git clone https://github.com/sebastienrousseau/pain001.git
cd pain001
poetry install --all-extras --with dev,docs

# Published container (CLI and REST API)
docker pull ghcr.io/sebastienrousseau/pain001:latest
```

Docker runs as a non-root user. Mount a writable directory at `/data` and use
`-w /data`; `generate -t pain.001.001.03 -d payments.csv -o output` writes into
an output **directory**, not a filename. No distro package or standalone native
binary is claimed; see [packaging](docs/packaging.md).

---

## Requirements

Python **3.11 or newer**; CI tests Python 3.11–3.14 on Linux. Development uses
Python 3.12 and Poetry. Optional integrations require their extras and, for
GPG, the system GnuPG executable. No distro-system-Python compatibility is
claimed. See [toolchain policy](docs/POLICIES.md).

---

## Quick Start

```bash
pain001 init pain.001.001.03 -o payments.csv
pain001 validate -t pain.001.001.03 -d payments.csv
pain001 generate -t pain.001.001.03 -d payments.csv -o output
```

Run in a fresh writable directory. The scaffold uses bundled synthetic data;
replace it with your own records before a real payment workflow. Generation
validates the rendered XML against the bundled XSD before writing it. A dry run
checks data but is not a bank acceptance guarantee.

---

## The Pain001 ecosystem

All nine repositories follow one suite version; see the
[suite policy](docs/adr/0001-monotonic-versioning-and-suite-lockstep.md).
The scaffold, native extension and website joined at 0.0.82 by maintainer
decision. Each member publishes through its own channels. The
[publication audit](docs/ecosystem-publications.md) verifies every member
before a coordinated release is declared complete. Component rows below
are generated from [the publication inventory](docs/ecosystem.json).

| Component | Purpose | Use case |
| :--- | :--- | :--- |
| [pain001](https://github.com/sebastienrousseau/pain001) | Generation, validation, CLI and REST | Payment-file pipelines |
| [pain001-mcp](https://github.com/sebastienrousseau/pain001-mcp) | Model Context Protocol server | Agent tools for payment data |
| [pain001-lsp](https://github.com/sebastienrousseau/pain001-lsp) | Language Server Protocol server | Editor diagnostics for payment data |
| [pain001-loader-mt101](https://github.com/sebastienrousseau/pain001-loader-mt101) | SWIFT MT101 loader plugin | Convert supported MT101 inputs |
| [pain001-loader-xlsx](https://github.com/sebastienrousseau/pain001-loader-xlsx) | Excel loader plugin | Read .xlsx and .xlsm payment inputs |
| [pain001-mockbank](https://github.com/sebastienrousseau/pain001-mockbank) | Synthetic SFTP bank-response test service | Generate pain.002 replies in integration tests |
| [pain001-plugin-template](https://github.com/sebastienrousseau/pain001-plugin-template) | Cookiecutter plugin scaffold | Develop an external loader or validator |
| [pain001-fast](https://github.com/sebastienrousseau/pain001-fast) | Experimental native validation extension | Optional IBAN, BIC and character-set helpers |
| [pain001.com](https://github.com/sebastienrousseau/pain001.github.io) | Website and browser demo | Browse documentation and try the library |

---

## Capabilities at a glance

| Area | Capability | Status |
| :--- | :--- | :--- |
| XML output | pain.001.001.03–13 and pain.008.001.02 / .08 | Bundled XSD and golden-file tests |
| Input | CSV, SQLite, JSON, JSONL, Python records; optional Parquet and plugins | Tested loaders |
| Validation | XSD, scheme profiles including anti-duplicate, rail rules and optional CEL | Policies do not replace bank certification |
| Delivery | Explicit SFTP upload with pinned host trust | `upload` extra, added in 0.0.71 |
| Corrections | Deterministic review-only suggestions; no financial-field correction | Core and companion MCP tool, added in 0.0.71 |

---

## Ecosystem comparison

This matrix describes the repository's scope, not an independently benchmarked
comparison with competitors.

| Project | Generate payment XML | Real settlement | Synthetic bank replies |
| :--- | :---: | :---: | :---: |
| **Pain001** | Yes | No | pain.002 builder; mockbank companion |

See [`docs/COMPARISON.md`](docs/COMPARISON.md) for the evidence and complete matrix.

---

## Benchmarks

CI smoke-runs benchmarks. No hardware-independent throughput or latency promise
is made; use the generated run report for measurements.

| Scenario | Result | Environment |
| :--- | ---: | :--- |
| Generation and corpus benchmarks | Run-specific | Python, hardware and dependency versions recorded per run |

See [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md) for methodology and full results.

---

## Features

- Generate validated XML to files or in memory through `generate_xml_string`.
  Streaming produces one file per chunk with recomputed control totals.
- Check files that already exist with `pain001 check` (XSD, message rules,
  schemes; text, JSON or SARIF), at `POST /api/v1/check`, in the GitHub Action
  or as a pre-commit hook.
- Discover bundled message types with `pain001 versions` and inspect metadata
  with `pain001 inspect`. Inputs, templates and schemas are described in the
  [user guide](docs/usage.rst) and [input-column reference](docs/input-columns.md).
- Compose scheme profiles, including `anti-duplicate`; see [SCHEMES.md](SCHEMES.md).
  [CEL rules](docs/custom-rules.md) (added in 0.0.71) apply before generation through CLI
  and REST. Account currency is never inferred from an IBAN.
- Extend loaders, validators, schemes and writers through the
  [plugin contract and XLSX worked example](docs/plugins.md). Plugins run with
  the process's privileges; they are not sandboxed.
- Use [SFTP upload](docs/sftp-upload.md) explicitly; generation never sends a
  payment automatically. Host trust is checked before authentication; keys,
  OpenSSH certificates and ssh-agent keys are supported, and DSA and FIDO keys
  are refused by name.
- Wrap a document in a Business Application Header and sign it with XML-DSig
  RSA-SHA256 (`pain001[sign]`); see the [security notes](docs/security.rst)
  for what verification does and does not prove.
- Project a pain.001 into UK Open Banking, Berlin Group NextGenPSD2 or ISO 2018
  JSON with a loss report through [faces](docs/faces.md) (`pain001 face`).
- Call the pipeline from `asyncio` code with `process_files_async`,
  `generate_xml_string_async` and `validate_all_async`; see
  [async adapters](docs/async_adapters.rst).
- Request `suggest_record_fix` via MCP for review-only corrections. IBANs, BICs,
  amounts and currencies are refused, not guessed; see
  [correction decisions](docs/adr/0006-local-policies-and-safe-corrections.md).
- Parse pain.002 status reports and camt.053 statements; build synthetic
  pain.002 reports and camt.053 statements for tests. This is not a settlement
  engine.
- Run REST with `pain001 serve`, MCP with `pain001 mcp`, or the CSV language server
  with `pain001-lsp-builtin`, after installing the corresponding extras.
- Generate typed clients from `openapi.json`; see the
  [public API reference](https://sebastienrousseau.github.io/pain001/api-reference.html).
- Browse the [example corpus](docs/corpus.md), [JSON twins](docs/twins.md), and
  [message deltas](docs/message-deltas.md). Confidence/provenance records describe
  the evidence for each scenario; they do not certify a bank's acceptance.

---

## Configuration

Use `pain001 generate --help`, `pain001 upload --help`, and
`pain001 plugins --help` for the current command options rather than a copied
flag list. YAML, TOML and INI configuration and profiles are described in
[configuration](docs/configuration.rst).

`PAIN001_API_KEY` enables API authentication; configure rate limits and shared
job storage before multi-replica deployments. `PAIN001_DISABLE_PLUGINS` disables
named plugins, and `OTEL_ENABLED` enables optional tracing. See
[OPERATIONS.md](OPERATIONS.md) and the [deployment cookbook](docs/deployment-cookbook.md).
Never commit keys, credentials or real payment data.

---

## Examples

The [numbered examples](examples/) cover generation, input formats, REST (in
process and a running server), MCP, LSP, streaming, schemes, parsers, corpus
access, faces, signing, SFTP upload and the plugin CLI; CI executes them and
fails when a public API name or CLI command has no example. The Quick Start
above is also exercised directly by a documentation regression test.

---

## When not to use Pain001

- XSD validity and scheme checks do not guarantee bank acceptance, regulatory
  compliance, or settlement. Validate against your bank's authorized rules.
- EBICS, AS2, SWIFT connectivity and real settlement simulation are not provided.
  Only the explicit SFTP adapter is implemented here.
- The camt.053 builder produces synthetic test statements, not bank statements;
  unrelated ISO families are outside scope. Inputs must be row-shaped records
  or a supported plugin format.
- Third-party plugins execute arbitrary Python with your process privileges.
- The project has one maintainer; independent plugin-author validation for
  issue #179 remains outstanding. Development-branch changes are not releases.

---

## Development

```bash
poetry install --all-extras --with dev,docs
poetry run make check
poetry run make type
poetry run python scripts/render_readme.py --check
poetry run make docs
```

The coverage floor is **100% line and branch**. `make check` runs lint,
coverage, security, complexity ceilings and corpus checks; `make type` is a separate required gate.
Pull requests also run mutation testing, benchmarks, SDK and container checks.
See [DEVELOPMENT.md](DEVELOPMENT.md) for the complete gate map and
[CONTRIBUTING.md](CONTRIBUTING.md) for signed commits and DCO.

README layout is generated from the portfolio template vendored at
`docs/readme-template.md`, with evidence in `docs/readme-values.json`.
Edit the values and regenerate with `scripts/render_readme.py`; CI checks drift.
No fixed test count is advertised because it changes with the branch.

---

## Security

Report security problems privately, never in a public issue.

Untrusted inbound XML uses hardened parsing and rendered XML is XSD-validated.
The build uses locked dependencies and audited CI installation inputs. Actions
are SHA-pinned except the explicitly accepted SLSA generator `v2.1.0` references
required for upstream provenance verification; see the [security audit](docs/code-scanning-audit.md).
Atheris and Hypothesis exercise validation paths; no OSS-Fuzz integration is claimed.

The maintainer-approved solo workflow requires PRs, status checks, conversation
resolution and administrator enforcement, but zero mandatory approving reviews
and no mandatory CODEOWNER approval. This is not independent review and does not
resolve historical review findings. See [governance](GOVERNANCE.md).

Report vulnerabilities according to [`SECURITY.md`](SECURITY.md).

---

## Documentation

[What is pain.001?](https://pain001.com/pain-001/) ·
[User manual](https://docs.pain001.com) ·
[API reference](https://sebastienrousseau.github.io/pain001/api-reference.html) ·
[Developer guide](DEVELOPMENT.md) ·
[Ecosystem map](#the-pain001-ecosystem)

Also see [architecture](ARCHITECTURE.md), [support](SUPPORT.md),
[release process](RELEASING.md), [changelog](CHANGELOG.md),
[issue acceptance](docs/issue-audit.md) and [security audit](docs/code-scanning-audit.md).

---

## Stability guarantees

Versions advance one step at a time on the `0.0.x` line, with `0.1.0` after
`0.0.999`; only the maintainer opens a release. The current release
is 0.0.86; publication requires approved release PRs and signed release tags.

Generated XML changes for identical input, required fields, CLI/REST/MCP
contracts and plugin contracts are breaking changes. They must be announced
one release ahead; deprecated interfaces remain for at least one release with
a warning. Golden files guard byte-exact output. Coordinated suite releases
follow [ADR-0001](docs/adr/0001-monotonic-versioning-and-suite-lockstep.md).
Toolchain changes follow [ADR-0004](docs/adr/0004-python-floor-policy.md), not
incidental dependency updates.

---

## License

Dual-licensed under [Apache-2.0](LICENSE-APACHE) OR [MIT](LICENSE-MIT), at your
option. See [LICENSE](LICENSE). Dependencies retain their own licences.
