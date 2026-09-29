<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Pain001 Roadmap

## Mission

A robust, secure, high-performance ISO 20022 payment library with a
small, well-tested core, first-class developer surfaces (library, CLI,
REST, MCP, LSP), and a formal plugin contract so the ecosystem can
extend it without forking.

## Where we are (v0.0.72 shipped 2026-09-28; v0.0.73 in progress)

- **Generation:** pain.001.001.03 to .13, pain.008.001.02 and .08,
  registry-driven, `Decimal` end-to-end, mandatory XSD validation
  (XXE-safe via `defusedxml`), ISO 20022 Business Application Header
  (BAH `head.001.001.03` / `head.003.001.01`), XML Digital Signatures
  (XML-DSig RSA-SHA256), and streaming XML chunk generation.
- **Validation:** ISO 20022 Schematron business rule evaluator for
  EPC/SEPA, CBPR+, and FedNow rulebooks; native acceleration hooks
  integrating `pain001-fast` for sub-25ns financial validation; six scheme
  rulebooks — `sepa-sct`, `sepa-sdd`, `sepa-inst`, `sepa-b2b`,
  `xborder-ct`, and `anti-duplicate`, composable as
  `--scheme sepa-sct,anti-duplicate`; 18 rail profiles and 5 purpose
  mandates; memoized IBAN / BIC validators; formula injection shielding
  across batch and streaming CSV ingestion (CWE-1236).
