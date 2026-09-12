# Pain001 Roadmap

## Mission

A robust, secure, high-performance ISO 20022 payment library with a
small, well-tested core, first-class developer surfaces (library, CLI,
REST, MCP, LSP), and a formal plugin contract so the ecosystem can
extend it without forking.

## Where we are (v0.0.66 shipped 2026-09-10; v0.0.67 in progress)

- **Generation:** pain.001.001.03 to .13, pain.008.001.02 and .08,
  registry-driven, `Decimal` end-to-end, mandatory XSD validation
  (XXE-safe via `defusedxml`).
- **Validation:** six scheme rulebooks — `sepa-sct`, `sepa-sdd`,
  `sepa-inst`, `sepa-b2b`, `xborder-ct`, and the cross-record
  **`anti-duplicate` (new in v0.0.66)**, composable as
  `--scheme sepa-sct,anti-duplicate`. IBAN / BIC / charset validators.
  Structured per-row violations with remediation hints.
- **Plugins (v0.0.56, v0.0.60):** `pain001.plugins` publishes
  `AbstractLoader` / `AbstractValidator` / `AbstractScheme` /
  `AbstractWriter`, entry-point discovery, `pain001 plugins list`, and
  the built-ins registered through the same contract external authors
  use. `pain001-loader-xlsx` is the first external plugin.
- **Parsers:** pain.002 status reports + camt.053 statements, plus
  `build_pain002_report` for round-trip testing.
- **Inputs:** CSV, SQLite, JSON, JSON Lines, Parquet, and GPG-encrypted
  wrappers of any of them (`pain001[gpg]`, `--decrypt-key`); streaming
  for large batches; cross-version migration between pain.001 versions.
- **Surfaces:** CLI command suite (`generate`, `validate`,
  `versions`, `inspect`, `init`, `serve`, `mcp`); REST `/api/v1`
  (auth, rate limiting, durable jobs, OpenAPI/Scalar, Prometheus
  `/metrics`) plus the single-file browser dashboard at `/api/v1/ui`
  (v0.0.66); MCP server; LSP server with editor diagnostics.
- **Observability:** Prometheus metrics and, behind `pain001[otel]` and
  `OTEL_ENABLED=true`, OpenTelemetry spans for the generator
  (`pain001.generate` → `write` → `render` → `validate`), the scheme
  checks, and every REST handler.
- **Distributed backends (new in v0.0.53):** Redis-backed job store
  and rate limiter so multi-replica deployments share state and
  enforce caps across the load balancer.
- **Distribution (new in v0.0.53):** official multi-arch Docker
  image at `ghcr.io/sebastienrousseau/pain001`, OpenAPI client SDK
  pipeline with drift-guard CI, hosted Scalar API reference.
- **Quality:** **1,700 tests**, **100% line + branch coverage (100%
  enforced floor)**, `mypy --strict`, 100% docstring coverage,
  ruff + pydoclint + bandit clean, CodeQL + pip-audit clean, every
  example exercised in CI.

Everything in the prior roadmap shipped. Focus now shifts from
breadth of *surfaces* to **plugin-driven extension by the
ecosystem**, **payment-gateway end-to-end workflows**, and
**project sustainability**.

## Suite

The suite all moves together; sibling packages release at matching
version numbers.