- **Custom policy & safe corrections:** Request-local CEL policy rules
  (`pain001 --rules my-policy.yaml`) for CLI and REST
  validation/generation via optional `rules` extra (#184); deterministic,
  review-only record correction suggestions that never modify account
  identifiers, amounts, or currencies (#185).
- **End-to-end transport:** Explicit SFTP upload (`pain001 upload --sftp`)
  with trusted host keys, staged publication, hash-based retry reuse,
  and optional `upload` dependencies (#186); `pain001-mockbank` Docker
  companion service with multi-arch edge image on GHCR for sub-second
  ACCP/RJCT round-trip testing (#187).
- **Example corpus & twins:** 100% schema coverage across all 13 bundled
  XSDs (ADR-0003); 42 bank-ready market scenarios and 238 market files
  with confidence chips; ISO JSON twins following ISO 20022 RA 2025
  conventions with byte-stable JSON Schema 2020-12 per edition; records
  twin with column gap analysis (ADR-0005).
- **Plugins (v0.0.56, v0.0.60):** `pain001.plugins` publishes
  `AbstractLoader` / `AbstractValidator` / `AbstractScheme` /
  `AbstractWriter`, entry-point discovery, `pain001 plugins list`, and
  the built-ins registered through the same contract external authors
  use. External plugins: `pain001-loader-xlsx`, `pain001-loader-mt101`;
  scaffold: `pain001-plugin-template`.
- **Parsers:** pain.002 status reports + camt.053 statements, plus
  `build_pain002_report` for round-trip testing.
- **Inputs:** CSV, SQLite, JSON, JSON Lines, Parquet, and GPG-encrypted
  wrappers of any of them (`pain001[gpg]`, `--decrypt-key`); streaming
  for large batches; cross-version migration between pain.001 versions.
- **Surfaces:** CLI command suite (`generate`, `validate`, `versions`,
  `inspect`, `init`, `serve`, `mcp`, `upload`); REST `/api/v1`
  (auth, rate limiting, durable jobs, OpenAPI/Scalar, Prometheus
  `/metrics`) plus single-file browser dashboard at `/api/v1/ui`
  (v0.0.66); MCP server (16 tools); LSP server with editor diagnostics.
- **Observability & Metrics:** Prometheus metrics engine on `/metrics`
  with transaction and latency quantiles; OpenTelemetry spans via
  `pain001[otel]` and `OTEL_ENABLED=true` for generator, scheme checks,
  and REST handlers.
- **Distributed backends:** Redis-backed job store and rate limiter so
  multi-replica deployments share state and enforce caps.
- **Distribution & Provenance:** Official multi-arch Docker image at
  `ghcr.io/sebastienrousseau/pain001`, OpenAPI client SDK pipeline with
  drift-guard CI, SLSA Level 3 attestations, hash-locked dependencies.
- **Quality:** **3,305 tests**, **100% line + branch coverage (100%
  enforced floor)**, `mypy --strict`, 100% docstring coverage,
  ruff + pydoclint + bandit clean, CodeQL + pip-audit clean, every
  example exercised in CI.

Everything in the prior roadmap shipped. Focus now shifts to
**faces and projections (UK Open Banking, Berlin Group, ISO 2018)**,
**inbound twin deserialization**, **mutation test floor hardening**,
and **project sustainability / ecosystem discovery**.

## Suite

The suite all moves together; sibling packages release at matching
version numbers.

| Package | Role | Latest |
| :--- | :--- | :--- |
| [`pain001`](https://pypi.org/project/pain001/) | Core library + CLI + REST API | 0.0.72 |
| [`pain001-mcp`](https://pypi.org/project/pain001-mcp/) | Model Context Protocol server (16 tools) | 0.0.72 |
| [`pain001-lsp`](https://pypi.org/project/pain001-lsp/) | Language Server Protocol server (6 features) | 0.0.72 |
| [`pain001-loader-xlsx`](https://pypi.org/project/pain001-loader-xlsx/) | Excel (.xlsx) loader plugin | 0.0.72 |
| [`pain001-loader-mt101`](https://pypi.org/project/pain001-loader-mt101/) | SWIFT MT101 loader plugin | 0.0.72 |
| [`pain001-plugin-template`](https://github.com/sebastienrousseau/pain001-plugin-template) | Cookiecutter scaffold for external plugins | 0.0.1 (unreleased) |
| [`pain001-mockbank`](https://github.com/sebastienrousseau/pain001-mockbank) | Synthetic SFTP bank response test service | 0.0.1 (edge image) |

## Planned releases

Issue links go to the canonical specs filed at
[`pain001` issues](https://github.com/sebastienrousseau/pain001/issues).
A ✅ marks an item that has shipped, with the release that carried it.

### Plugin substrate + table-stakes formats *(shipped: v0.0.56 → v0.0.66)*

Foundation release. Every subsequent format and validator becomes a
first-class plugin, so the contract has to land *before* those
features ship. Also addresses the single-maintainer risk by letting
the ecosystem extend pain001 without merging through the upstream.

| Issue | Item | Effort |
| :--- | :--- | :--- |
| [#179](https://github.com/sebastienrousseau/pain001/issues/179) | **Plugin architecture** — `AbstractLoader`, `AbstractValidator`, `AbstractScheme`, `AbstractWriter` Protocols; entry-point discovery; `pain001 plugins list` CLI | ✅ v0.0.56 (substrate), v0.0.60 (built-ins as plugins), `pain001-plugin-template` scaffold on `feat/v0.0.1`. |
| [#180](https://github.com/sebastienrousseau/pain001/issues/180) | XLSX loader as a first-class plugin | ✅ published as `pain001-loader-xlsx` |
| [#181](https://github.com/sebastienrousseau/pain001/issues/181) | GPG-encrypted input files via composable loader | ✅ v0.0.56 (loader), v0.0.66 (`--decrypt-key`, `--decrypt-passphrase-env`) |
| [#182](https://github.com/sebastienrousseau/pain001/issues/182) | OpenTelemetry instrumentation for the generator and REST API | ✅ v0.0.56 (surface), v0.0.66 (validate / write / scheme / REST spans, startup bootstrap) |

### Validation depth & Enterprise validation *(shipped: v0.0.66 → v0.0.72)*

With plugins live, validation extensions ship without core changes.
Cross-record rules, custom-rule DSLs, safe record repairs, Schematron,
and native acceleration are shipping artefacts.

| Issue | Item | Effort |
| :--- | :--- | :--- |
| [#183](https://github.com/sebastienrousseau/pain001/issues/183) | Cross-record duplicate-detection scheme profile (`anti-duplicate`) | ✅ v0.0.66, composable via `--scheme a,b` |
| [#184](https://github.com/sebastienrousseau/pain001/issues/184) | Custom YAML rule DSL via CEL (`pain001 --rules my-policy.yaml`) | ✅ v0.0.71 (request-local CEL policy rules for CLI/REST via `rules` extra) |
| [#185](https://github.com/sebastienrousseau/pain001/issues/185) | MCP `suggest_record_fix` tool for deterministic, review-only correction | ✅ v0.0.71 (core + companion MCP) |
| — | ISO 20022 Schematron business rule evaluator (EPC/SEPA, CBPR+, FedNow) | ✅ v0.0.72 |
| — | Formula injection shielding across batch and streaming CSV ingestion (CWE-1236) | ✅ v0.0.72 |
| — | ISO 20022 BAH (`head.001.001.03` / `head.003.001.01`) and XML-DSig RSA-SHA256 | ✅ v0.0.72 |
| — | Native acceleration integration hooks (`pain001-fast`) | ✅ v0.0.72 |

### End-to-end workflow *(shipped: v0.0.66 → v0.0.71)*

The bits that take pain001 from "validator" to "payment gateway."

| Issue | Item | Effort |
| :--- | :--- | :--- |
| [#186](https://github.com/sebastienrousseau/pain001/issues/186) | `pain001 upload --sftp` subcommand (SFTP only; EBICS deferred) | ✅ v0.0.71 (trusted host keys, atomic staging, retry reuse) |
| [#187](https://github.com/sebastienrousseau/pain001/issues/187) | `pain001-mockbank` Docker image for pain.002 round-trip testing | ✅ v0.0.71 (multi-arch edge container published to GHCR) |
| [#188](https://github.com/sebastienrousseau/pain001/issues/188) | Single-file hosted dashboard at `/api/v1/ui` (vanilla HTML, no framework) | ✅ v0.0.66 |

### Example corpus *(shipped: v0.0.67 → v0.0.69)*

Two corpora, one engine
([ADR-0003](docs/adr/0003-example-corpus-two-corpora-one-engine.md),
[docs/corpus.md](docs/corpus.md)): schema coverage sets that exercise every
element and choice branch of every bundled XSD, and bank-ready market files
per country and rail with provenance and an evidence state.

| Release | Scope | Status |
| :--- | :--- | :--- |
| v0.0.67 | Ground cleared; XSD inventory, message deltas, external code sets; `pain.008.001.08` bundled; scenario DSL and builder; coverage corpus at 100 % for 13 XSDs; MDR rules; 18 rail profiles and 5 purpose mandates; validation ladder and evidence workflow; three market scenarios (GB CHAPS, DE SEPA SCT, NL SEPA SDD) | ✅ v0.0.67 ([#271](https://github.com/sebastienrousseau/pain001/pull/271)) |
| v0.0.68 | Tier-1 market packs (UK, SEPA core countries, US, CH, SE), overlay tooling to apply a bank's guideline privately, website corpus page, MCP and LSP corpus tools | ✅ v0.0.68 |
| v0.0.69 | Tiers 2 and 3 (CZ, LU, HK, SG, MY, QA, AE) with confidence chips; CSV pipeline extension for the twelve most-used rails; the pain.001 twin foundation (ISO JSON twins, JSON Schema per edition, records twin, ADR-0005) | ✅ v0.0.69 |

### Next releases *(v0.0.73+)*

| Milestone | Scope | Effort | Status |
| :--- | :--- | :--- | :--- |
| **Faces engine (ADR-0005 Phase B & C)** | Outbound JSON projections of pain.001 to compatible standards: UK Open Banking Payment Initiation API and Berlin Group NextGenPSD2, plus the legacy ISO 2018 compatibility face backed by e-Repository name mappings, with explicit structured loss reports. | M | in progress |
| **Mutation floor hardening** | Pin ordering and timing dependencies in the fast mutation tier tests to eliminate variance (2,941 mutants), raising `MUTATION_FLOOR` from 80% to >=85%. | M | planned |
| **Twin import (ADR-0005 Phase D)** | Inbound deserialization: read ISO JSON twins and Open Banking / Berlin Group payloads back into canonical payment instruction models and validated XML documents. | L | planned |
| **Ecosystem discovery** | Submit `pain001-mcp` to `awesome-mcp-servers` and `pain001-lsp` to `awesome-language-servers` per `scripts/awesome-list-submissions.md`. | S | ready |

## Explicitly declined / deferred

A project's "no" list is as important as its "yes" list. The
following are **not** on the roadmap, with reasons:

| Item | Reason |
| :--- | :--- |
| Full SPA dashboard (React/Vue with build pipeline) | Maintenance burden vs. value. Community-led template; the in-tree alternative is the single-file `/api/v1/ui` page (#188). |
| **EBICS transport** | Bank-specific dialects (German H004 ≠ French T ≠ Swiss EBICS); months of per-bank conformance testing. Doing it wrong is worse than not doing it. Revisit only as "Deutsche Bank EBICS support" with a named bank partner. |
| AS2 / SWIFT transport | Same reasoning as EBICS; out of scope for the foreseeable future. |
| LLM-driven *generative* fix-it | Risk of hallucinated IBANs / BICs. The deterministic-patch alternative (#185) covers the safe subset. |
| Template hot-reload | The LSP already gives template authors real-time feedback; low ROI relative to the implementation cost. |
| Fuzzy-name matching | Out of scope — separate ML problem. Anti-duplicate (#183) is exact-key only. |
| Cross-batch deduplication | The engine has no memory between runs; document the workaround rather than build batch storage. |

## Project sustainability

The single highest-impact item on this entire page.

- [ ] **Recruit a second maintainer** with independent release
      authority. See [GOVERNANCE.md](GOVERNANCE.md#becoming-a-maintainer)
      and [MAINTAINERS.md](MAINTAINERS.md) for the current state
      (one maintainer; this *is* the bus-factor risk).
- [ ] **Identify and onboard subsystem maintainers** for the
      growing ecosystem (`pain001-mcp`, `pain001-lsp`, the loader
      plugins) so the suite doesn't depend on a single human's
      bandwidth.
- [ ] Stabilise the plugin contract through external author validation
      so external loaders / schemes can publish without fear of
      breaking changes inside the v0.0.x line (#179).
- [ ] **Marketing parity with engineering.** The project is
      under-discovered relative to quality — see the open tasks in
      [`scripts/awesome-list-submissions.md`](scripts/awesome-list-submissions.md)
      and the planned blog post.

## How to contribute

1. Read [CONTRIBUTING.md](CONTRIBUTING.md) and
   [ARCHITECTURE.md](ARCHITECTURE.md).
2. Run the quality gate locally: `make lint && make type && make test`.
3. Good first areas:
   - **Build an external loader plugin** (the contract is in
     [`docs/plugins.md`](docs/plugins.md); the worked example is
     [`pain001-loader-xlsx`](https://github.com/sebastienrousseau/pain001-loader-xlsx)).
   - A new scheme profile ([SCHEMES.md](SCHEMES.md)).
   - Docs (especially [`docs/quickstart.md`](docs/quickstart.md)
     feedback from new users).
4. Open an issue or discussion to claim one before starting.

## Key metrics (current)

| Metric | v0.0.51 | v0.0.52 | v0.0.53 | **v0.0.72** |
| :--- | :--- | :--- | :--- | :--- |
| Tests | ~1,150 | 1,181 | 1,265 | **3,305** |
| Line + branch coverage | 100% (98% floor) | 99.85% (98% floor) | 100% (100% floor) | **100% (100% floor)** |
| Docstring coverage (interrogate) | 100% | 100% | 100% | **100%** |
| Runnable examples in CI | 11 | 13 | 14 | **20** |
| Open CodeQL alerts | 0 | 1 (high) | 0 | **0** |
| Open security advisories on lockfile | 0 | (varies) | 0 | **0** |
| Companion packages (matching version) | 0 | 2 | 3 | **5** |

---

*Roadmap is indicative, not a commitment; the maintainer prioritises.
Subsequent versions of this document will live at
[ROADMAP.md](https://github.com/sebastienrousseau/pain001/blob/main/ROADMAP.md).*

## Quality debt, recorded 2026-09-18

- **Mutation-score variance.** Two runs of the fast mutation tier on
  identical code scored 87.1% and 83.2%: about 120 of 2,941 mutants
  change verdict between runs. Find the tests whose outcome depends on
  time, ordering or unseeded data, pin them, and raise `MUTATION_FLOOR`
  in the Makefile to two points under the stable score. Until then the
  floor is 80.