| Package | Role | Latest |
| :--- | :--- | :--- |
| [`pain001`](https://pypi.org/project/pain001/) | Core library + CLI + REST API | 0.0.65 |
| [`pain001-mcp`](https://pypi.org/project/pain001-mcp/) | Model Context Protocol server (16 tools) | 0.0.65 |
| [`pain001-lsp`](https://pypi.org/project/pain001-lsp/) | Language Server Protocol server (6 features) | 0.0.65 |
| [`pain001-loader-xlsx`](https://pypi.org/project/pain001-loader-xlsx/) | Excel (.xlsx) loader plugin | 0.0.65 |
| [`pain001-loader-mt101`](https://pypi.org/project/pain001-loader-mt101/) | SWIFT MT101 loader plugin | 0.0.65 |

## Planned releases

Three coordinated milestones. Issue links go to the canonical specs
filed at [`pain001` issues](https://github.com/sebastienrousseau/pain001/issues).
A ✅ marks an item that has shipped, with the release that carried it.

### Plugin substrate + table-stakes formats *(shipped: v0.0.56 → v0.0.66)*

Foundation release. Every subsequent format and validator becomes a
first-class plugin, so the contract has to land *before* those
features ship. Also addresses the single-maintainer risk by letting
the ecosystem extend pain001 without merging through the upstream.

| Issue | Item | Effort |
| :--- | :--- | :--- |
| [#179](https://github.com/sebastienrousseau/pain001/issues/179) | **Plugin architecture** — `AbstractLoader`, `AbstractValidator`, `AbstractScheme`, `AbstractWriter` Protocols; entry-point discovery; `pain001 plugins list` CLI | ✅ v0.0.56 (substrate), v0.0.60 (built-ins as plugins). Open: the `pain001-plugin-template` cookiecutter repo. |
| [#180](https://github.com/sebastienrousseau/pain001/issues/180) | XLSX loader as a first-class plugin | ✅ published as `pain001-loader-xlsx` |
| [#181](https://github.com/sebastienrousseau/pain001/issues/181) | GPG-encrypted input files via composable loader | ✅ v0.0.56 (loader), v0.0.66 (`--decrypt-key`, `--decrypt-passphrase-env`) |
| [#182](https://github.com/sebastienrousseau/pain001/issues/182) | OpenTelemetry instrumentation for the generator and REST API | ✅ v0.0.56 (surface), v0.0.66 (validate / write / scheme / REST spans, startup bootstrap) |

### Validation depth *(in progress)*

With plugins live, validation extensions ship without core changes.
The first cross-record rule (anti-duplicate) and the first
custom-rule DSL both move out of "everyone wants this" territory
into shipping artefacts.

| Issue | Item | Effort |
| :--- | :--- | :--- |
| [#183](https://github.com/sebastienrousseau/pain001/issues/183) | Cross-record duplicate-detection scheme profile (`anti-duplicate`) | ✅ v0.0.66, composable via `--scheme a,b` |
| [#184](https://github.com/sebastienrousseau/pain001/issues/184) | Custom YAML rule DSL via CEL (`pain001 --rules my-policy.yaml`) | L — the declarative part landed as the overlay grammar in v0.0.67 (`scenarios/overlays/`, shared with `iso20022-bank-profile-mcp`); a CEL expression layer on top remains open |
| [#185](https://github.com/sebastienrousseau/pain001/issues/185) | MCP `suggest_record_fix` tool for LLM-orchestrated correction | M |

### End-to-end workflow *(next)*

The bits that take pain001 from "validator" to "payment gateway."

| Issue | Item | Effort |
| :--- | :--- | :--- |
| [#186](https://github.com/sebastienrousseau/pain001/issues/186) | `pain001 upload --sftp` subcommand (SFTP only; EBICS deferred) | L |
| [#187](https://github.com/sebastienrousseau/pain001/issues/187) | `pain001-mockbank` Docker image for pain.002 round-trip testing | M |
| [#188](https://github.com/sebastienrousseau/pain001/issues/188) | Single-file hosted dashboard at `/api/v1/ui` (vanilla HTML, no framework) | ✅ v0.0.66 (beta) |

### Example corpus *(in progress: v0.0.67 → v0.0.69)*

Two corpora, one engine
([ADR-0003](docs/adr/0003-example-corpus-two-corpora-one-engine.md),
[docs/corpus.md](docs/corpus.md)): schema coverage sets that exercise every
element and choice branch of every bundled XSD, and bank-ready market files
per country and rail with provenance and an evidence state.

| Release | Scope | Status |
| :--- | :--- | :--- |
| v0.0.67 | Ground cleared; XSD inventory, message deltas, external code sets; `pain.008.001.08` bundled; scenario DSL and builder; coverage corpus at 100 % for 13 XSDs; MDR rules; 18 rail profiles and 5 purpose mandates; validation ladder and evidence workflow; three market scenarios (GB CHAPS, DE SEPA SCT, NL SEPA SDD) | in progress ([#271](https://github.com/sebastienrousseau/pain001/pull/271)) |
| v0.0.68 | Tier-1 market packs (UK, SEPA core countries, US, CH, SE), HSBC overlays where evidenced, website corpus page, MCP and LSP corpus tools | planned |
| v0.0.69 | Tiers 2 and 3 (CZ, LU, HK, SG, MY, QA, AE) with confidence chips; CSV pipeline extension for the twelve most-used rails | planned |

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
- [ ] Stabilise the plugin contract through v0.0.54 + early v0.0.55
      so external loaders / schemes can publish without fear of
      breaking changes inside the v0.0.x line.
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

| Metric | v0.0.51 | v0.0.52 | **v0.0.53** |
| :--- | :--- | :--- | :--- |
| Tests | ~1,150 | 1,181 | **1,265** |
| Line + branch coverage | 100% (98% floor) | 99.85% (98% floor) | **100% (100% floor)** |
| Docstring coverage (interrogate) | 100% | 100% | 100% |
| Runnable examples in CI | 11 | 13 | **14** |
| Open CodeQL alerts | 0 | 1 (high) | **0** |
| Open security advisories on lockfile | 0 | (varies) | **0** |
| Companion packages (matching version) | 0 | 2 | **3** |

---

*Roadmap is indicative, not a commitment; the maintainer prioritises.
Subsequent versions of this document will live at
[ROADMAP.md](https://github.com/sebastienrousseau/pain001/blob/main/ROADMAP.md).*
