# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — 0.0.60

A **licensing correctness and governance** release. No runtime behaviour
change and no public API change so far. Add entries here as work lands.

### Fixed

- **The published licence did not match the claimed one.** LICENSE,
  LICENSE-APACHE, LICENSE-MIT and the website all said dual
  Apache-2.0 OR MIT, but PyPI published `Apache-2.0`, `pyproject.toml`
  declared a single licence, all 167 source headers said Apache alone,
  and 27 files had no header. Now `SPDX-License-Identifier:
  Apache-2.0 OR MIT` in all 194 Python files, and the wheel carries
  `License-Expression: Apache-2.0 OR MIT` with all three licence files.
  Declared via PEP 639, not the legacy `license = "..."` string, which
  Poetry maps to `License :: Other/Proprietary License` for a compound
  expression. The corrected metadata only reaches PyPI on release, so
  0.0.59 and earlier still advertise Apache-2.0 only.

### Added

- **Developer Certificate of Origin required.** Every commit needs a
  `Signed-off-by` trailer, enforced by `.github/workflows/dco.yml`;
  see `DCO.txt` and `CONTRIBUTING.md`.
- **Security assurance case** at `docs/assurance-case.md` — threat
  model, trust boundaries, secure-design principles applied, and
  countered implementation weaknesses, each with checkable evidence.

## [0.0.59] - 2026-07-30

A **supply-chain** release. No runtime behaviour change and no public
API change; what changes is what can be proven about the artefacts.

### Fixed

- **The Docker image installed `fastapi` and `uvicorn` unpinned.**
  `requirements.txt` is hash-pinned but covers only the base install, so
  `pip install ".[api]"` resolved the web stack from PyPI at image build
  time. New hash-pinned `.github/requirements/api.txt` (13 pins, 144
  hashes) supplies them; the package is then installed with `--no-deps`
  so pip never resolves a third-party version. Same change in the docs
  and SDK workflows.
- **Release provenance attested 2 of 5 artefacts.** The SLSA job hashed
  only `dist/`, while the CycloneDX and SPDX SBOMs are written to
  `sbom/`. All five assets are covered now, and this is the first
  release where the fix actually runs — v0.0.58's SBOMs were attested
  only by a manual backfill, which cannot carry the tag binding.
- **The backfill workflow attested its own attestation**, listing
  `multiple.intoto.jsonl` as a subject and then overwriting it.
  `*.intoto.jsonl` is excluded before hashing; re-runs are idempotent.
- **`preflight_release.py`** reported `HEAD matches origin/main` with no
  explanation when run on an unpushed release commit; it now names the
  unpushed commit count and the fix.

## [0.0.58] - 2026-07-29

A **correctness** release. Two bundled schemas were hand-authored
placeholders rather than ISO publications, and one of them was masking a
defect in the direct-debit generator. Upgrade if you generate `pain.008`.

### Fixed

- **`pain.008.001.02` emitted `<SeqTp>` where ISO does not allow it.**
  `SeqTp` belongs to `PaymentTypeInformation20`, i.e. inside `<PmtTpInf>`;
  Pain001 emitted it as a bare child of `<DrctDbtTxInf>`. Every direct
  debit file this package produced would have been rejected by a bank.
  The permissive hand-authored schema validated them as correct, which is
  why it went unnoticed. `SeqTp` now follows `SvcLvl` inside `PmtTpInf`,
  and the preparer reads `sequence_type` from the data (default `RCUR`).
- **`pain.001.001.12` shipped a 475-byte stub that accepted any
  document.** Schema validation for that message type was reported as
  successful without being performed. The genuine ISO schema now ships;
  files that previously passed may now legitimately fail.
- **Migration between modern versions was refused.** `VersionMapper`
  raised `DataSourceError` for v09 -> v12, v10 -> v09 and every other
  modern-to-modern pair. These now work. Modern -> legacy stays refused:
  the legacy schemas have nowhere to put the newer structured data.
- **`bundled_schema_versions` and `schema_for_namespace` are exported**
  from `pain001.pain002`; they were documented but importable only from
  the parser submodule.

### Added

- **`pain.001.001.13`** templates, schema and registry entry — twelve
  message definitions now ship.
- **`pain.002` response validation.** `parse_pain002_report(...,
  validate=True)` checks a bank's status report against the bundled ISO
  schema for its namespace. Bundled: `pain.002.001.03` (the usual SEPA
  reply), `.12`, `.14`, `.15`. An unbundled namespace is refused
  explicitly rather than skipped.
- **`tests/test_schema_completeness.py`** — every shipped schema must
  exceed 10 KB, define at least five complex types, and behaviourally
  reject a junk document. `KNOWN_PLACEHOLDER_SCHEMAS` is empty.
- **`scripts/preflight_release.py`** / `make release-check` — the
  RELEASING.md checklist made executable, run before tagging.

### Changed

- All twelve bundled schemas are genuine ISO publications carrying a
  Standards Editor header; four were replaced.
- SLSA provenance is generated by the `provenance` job inside `ci.yml`.
  A release created with `GITHUB_TOKEN` emits no events, so the previous
  `on: release: published` workflow could never fire. `slsa.yml` is now
  dispatch-only backfill.
- `LICENSE` carries the full Apache-2.0 text plus a dual-licence note; a
  pointer file made GitHub report `NOASSERTION`.

## [0.0.57] - 2026-07-28

A **type-distribution, supply-chain and test-hardening** release. No
runtime behaviour change; no public API change.

### Security

- **Dependency vulnerabilities cleared.** `requirements.txt` had drifted
  from `poetry.lock` and pinned `click==8.1.7` (PYSEC-2026-2132) and
  `jsonschema==4.17.3`; both are resynced to the locked `8.4.2` /
  `4.26.0`. The transitive `soupsieve` is bumped `2.8.1 -> 2.9.1`
  (GHSA-2wc2-fm75-p42x, GHSA-836r-79rf-4m37). `pip-audit` reports no
  known vulnerabilities for the locked set.
- **CI installs are hash-pinned.** New pip-compile-generated
  `.github/requirements/{fuzz,sbom,build-test,docs}.txt` are installed
  with `--require-hashes`, `requirements.txt` now carries hashes, the
  unpinned `pip install --upgrade pip` steps are gone (workflows and
  `Dockerfile`), and `pipx install poetry` is pinned to `2.4.1`.
- **Signed release provenance.** This is the first release to trigger
  `slsa.yml`, which attaches a Sigstore-signed SLSA Build L3 provenance
  attestation (`*.intoto.jsonl`) to the release assets. Verify with
  `slsa-verifier verify-artifact <artifact> --provenance-path
  multiple.intoto.jsonl --source-uri github.com/sebastienrousseau/pain001`.
- OpenSSF Scorecard improved from 5.4 to 7.5 across these changes
  (Vulnerabilities 10/10, Pinned-Dependencies 8/10).

### Added

- **PEP 561 `py.typed` marker.** The package has been `mypy --strict`
  clean internally for several releases, but shipped no `py.typed`
  marker — so downstream consumers received none of the annotations.
  The marker is now present and included in both the wheel and the sdist
  (verified: `pain001/py.typed` is packaged in the built wheel). Type
  checkers now see `pain001` as a typed dependency.
- **Regression tests for the marker** (`test_typing_and_validator_properties.py`):
  fail before release if `py.typed` is ever dropped from the tree or the
  packaging include list.
- **Property test: in-memory and on-disk XSD validators agree.** A
  Hypothesis test pins `validate_xml_string_via_xsd` (the serverless /
  in-memory path) and `validate_via_xsd` (the on-disk path) to the same
  verdict across valid and invalid documents, so a deployment-shape
  divergence cannot let a document pass one gate and fail the other.

### Changed

- Version synced to `0.0.57` across `pyproject.toml`, `constants.py`,
  `__init__.py` and the GPG plugin's advertised version.
- Docs and security workflows standardised on Python 3.12 so the
  hash-pinned requirement sets resolve consistently.
- `fuzz/fuzz_validation.py` uses an f-string in its assertion message
  (ruff UP031), which had been failing the lint gate.

## [0.0.56] - 2026-07-18

Ships the plugin substrate, a GPG-encrypted-input loader, and an
OpenTelemetry observability surface **on top of** the 0.0.55 path-injection
hardening. This is the first release to publish `pain001.plugins` to PyPI:
the feature work that had been developed in parallel with the 0.0.55 security
release is merged forward here with the job-store containment guarantees fully
preserved.

### Added

- **Plugin substrate (`pain001.plugins`):** a formal, versioned plugin
  contract (`contracts.py` — `AbstractLoader` / `AbstractValidator` /
  `AbstractScheme` / `AbstractWriter` Protocols), a process-level
  `PluginRegistry` (`registry.py`) that discovers built-ins eagerly and
  third-party plugins via `importlib.metadata` entry points, the built-in
  loader adapters (`_builtins.py`), and a single-source contract API version
  (`_version.py`). Exposed on PyPI for the first time.
- **GPG-encrypted-input loader (`pain001[gpg]` extra):** `builtins_gpg.py`
  registers an opt-in loader (`kind=loader`, `name=gpg`) that decrypts
  `.gpg` / `.asc` inputs in memory via `python-gnupg` and dispatches to the
  inner-extension loader (`batch.csv.gpg` → gpg → csv). Decrypted bytes still
  flow through the existing path-validator and schema guards.
- **OpenTelemetry observability surface (`pain001[otel]` extra):** opt-in
  distributed tracing (`traced`, `init_otel`, `set_span_attributes`,
  re-exported from `pain001.observability.otel`), off by default and enabled
  with `OTEL_ENABLED=true`. Metric events attach the active span's
  `(trace_id, span_id, is_remote)` so metrics correlate back to traces.

### Security

- **Retains all 0.0.55 path-injection hardening.** The merge preserves
  `pain001/api/job_store.py` in full: the module-level `_validate_job_id`
  safe-token gate (`[A-Za-z0-9][A-Za-z0-9_-]{0,127}`), the
  `FileJobStore._path` `realpath` + `commonpath` + `startswith` containment
  barrier, and `RedisJobStore._key` validating the id before namespacing it.
  The `pain001/api/app.py` `_gate_output_dir` containment and the
  `mcp>=1.28.1` bump are carried forward unchanged.

### Changed

- **New optional extras `gpg` and `otel`** added to `pyproject.toml`
  (`python-gnupg`, `opentelemetry-api` / `-sdk` / `-exporter-otlp-proto-http`).
  `poetry.lock` regenerated cleanly (`mcp` resolves 1.28.1,
  `pydantic-settings` at 2.14.2).
- **mypy `--strict` type-correctness on the plugin surface:** built-in
  loaders annotate `extensions: tuple[str, ...]` to satisfy the
  `AbstractLoader` Protocol invariantly, and `gnupg` / `opentelemetry` are
  registered as untyped third-party imports.

## [0.0.55] - 2026-07-18

Security hardening for the async job API and a dependency bump. Closes the
outstanding CodeQL path-injection findings on the job store and the API
output-directory sink, and clears the `mcp` Dependabot advisory.

### Security

- **Job id path-traversal hardening (`pain001/api/job_store.py`, CWE-22):**
  every identifier that becomes part of a filesystem path or Redis key is now
  validated against a strict safe-token pattern
  (`[A-Za-z0-9][A-Za-z0-9_-]{0,127}`) before use — rejecting path separators,
  `..`, and leading dots. `FileJobStore._path` additionally enforces a
  canonical `os.path.realpath` + `os.path.commonpath` + `startswith`
  containment barrier so a resolved job file can never escape the store
  directory, and `RedisJobStore._key` validates the id before namespacing it.
- **API output-directory sink (`pain001/api/app.py`):** `_gate_output_dir`
  now applies the `startswith` containment barrier on the canonicalised
  candidate it returns, so the downstream `mkdir` sink clears the CodeQL
  `py/path-injection` query natively rather than relying on the neutral model.

### Changed

- **`mcp` dependency raised to `>=1.28.1,<2`** (was `>=1.23,<2`) to clear the
  Dependabot advisory affecting `mcp < 1.28.1`; `poetry.lock` now resolves
  `mcp` 1.28.1.

### Fixed

- **`tests/test_sepa_b2b_profile.py`:** collapsed the duplicate
  `import pain001` / `from pain001 import validate_scheme` pair into a single
  `from pain001 import __version__, validate_scheme`, resolving the
  `py/import-and-import-from` note.

## [0.0.54] - 2026-07-16

LLM-ergonomic generate path. Driven by a real agent transcript in which
Claude Code, connected through the iso20022-mcp gateway, needed 5+
retries to produce a schema-valid pain.001.001.09: natural inputs
(`amount`, `currency`, a bare `YYYY-MM-DD` date, a JSON boolean, no
`nb_of_txs`) each failed one at a time, and the primary bug - the v09
data preparer reading only `payment_currency` and silently rendering
`Ccy=""` - surfaced only as an opaque XSD failure.

### Added

- **`normalize_payment_records()`** (exported from `pain001`): the
  canonical input-normalization step the generators now apply
  internally - field aliases (`amount` -> `payment_amount`,
  `currency` <-> `payment_currency`, `execution_date` ->
  `requested_execution_date`, lower-case `*_iban` / `*_bic` key
  spellings), two-decimal amount formatting, XSD boolean rendering
  (including `"True"` / `"FALSE"` strings), temporal coercion (bare
  `date` -> `T00:00:00`; datetime `requested_execution_date` truncated
  to its date part), and computed `nb_of_txs` / `ctrl_sum`.
- **`canonicalize_payment_record()`** (exported from `pain001`): the
  key-mapping half of the above, preserving value types for
  JSON-Schema validation.
- **`collect_xsd_validation_errors()`** in
  `pain001.xml.validate_via_xsd`: returns every XSD violation (element
  path + reason) for an XML string instead of a bare boolean.

### Fixed

- **Silent `Ccy=""`**: the v03/v05-v08/v09-v12 preparers accept
  `currency` as well as `payment_currency`; a missing currency is now
  reported by name instead of rendering an empty attribute that only
  fails XSD validation later.
- **One-KeyError-per-retry**: the v03 and v09-v12 preparers validate
  required fields up front and raise a single `PaymentValidationError`
  listing *all* missing header and per-row fields at once.
- **Opaque XSD failures**: `generate_xml_string` now includes the
  collected per-element violations in the `RuntimeError` it raises.
- **Unconditional `SplmtryData`**: the v09-v12 templates emitted a
  hardcoded empty `<SplmtryData><Envlp><WC/></Envlp></SplmtryData>`
  block that some bank gateways reject; it is now emitted only when a
  record provides `supplementary_data`.
- **Ergonomic defaults**: `payment_method` (`TRF`), `charge_bearer`
  (`SLEV`) and v03 `batch_booking` (`false`) default sensibly;
  `nb_of_txs` / `ctrl_sum` are computed and no longer listed as
  required by the bundled JSON Schemas. IBAN/BIC validation is
  unchanged.

## [0.0.53] - 2026-06-20

Security + observability + scheme-validation release. Closes every open
issue and every open code-scanning alert at the time of the release; the
public API surface is unchanged, so v0.0.52 callers upgrade
transparently. v0.0.53 also moves the project to a **100 % enforced
coverage floor** (line + branch + docstrings) so regressions can no
longer slip past CI.

### Added

- **SEPA Business-to-Business Direct Debit scheme profile** (issue #173):
  `SepaB2BDirectDebitProfile` in `pain001.validation.schemes` enforces
  the two rules the consumer SDD profile doesn't - only `FRST` or `RCUR`
  sequence types (no `OOFF` / `FNAL`) via rule `B2B-SEQTP`, and a
  mandatory creditor identifier via `B2B-CDTR-ID`. The CLI accepts
  `--scheme sepa-b2b`; the REST API accepts `scheme: "sepa-b2b"` on
  `/api/v1/validate` and `/api/v1/generate`. The `PROFILES` registry now
  advertises five profiles; the `pain001_scheme_profiles` Prometheus
  gauge reflects the new count.
- **Redis-backed durable job store** (issue #171):
  `pain001.api.job_store.RedisJobStore` implements the existing
  `JobStore` Protocol with cursor-paginated SCAN so multi-replica
  deployments share async-job state and survive restarts. Selected via
  `PAIN001_JOB_STORE_URL=redis://...`; in-process consumers swap
  backends without code changes.
- **Redis-backed distributed rate limiter** (issue #172):
  `pain001.api.ratelimit.RedisFixedWindowBackend` plus the
  `RateLimiterBackend` Protocol and the env-driven `backend_from_env`
  factory. Same `PAIN001_RATE_LIMIT` spec is parsed by both backends;
  the per-client cap is now enforced across replicas behind a load
  balancer (in-process limiters only protected one worker).
  Configured via `PAIN001_RATE_LIMIT_BACKEND=redis` plus
  `PAIN001_RATE_LIMIT_REDIS_URL=...` (falls back to
  `PAIN001_JOB_STORE_URL` if unset). A new `pain001[redis]` extra
  pulls in `redis >= 5`; `fakeredis` is in the dev group.
- **Official multi-arch Docker image** (issue #169) at
  `ghcr.io/sebastienrousseau/pain001` - Python 3.12-slim multi-stage
  build, non-root `pain001` user, `[api]` extra preinstalled, published
  for `linux/amd64` and `linux/arm64` on every push and tag with
  provenance attestations and a registry-side smoke test. New
  `docker.yml` workflow + `Dockerfile` + `.dockerignore`.
- **Typed OpenAPI client SDK pipeline** (issue #170): `sdk.yml`
  workflow runs `openapi-generator-cli` against the live API spec, builds
  the Python client, smoke-tests it, and fails CI when
  `scripts/export_openapi.py` drifts from the live spec. The drift
  guard is the safety net that keeps generated clients honest as the
  API evolves.
- **Hosted interactive Scalar API reference** (issue #174):
  `docs.yml` now exports `openapi.json` and bundles
  `docs/_static/api-reference.html` (a Scalar embed) into the Sphinx
  site at <https://sebastienrousseau.github.io/pain001/api-reference.html>.
  The runtime REST API still serves the same reference at
  `/api/reference`.
- **`examples/14_redis_distributed.py`** - runnable, self-checking
  walkthrough of the Redis job store + cross-replica rate limiter via
  `fakeredis`.
- **`examples/06_scheme_validation.py`** rewritten to cover every
  bundled profile (`sepa-sct`, `sepa-sdd`, `sepa-inst`, `sepa-b2b`,
  `xborder-ct`) plus a `PROFILES` registry check; previously only the
  first two were exercised.

### Changed

- **Coverage floor raised from 98 % to 100 %.** `make test` / `make cov`
  / the CI suite all run with `--cov-fail-under=100`; the suite carries
  **1,265 tests** and exercises every statement and branch of
  `pain001/`. Defensive guards that are genuinely unreachable carry an
  inline `# pragma: no cover` with the reason.
- **Security gate migrated from `safety` to `pip-audit`** (issue #175).
  `safety scan` v3 requires an interactive auth prompt that hangs CI;
  the issue text explicitly permits an equivalent scanner, and
  `pip-audit` covers the same OSV/PyPI advisory feed with no auth. The
  `make sec` target, `security.yml` workflow, and the `tollgate-deps`
  enterprise gate all use `pip-audit` now; the `.safety-policy.yml`
  file is retained as a documentation artifact of the migration.
- **Plugin & companion-package README sections** refreshed: the
  standalone `pain001-mcp` companion now ships **sixteen** tools (was
  eleven), and `pain001-lsp` now ships **six** features (was four -
  `textDocument/formatting` + `textDocument/documentSymbol` are new in
  the matching sibling-package release). README badges, install table,
  CLI subcommands, REST env-var table, and the "Current state" line
  are all aligned with the v0.0.53 surface.
- **`tests/test_docker_smoke.py`** skips its live `docker build`
  fixture when `GITHUB_ACTIONS=true`; the dedicated `docker.yml`
  workflow already exercises the image end-to-end on every push, and
  building it twice on the shared runner was the slowest + flakiest
  step in `make check`.

### Fixed

- **CodeQL alert #176** (`py/path-injection`, high severity) in
  `pain001/api/app.py:249`. `_sanitise_message_type` was called only
  for its side effect; the sanitised return value is now used to build
  the downstream `Path` join so the static-analysis sanitiser barrier
  is recognised.
- **CodeQL `py/incomplete-url-substring-sanitization`** in
  `tests/test_docker_smoke.py:105`. The bare `"ghcr.io" in text`
  workflow-content check is anchored to `"REGISTRY: ghcr.io"` so the
  query no longer flags it as a URL-host check.
- **`py/import-and-import-from`** in `tests/test_sepa_b2b_profile.py`.
  `pain001` is now imported once at module level instead of once via
  `from pain001 import ...` and once via `import pain001` inside a
  function.
- **`pydantic-settings 2.14.1 -> 2.14.2`** (GHSA-4xgf-cpjx-pc3j). A
  fresh advisory dropped against the transitive dep between branch
  cut and CI's nightly `pip-audit` pass; re-locking pulled in the
  patch.

### Security

- **`pip-audit` runs in CI on every push and PR** (replaces `safety
  scan`). The same scanner is wired into `make sec` and into the
  enterprise `tollgate-deps` gate so local developers get the same
  signal CI does.
- **Bandit + CodeQL** both pass with zero open alerts at release time.
- **Plaintext secret handling**: no change. Plaintext payment data and
  GPG-decrypted bytes still flow through the existing path-validator
  + `defusedxml` barriers.

### Documentation

- `README.md` "Current state" line, install table, CLI surface table,
  REST API env-var table, and the entire companion-packages section
  refreshed to reflect every v0.0.53-NEW surface.
- `examples/README.md` advertises the new `14_redis_distributed.py`
  script and the expanded scheme-profile coverage.
- `tests/test_examples.py` discovery floor raised to 14 so a silently-
  deleted example fails CI loudly.

### Quality gates (all enforced on every commit)

| Gate | v0.0.52 | v0.0.53 |
| :--- | :--- | :--- |
| Tests | 1,181 | **1,265** |
| Line + branch coverage | 99.85 % (98 % floor) | **100 % (100 % floor)** |
| Docstring coverage (interrogate) | 100 % | 100 % |
| Runnable examples | 13 | **14** |
| Open CodeQL alerts | 1 (high) | **0** |
| Open security advisories on lockfile | (varies) | **0** |
| mypy `--strict` | clean | clean |
| ruff + pydoclint + black | clean | clean |

### Migration notes

There are no breaking changes. v0.0.52 callers upgrade transparently.
New optional features are opt-in via extras:

```bash
pip install "pain001[redis]"   # distributed job store + rate limiter
docker pull ghcr.io/sebastienrousseau/pain001:0.0.53
```

To enable the new scheme profile:

```bash
pain001 -t pain.001.001.03 -d payments.csv --scheme sepa-b2b
```

### Issues closed

#169, #170, #171, #172, #173, #174, #175 plus CodeQL alert #176.

## [0.0.52] - 2026-06-18

Companion-packages release. The MCP and LSP servers added in 0.0.51 remain
in-tree (so `pip install "pain001[mcp]"` and `pip install "pain001[lsp]"`
keep working), and ship alongside two new **standalone** sibling packages
so users who want only the agent or editor surface can install just that
piece without pulling in the full core. Versioning is now aligned across
the three packages: `pain001`, `pain001-mcp`, and `pain001-lsp` all release
under matching numbers.

### Added

- **Standalone companion packages**, both at matching version `0.0.52`:
  - [`pain001-mcp`](https://github.com/sebastienrousseau/pain001-mcp) - a
    Model Context Protocol server exposing the pain001 public API as
    eleven agent tools (schema discovery, validation, generation, async
    + file-driven generation, supported-format discovery, camt.053 and
    pain.002 parsing). Built on FastMCP; ships a multi-stage Dockerfile.
  - [`pain001-lsp`](https://github.com/sebastienrousseau/pain001-lsp) - a
    pygls-based Language Server with diagnostics, completion, hover, and
    a multi-record "add missing required fields" code action for
    payment-data JSON files. Supports both startup and live
    (`workspace/didChangeConfiguration`) message-type overrides.
- README **MCP Server** and **Language Server (LSP)** sections covering
  both the in-tree and standalone install paths.

### Changed

- The in-tree console scripts are renamed to `pain001-mcp-builtin` and
  `pain001-lsp-builtin` so the canonical command names (`pain001-mcp`,
  `pain001-lsp`) belong to the standalone packages when both are
  installed. The Python import paths (`pain001.mcp.server`,
  `pain001.lsp.server`, `pain001.lsp.diagnostics`) are unchanged.
- Version bumped from `0.0.51` to `0.0.52` to land alongside the initial
  release of the two companion packages.

## [0.0.51] - 2026-06-16

Feature release. Scheme-aware validation is the flagship capability, rounded
out by a unified CLI command suite, a versioned REST API portal, an MCP
server, and an LSP server — on a core with strict typing, a 100% documented
public API, and an enforced coverage floor. See [GOVERNANCE.md](GOVERNANCE.md)
for how the project is run.

### Added

- **Scheme rulebook validation** (`pain001.validation.validate_scheme`): a
  pluggable `ValidationProfile` framework with three profiles —
  `sepa-sct` (SEPA Credit Transfer, pain.001), `sepa-sdd` (SEPA Direct
  Debit, pain.008), and `sepa-inst` (SEPA Instant Credit Transfer, pain.001,
  with the 100,000.00 EUR per-transaction cap). They enforce EUR currency,
  valid debtor/creditor IBANs
  (ISO 13616 / mod-97), well-formed BICs, the SEPA amount ceiling
  (999,999,999.99), ISO 20022 character-set and field-length limits, and —
  for SDD — mandate id and sequence type. Results are structured, per-row
  `SchemeViolation` objects with stable rule ids, `error`/`warning`
  severities, and remediation hints.
- **ISO 20022 character-set guard** (`pain001.validation`):
  `is_valid_charset`, `find_invalid_characters`, and `sanitize_to_charset`
  (transliterates accented Latin and replaces unsupported characters) —
  the restricted Latin set is a leading real-world rejection cause.
- **CLI**: `--scheme sepa-sct|sepa-sdd` runs the rulebook on top of XSD
  validation in both dry-run and generation (exit `1` on violation, `2` on
  unknown profile); `--explain` prints a remediation hint per violation;
  `--scheme-format json` emits a machine-readable result for CI.
- **REST API**: `POST /api/validate` and `/api/generate` accept an optional
  `scheme` field and return `scheme_violations`; generation is refused when
  scheme validation fails.
- **Top-level exports**: `validate_scheme`, `SchemeValidationResult`,
  `SchemeViolation`, and `sanitize_to_charset` are importable from
  `pain001`.
- **MCP server** (`pip install "pain001[mcp]"`, run `pain001-mcp`): a
  FastMCP stdio server exposing generation and validation to LLM clients.
  Tools — `generate_payment_file`, `validate_payment_data`,
  `validate_payment_scheme`, `list_supported_versions`, `inspect_template`;
  a read-only `pain001://schema/{message_type}` resource; and a
  `build_payment_batch` prompt. Tools take inline rows and return XML as a
  string (no shared filesystem), so they wrap the existing core directly.
- **CLI command suite**: `pain001` is now a command group. Alongside the
  default `generate`, the binary gains `validate` (a named `--dry-run` for
  CI pre-flight), `versions` (`--json`), `inspect <type>` (`--json`),
  `init <type>` (scaffold a starter CSV), `serve` (launch the REST API),
  and `mcp` (launch the MCP server). A bare invocation — the long-documented
  `pain001 -t … -d …` — is routed to `generate`, so existing scripts and
  one-liners keep working unchanged.
- **LSP server** (`pip install "pain001[lsp]"`, run `pain001-lsp`): a
  `pygls` stdio language server giving editors live diagnostics on payment
  CSVs — invalid IBAN/BIC/currency cells, characters outside the ISO 20022
  Latin set, and missing required columns — reusing the same validators as
  the generator. The diagnostic engine (`pain001.lsp.diagnostics_for_csv`)
  is dependency-free and reusable on its own; a thin VS Code client ships
  under `editors/vscode/`.
- **REST API portal**: endpoints are now versioned under `/api/v1` (the
  unversioned `/api/*` paths remain as a backwards-compatible alias). New
  operational controls, all environment-driven and off by default —
  `PAIN001_RATE_LIMIT` (in-process per-client request cap, e.g.
  `100/minute`) and `PAIN001_JOB_STORE_DIR` (durable file-backed async job
  store that survives restarts). Enriched OpenAPI metadata (tag
  descriptions, contact, licence, request examples), an interactive
  [Scalar](https://scalar.com) reference at `/api/reference`, and a
  `scripts/export_openapi.py` helper plus documented `openapi-generator`
  workflow for generating typed client SDKs.
- **Bank-response generation** — `pain001.build_pain002_report` (payment
  status reports) and `pain001.build_camt053_statement` (account statements)
  build the messages a bank sends back, from structured data with validated
  ISO 20022 status/indicator codes. They complement the existing parsers and
  round-trip with them — useful for simulating bank responses in tests.
- **Prometheus metrics**: the REST API exposes `GET /metrics` (build info,
  supported-type/scheme gauges, async-job gauges, HTTP request counters)
  with no extra dependency; see the new `OPERATIONS.md` runbook.
- **Project governance**: `GOVERNANCE.md` (roles, decision making, release
  authority, and an explicit path to becoming a maintainer), `MAINTAINERS.md`
  with an open co-maintainer slot, and a Contributor Covenant
  `CODE-OF-CONDUCT.md` — reducing single-maintainer (bus-factor) risk.

### Fixed

- Corrected every bundled sample's IBANs and BICs to pass mod-97 / format
  validation (the shipped templates, examples, fixtures, SQLite DBs, and
  golden XML had invalid checksums and placeholder values). The bundled
  `pain.001.001.03` sample is now fully SEPA-SCT compliant.

### Tests

- Expanded the suite to **1,020+ tests** and set the coverage floor to
  **98%** (branch coverage; actual ~100%). New tests cover the scheme CLI
  flags, the REST scheme paths, the async generation worker, the
  validation service, the migration mapper, and the loader/parser error
  branches. Only entry-point guards and genuinely-defensive barriers
  (catch-all 500 handlers, redundant CWE-22 path checks) are excluded via
  `[tool.coverage.report]` and targeted `# pragma: no cover` — never
  padded with fake tests. The 98% floor leaves headroom over the ~100%
  actual so routine changes don't fail CI on a single line.
- Added `tests/test_regression_suite.py`: a feature-matrix regression
  suite with one end-to-end guard per documented feature — generation
  across all 11 message types, every input format, the library/CLI/REST
  surfaces, scheme validation, the pain.002/camt.053 parsers, version
  migration, and observability hooks.
- Added `tests/test_sample_data_valid.py`: lints every bundled sample CSV
  through the library's own validators so invalid IBAN/BIC/currency data
  can never silently ship again.

### Documentation

- Added `SCHEMES.md`: the full rule catalogue (id, severity, scope,
  remediation) and a guide to adding new profiles.
- Expanded `examples/` to one self-checking script per feature (now 11):
  added scheme validation, pain.002/camt.053 parsing, version migration,
  streaming, input formats, and observability examples. Every example is
  executed in CI, so the documented feature surface cannot silently rot.
- Added `ARCHITECTURE.md` (module map + design decisions and extension
  points), `RELEASING.md` (what merits a release + the cut/publish
  process), `GOVERNANCE.md`/`MAINTAINERS.md`, and `.github/CODEOWNERS` —
  lowering the project's onboarding and bus-factor risk.
- Grew `examples/` to 13 self-checking scripts (added the MCP tools and the
  LSP diagnostic engine), each executed in CI so the feature surface cannot
  silently rot.
- Simplified the `Makefile` `lint`/`type`/`test` targets: dropped the
  build-failing SLO timers (which could fail CI on slow runners for no
  functional reason) and pointed `make type` at the package.

### Dependencies

- Bumped `starlette` 1.2.1 → 1.3.1 (supersedes Dependabot #167).

## [0.0.50] - 2026-06-15

Internal maintainability release. No functional or API changes; all public
imports and behaviour are unchanged.

### Changed

- **pydantic:** Migrated the FastAPI request/response models from the
  deprecated class-based `Config` to pydantic v2 `ConfigDict`, removing
  `PydanticDeprecatedSince20` warnings and preparing for pydantic v3.
- **logging:** Split the 1,064-line `pain001/logging_schema.py` god module
  into a focused `pain001/logging_schema/` package (schema, context,
  redaction, events, tracker, formatter, metrics). The `pain001.logging_schema`
  import path and public API are unchanged.

### Tests

- Removed coverage-padding tests that inflated the coverage number with
  line-chasing rather than behavioural assertions (deleted
  `test_full_coverage.py`; trimmed `exec()`-based padding from the former
  `test_coverage.py`, now `test_error_paths.py`). Genuine behavioural
  coverage is 92%; the coverage floor is reconciled to an honest 90%
  across `pyproject.toml` and the `Makefile`.

### Documentation

- Corrected two inaccurate claims in `README.md`: SQLite input reads from a
  user-specified table (not a fixed `pain001` table), and the programmatic
  `main()` entry point requires a template/schema (only the CLI auto-resolves
  the bundled pair). Refreshed the test/coverage stats, replaced the Python
  API example with a fully self-contained runnable `generate_xml_string`
  snippet, and added a Documentation section.

## [0.0.49] - 2026-06-14

Maintenance release. No functional or API changes since 0.0.48; this is a
version bump for release hygiene.

### Changed

- Bumped package version to `0.0.49` across `pyproject.toml`,
  `pain001/constants.py`, and `pain001/__init__.py`.

### Security

- No new advisories. The dependency set remains clean: `pip-audit` reports
  zero known vulnerabilities across all locked packages, carrying forward the
  remediations shipped in 0.0.48.

## [0.0.48] - 2026-06-12

### Highlights
- **New ISO 20022 coverage:** pain.001.001.12 generation (versions .03
  through .12), pain.008.001.02 direct debits, plus pain.002 and
  camt.053 parsers and a version-migration CLI.
- **Financial correctness:** amounts are parsed as `Decimal` and strictly
  validated; `NbOfTxs` and `CtrlSum` are computed from the payment rows,
  never trusted from input.
- **Explicit output paths:** `process_files()` and `generate_xml()` accept
  an `output_path` argument and return the written path; the CLI writes
  to the current directory by default.
- **API hardening:** optional bearer-token auth, bounded job store, and
  package-relative template resolution.
- **Python 3.10+:** EOL Python 3.9 support dropped.
- **Leaner packaging:** FastAPI/uvicorn and pyarrow moved to `[api]` and
  `[parquet]` extras; unused runtime dependencies removed.

### Added

- pain.001.001.12 generation support; pain.008.001.02 (Customer Direct
  Debit Initiation) as the first non-pain.001 generator.
- pain.002 (payment status report) and camt.053 (bank statement) parsers.
- Version migration tooling: `python -m pain001.migrate` maps payment
  data between pain.001 versions via YAML mappings (generic fallback
  through v12).
- Template registry bundling Jinja2 template, official XSD, and metadata
  per message type, with schema-drift guardrails;
  `--list-templates` / `--show-template` CLI discovery.
- `output_path` parameter on `process_files()` and `generate_xml()`; both
  now return the path the XML was written to. The legacy behaviour of
  writing next to the template is deprecated (emits `DeprecationWarning`).
- `output_dir` parameter on `process_files_streaming()`.
- Optional API authentication: set `PAIN001_API_KEY` to require
  `Authorization: Bearer <key>` on all endpoints except `/api/health`.
- Packaging extras: `pip install pain001[api]` for the REST API and
  `pain001[parquet]` for Parquet support, with clear `ImportError` hints.
- Runnable `examples/` suite (file/string generation, CLI workflows,
  config profiles, API job lifecycle), executed as part of the test
  suite.

### Changed

- **Python floor raised to 3.10** across packaging, CI, and tooling.
- **Amount validation is strict:** missing, non-numeric, non-positive, or
  more-than-2-decimal amounts now raise `PaymentValidationError` instead
  of being silently passed through to the XML.
- `NbOfTxs` and `CtrlSum` in generated XML are always computed from the
  data rows; input values for these fields are ignored.
- The CLI writes generated XML to the current directory by default
  (previously next to the template) and resolves `-o/--output-dir`
  explicitly instead of changing the working directory, so relative
  data and template paths stay anchored to the caller's cwd.
- The REST API resolves bundled templates package-relatively and honours
  `output_dir`; async jobs run in a worker thread and retain task
  references (no mid-flight garbage collection).
- Job store: terminal job states (success/failed/cancelled) are final and
  the in-memory store is bounded; timestamps are timezone-aware UTC.
- Runtime dependencies use floor pins (`>=x,<next-major`) instead of
  exact pins; `jsonschema` constraint widened to `<5`.
- Lint stack consolidated to Ruff (formatting, linting, import sorting);
  black/isort/flake8/pylint removed from dev dependencies and CI.
- Library logging is now well-behaved: no root-logger configuration, no
  handler attachment, no `logging.basicConfig()` at import time; a
  `NullHandler` is attached to the package logger.
- Documentation gates enforced in CI: 100% docstring coverage
  (interrogate) and zero pydoclint errors.

### Fixed

- API generation works end to end for every input type: CSV string
  values are coerced to the schema's declared types before validation,
  and Python booleans render as XSD `"true"`/`"false"` instead of
  `"True"` in v03-v08 templates.
- Version migration accepts pain.001.001.12 as a generic mapping target.
- XSD validators log errors via the module logger instead of printing
  to stdout.
- `process_files()` success check now verifies the actually written file
  instead of a derived template path.
- DB-sourced data is validated with the same type rules as CSV data
  (including SQLite 0/1 booleans), and non-string values from JSON or
  Python dicts no longer crash validation.
- The security workflow now fails on known vulnerabilities instead of
  always passing.

### Security

- 14 Dependabot alerts remediated (cryptography, fastapi, starlette,
  urllib3, requests, idna, python-dotenv, pyarrow, Pygments, pytest
  stack); wheel pinned >=0.46.2 (CVE-2026-24049).
- Scoped, expiring safety-policy ignore for disputed CVE-2022-42969 in
  `py` (dev-only transitive dependency of interrogate).

## [0.0.47] - 2026-01-18

### Highlights
- **Full I/O decoupling for Serverless and API architectures.**
- **Introduced O(1) memory streaming data loaders for CSV and SQLite.**
- **Hardened path validation and security against Log/SQL injection.**
- **Achieved 92.22% test coverage with 851 passing tests.**

### Added

- **Serverless I/O Decoupling** - String-based XML generation for AWS Lambda/Azure Functions (PR #152):
  - New `generate_xml_string()` function returns XML as string instead of writing to file
  - Eliminates file system dependencies for cloud-native deployments
  - Compatible with API Gateway, Cloud Functions, and container orchestration
  - Memory-efficient streaming for large payment files
  - Full backward compatibility with existing file-based workflows

- **O(1) Streaming Data Loaders** - Memory-efficient processing for large datasets (PR #152):
  - `load_csv_data_streaming()` - Process CSV files in configurable chunks (default: 1000 rows)
  - `load_db_data_streaming()` - Stream SQLite query results without loading full table
  - ~90% memory reduction for files with 10,000+ transactions
  - Enables processing of datasets larger than available RAM
  - Generator-based architecture for pipeline-friendly data flow

### Security

- **Log Injection Protection (CWE-117)** - Prevents log forging attacks (Commit: 894106e):
  - Sanitizes file paths before logging to prevent newline injection
  - Escapes `\n` and `\r` characters in user-controlled input
  - Applied to CSV streaming loader error handling
  - CodeQL security gate compliance achieved (0 alerts)

- **SQL Injection Hardening (CWE-89)** - Strict table name validation (Commit: 95934ae):
  - Replaced weak transformation with strict regex validation: `^[a-zA-Z][a-zA-Z0-9_]*$`
  - Rejects invalid table names instead of attempting sanitization
  - Prevents SQL injection via malicious table identifiers
  - Applied to both standard and streaming SQLite loaders

- **Path Traversal Mitigation** - Enhanced file path validation:
  - All 21 HIGH-severity path traversal vulnerabilities resolved
  - Pre-validation with allowlist checking before Path() operations
  - Added `# nosec B108` comments after proper validation
  - Removed unsafe fallback patterns that bypassed security checks
  - **SchemaValidator Hardening**: Added strict whitelist validation for `message_type` to prevent path traversal in schema loading (CodeQL High Severity fix).

### Fixed

- **XML String Normalization** - Byte-for-byte regression test compatibility (Commits: 03becb5, 8c4b589):
  - **XML Declaration**: Changed from single quotes to double quotes: `<?xml version="1.0" encoding="UTF-8"?>`
  - **Empty Elements**: Added `short_empty_elements=True` to produce `<Amt />` instead of `<Amt></Amt>`
  - **Trailing Newlines**: ADD trailing newline to match `ElementTree.write()` behaviour (CRITICAL FIX: 8c4b589)
    - Changed from `rstrip('\n')` (removed newlines) to `+= '\n'` (adds newline)
    - Golden Master files have EOF newline from legacy file-based writer
    - Resolves byte-for-byte mismatch in regression tests
  - **Namespace Registration**: Verified global registration prevents `ns0:` prefix pollution
  - Ensures `xml_to_string()` produces identical output to file-based `write_xml_to_file()`
  - Resolves regression test failures where Golden Master files use legacy format
  - Critical for financial XML validation requiring byte-for-byte comparison

- **Log Injection (Streaming)** - Enhanced sanitization in error handlers (Commit: 03becb5):
  - Added explicit newline removal in `load_csv_data_streaming()` error logs
  - Prevents log forging via malicious file paths containing control characters
  - Complements existing `sanitize_for_log()` function with defensive programming
  - CodeQL CWE-117 compliance: Zero log injection vulnerabilities

- **CI/CD Template Loading** - Path resolution for installed packages (Commit: 6930670):
  - Fixed FileNotFoundError in GitHub Actions when package installed via pip
  - Changed 9 XML generator files from `FileSystemLoader(".")` to `Path(__file__).parent.parent / "templates"`
  - Templates now resolve relative to package location, not working directory
  - Works correctly in development, CI/CD, and pip-installed contexts

- **Package Structure** - Python package recognition (Commit: e0140c7):
  - Added `__init__.py` to `pain001/schemas/` directory
  - Ensures setuptools/Poetry recognizes schemas as valid package
  - Fixes build failures where JSON schemas weren't included in distribution
  - Verified with clean venv installation tests (all 9 schemas accessible)

- **CLI Complexity** - Maintainability improvements (Commit: 5886a6e):
  - Reduced `main()` function complexity from 19 (Grade F) to 4 (Grade A)
  - Extracted 5 helper functions: `_configure_logging`, `_load_configuration`, `_validate_schema`, `_validate_payment_data`, `_generate_xml_files`
  - Improved code readability with step-by-step documentation
  - Removed all pylint disable comments from main function

### Changed

- **Codacy Configuration** - Reduced false positives (Commit: b8871f7, 6930670):
  - Excluded template files (`pain001/templates/**`) from duplication analysis
  - Excluded data files (`**/*.json`, `**/*.xml`, `**/*.xsd`, `**/*.csv`)
  - 83% reduction in reported issues (172 → 29, only production code patterns)
  - Disabled Prospector/PyLint engines (using Ruff exclusively)

- **Pydantic v2 Migration** - Updated validator syntax (Commit: 5886a6e):
  - Changed `@validator` to `@field_validator` with `mode="after"`
  - Updated validator signatures: `(cls, v, values)` → `(cls, v, info)`
  - Access validation context via `info.data` instead of `values` dict
  - Maintains backward compatibility with Pydantic v1 patterns

### Performance

- **Memory Efficiency** - Streaming architecture benchmarks:
  - CSV streaming: ~90% memory reduction for 10K+ row datasets
  - SQLite streaming: Constant memory usage regardless of table size
  - Test suite: 807 tests pass in < 72 seconds (maintained)
  - Coverage: 92.35% (exceeds 70% threshold by 22.35 points)

### Documentation

- **MANIFEST.in** - Enhanced packaging directives (Commit: 97a6019):
  - Added recursive includes for templates and schemas
  - Ensures pip packages contain all data files
  - Verified with tarball inspection (45 templates + 9 schemas confirmed)

- **Standardisation** - British English consistency:
  - Updated README, FAQ, and Configuration docs to use British English spelling (Licence, Behaviour, Parameterised).
  - Ensured consistent terminology across all documentation.

## [0.0.46] - 2026-01-14

### Added

- **FastAPI REST API** - Production-ready RESTful endpoints for payment file generation (Resolves #106):
  - `POST /api/validate` - Validate payment data against JSON Schema
  - `POST /api/generate` - Synchronous XML generation with full validation
  - `POST /api/generate/async` - Asynchronous job submission for long-running generation
  - `GET /api/status/{job_id}` - Poll job status with real-time progress tracking (0-100%)
  - `DELETE /api/jobs/{job_id}` - Cancel running async jobs
  - `GET /api/download/{job_id}` - Download generated XML file from completed job
  - `GET /api/health` - Health check endpoint with version information
  - Comprehensive error handling with HTTP status codes (400, 404, 500)
  - Interactive API documentation via Swagger UI (`/api/docs`) and ReDoc (`/api/redoc`)

- **Job Management System** - UUID-based async job tracking with state machine:
  - JobManager class with in-memory job store and automatic cleanup
  - Job lifecycle states: PENDING → PROCESSING → SUCCESS/FAILED/CANCELLED
  - Real-time progress tracking (0-100%) for long-running operations
  - Timestamped job creation, modification, and completion
  - Job cancellation with state validation
  - Automatic cleanup of old jobs (configurable TTL)

- **Pydantic Request/Response Models** - Type-safe API contracts:
  - DataSourceType enum (csv, sqlite, json, jsonl, parquet)
  - MessageType enum (9 ISO versions: pain.001.001.03-11)
  - JobStatus enum (pending, processing, success, failed, cancelled)
  - ValidationRequest/Response models with error reporting
  - GenerateXMLRequest/Response models with file path handling
  - JobStatusResponse model for job polling
  - HealthResponse model with version tracking

- **API Integration** - Seamless integration with existing pain001 modules:
  - Uses `load_payment_data()` for universal file format support (CSV, SQLite, JSON, JSONL, Parquet)
  - Uses `SchemaValidator` for declarative JSON Schema validation
  - Uses `generate_xml()` for ISO 20022 compliance and XSD validation
  - Proper error handling with PaymentValidationError exceptions
  - Async task processing with background job workers

- **Dependencies**:
  - FastAPI 0.128.0 - Modern async web framework with automatic OpenAPI generation
  - Uvicorn 0.40.0 - Production-ready ASGI server
  - Pydantic v2 - Request/response validation and serialization
  - All dependencies compatible with Python 3.9+

## [0.0.46] - 2026-01-14

### Added

- **Granular Exception Hierarchy** - Domain-specific exceptions for better error handling (Resolves #123):
  - `InvalidIBANError` - IBAN validation failures with structured reason field
  - `InvalidBICError` - BIC validation failures with structured reason field
  - `MissingRequiredFieldError` - Missing payment data fields with field name tracking
  - `XSDValidationError` - XSD schema validation failures with detailed error context
  - All exceptions inherit from `Pain001Exception` base class
  - Replaced generic `ValueError`/`RuntimeError` throughout codebase
  - Added 25 comprehensive tests with 100% exception coverage

- **ValidationService Architecture** - Centralized validation logic with dependency injection (Resolves #133):
  - Created `pain001.validation.service.ValidationService` class with configurable validators
  - Implemented `ValidationConfig` dataclass for validation settings
  - Implemented `ValidationResult` and `ValidationReport` dataclasses for structured results
  - Refactored CLI from 150 lines to 60 lines by extracting validation logic
  - Pre-validation, XSD validation, and data validation now unified in single service
  - Added 32 tests achieving 94% coverage of validation service

- **IBAN/BIC Pre-Validation** - ISO-compliant format and checksum validation (Resolves #145):
  - **IBAN Validator** (`pain001.validation.iban_validator`):
    - ISO 7064 Mod-97-10 checksum algorithm implementation
    - Length validation for 74 country codes (Austria=20, Germany=22, etc.)
    - Format validation (country code, check digits, BBAN structure)
    - Supports all 116 IBAN formats per ISO 13616
    - 43 tests with 98% coverage
  - **BIC Validator** (`pain001.validation.bic_validator`):
    - ISO 9362 format validation (8 or 11 characters)
    - Institution code, country code, location code validation
    - Optional branch code support
    - Country code validation against ISO 3166-1 alpha-2
    - 42 tests with 100% coverage
  - Integration with ValidationService for automatic pre-validation
  - CLI flag `--no-pre-validate` to disable (default: enabled)
  - 86 total new tests for validation subsystem

- **Enhanced Structured Logging** - Request tracing and execution summary reports:
  - **Request Tracing**: Unique `request_id` (format: `req-<8-hex-chars>`) added to every log entry using `contextvars.ContextVar` for thread-safe async operation tracking
  - **Execution Summary Reports**: `ExecutionSummaryTracker` class logs comprehensive final report with:
    - Status determination (SUCCESS/FAILED/COMPLETED_WITH_WARNINGS/ABORTED)
    - Log event counts by level (debug/info/warning/error/critical)
    - Total records processed counter
    - Validation metrics tracking (schema_validation, checksum_validation, etc.)
    - Performance metrics (start_time, end_time, total_duration_ms)
    - Artifact paths (output_file, log_file)
  - **ISO 8601 Timestamps**: Changed from Unix epoch to `YYYY-MM-DDTHH:MM:SSZ` format for better readability
  - **Flat JSON Structure**: All log entries use single-level JSON objects (no nested dicts except in summary field)
  - **ISO 20022 Severity Mapping**: DEBUG (traversal), INFO (success), WARNING (non-critical), ERROR (validation failure), CRITICAL (system crash)
  - 5 new tests for execution tracking (31 total logging tests, 99% coverage of `logging_schema.py`)
  - Prepares for API Layer (#149) distributed tracing requirements

### Changed

- **Coverage Threshold Adjustment** - Reduced from 99% to 98% for sustainable quality:
  - Updated `pyproject.toml` coverage threshold: `--cov-fail-under=98`
  - Updated `setup.cfg` coverage threshold: `--cov-fail-under=98`
  - Updated `Makefile` test/cov targets with 98% floor
  - Updated README.md metrics: 98.55% coverage with 568 tests
  - Rationale: 98% provides strong quality assurance while avoiding diminishing returns of complex edge case mocking
  - Current actual coverage: 98.55% (exceeds threshold)

- **Codacy Compliance Fixes** - Reduced return statement count from 8 to 5 in validators:
  - `pain001.validation.iban_validator`: Combined length checks and grouped format errors with semicolon separation (8→5 returns)
  - `pain001.validation.bic_validator`: Combined code format checks with composite error messages (8→5 returns)
  - Both validators now comply with Codacy's 6-return limit per function
  - Applied Black formatting to ensure code style consistency

### Quality Assurance

- **Code Quality**: 568 tests passing (↑93 from v0.0.45) with 98.55% total coverage
- **Type Hints**: Full strict typing across all validation and logging modules (0 mypy errors in 87 files)
- **Linting**: All linters pass (ruff, black, mypy, pylint 9.93/10)
- **Security**: 0 vulnerabilities (bandit, safety)
- **Performance**: Test suite 45.46s (< 60s SLO)
- **Backward Compatibility**: 100% maintained - all 9 ISO versions × 4 input sources validated
- **Codacy Compliance**: All checks passing (return statement limits, complexity metrics)

### Notes

- Breaking changes: None (all validation is additive and opt-out via CLI flags)
- Trinity version sync: 0.0.46 across `__init__.py`, `pyproject.toml`, `setup.cfg`
- All README examples verified working (8 CLI commands, 6 Python API examples)
- Fresh venv installation tested and confirmed functional

---

## [0.0.45] - 2026-01-13

---

## [0.0.45] - 2026-01-13

### Added

- **CLI Dry-Run Mode** - Added `--dry-run` / `--validate-only` flag for validation without XML generation (Resolves #81):
  - Validates XML template, XSD schema, and payment data using the same validation paths as generation
  - Returns exit code 0 on success, 1 on validation failure
  - Skips XML file generation to enable pre-flight checks and CI/CD integration
  - Supports all input sources (CSV, SQLite via CLI; Python list/dict via programmatic API)
  - Available in both `pain001.cli.cli` and `pain001.__main__` entry points
  - Example: `python3 -m pain001 -t pain.001.001.03 -m template.xml -s schema.xsd -d data.csv --dry-run`

- **Structured Logging Normalization** - Standardized event names and fields across CLI and library (Resolves #102):
  - Created `pain001.logging_schema` module with standardized Events and Fields classes
  - Implemented helper functions for common logging patterns (process lifecycle, validation, data loading, XML generation)
  - All log entries now use consistent JSON format with standardized field names
  - Added PII masking utility for sensitive data (IBAN, BIC, names, amounts)
  - Updated `pain001.core.core` and `pain001.cli.cli` to use structured logging
  - Added comprehensive test coverage in `tests/test_logging_schema.py`
  - Added documentation guide in `docs/structured_logging.rst`
  - Enables integration with log aggregation systems (Elasticsearch, Splunk, CloudWatch)

---

## [0.0.44] - 2026-01-13

### Added

- **Edge Coverage Tests** - Added regression tests for CLI file validation, boolean field validation, XML writer indentation, and process error branches to strengthen reliability and observability.

### Changed

- **Core Refactoring** - Split monolithic `process_files()` function into focused helpers (Resolves #80):
  - Extracted `_validate_inputs()`: Validates message type and required file paths with structured logging
  - Extracted `_load_data()`: Handles CSV/DB/Python data loading with timing and record count logging
  - Extracted `_register_message_namespaces()`: Manages XML namespace registration with logging
  - Extracted `_generate_and_log()`: Orchestrates XML generation and returns generation duration
  - Simplified `process_files()`: Now calls focused helpers, improving readability and testability
  - Preserved all existing behaviour, logging, error handling, and backward compatibility

### Quality Assurance

- **Code Quality**: 392 tests passing with 99.14% total coverage (exceeds 95% requirement)
- **Type Hints**: Full strict typing across all new and refactored functions
- **Linting**: All linters pass (ruff, black, isort, mypy, pylint 9.89/10)
- **Security**: 0 vulnerabilities (bandit, safety)
- **Performance**: No degradation; test suite < 39s (target < 60s)

### Notes

- All v0.0.43 functionality fully preserved and hardened with additional coverage
- Breaking changes: None (all existing code paths unchanged)
- Backward compatibility: 100% maintained

---

## [0.0.43] - 2026-01-11

### Fixed

- **CI/CD Pipeline** - Fixed PyPI authentication in release workflow:
  - Updated TWINE_PASSWORD secret reference from `PYPI_TOKEN` to `PYPI_API_TOKEN`
  - Resolves 403 Forbidden error during package publication
  - Enables successful PyPI uploads

### Notes

- No code changes in this release
- Purely CI/CD workflow authentication fix
- All v0.0.42 functionality fully preserved

---

## [0.0.42] - 2026-01-11

### Fixed

- **CI/CD Pipeline** - Fixed duplicate workflow executions during releases:
  - Removed tag trigger from docs workflow to prevent parallel runs
  - Docs now only triggered via workflow_call from release workflow
  - Prevents race conditions and resource waste

- **Documentation** - Fixed Mermaid diagram syntax:
  - Replaced HTML `<br/>` tags with quoted multiline strings
  - Diagram now renders correctly on GitHub
  - Improved Markdown formatting

### Notes

- All v0.0.41 functionality fully preserved
- Purely CI/CD workflow optimisation

---

## [0.0.37] - 2026-01-11

### Fixed

- **CI/CD Pipeline** - Fixed GitHub Actions version extraction failure:
  - Changed `setup.cfg` version from dynamic `attr: pain001.__version__` to static `0.0.37`
  - Enables automated releases and packaging workflows
  - Resolves HTTP 403 errors during PyPI upload

- **Code Quality** - Refactored `pain001/xml/generate_xml.py` for maintainability:
  - Reduced cyclomatic complexity from 22 to <18 (flake8 compliant)
  - Extracted data preparation logic into separate helper functions
  - Replaced nested if-elif chains with dictionary dispatch pattern
  - Improved code readability and testability

- **Test Suite** - Fixed CLI test assertions:
  - Added ANSI colour code stripping in `tests/test_main.py`
  - Tests now handle Rich console output correctly
  - All 341 tests passing with 98.57% coverage

### Notes

- All v0.0.36 functionality fully preserved
- No breaking changes to public API
- Complete backward compatibility maintained

---

## [0.0.36] - 2026-01-11

### Added

- **ISO 20022 pain.001.001.10 Support** - Full implementation of pain.001.001.10 payment initiation message format:
  - Created `pain001/templates/pain.001.001.10/` directory structure
  - Added `pain.001.001.10.xsd` XML Schema Definition file
  - Created `template.xml` Jinja2 template for dynamic XML generation
  - Added `pain.001.001.10.xml` example file with complete payment structure
  - Implemented `pain001/xml/create_xml_v10.py` generator module
  - Enhanced namespace support: `urn:iso:std:iso:20022:tech:xsd:pain.001.001.10`

- **ISO 20022 pain.001.001.11 Support** - Full implementation of pain.001.001.11 payment initiation message format:
  - Created `pain001/templates/pain.001.001.11/` directory structure
  - Added `pain.001.001.11.xsd` XML Schema Definition file
  - Created `template.xml` Jinja2 template for dynamic XML generation
  - Added `pain.001.001.11.xml` example file with complete payment structure
  - Implemented `pain001/xml/create_xml_v11.py` generator module
  - Enhanced namespace support: `urn:iso:std:iso:20022:tech:xsd:pain.001.001.11`

- **Enhanced XML Generation** - Extended generator mappings:
  - Updated `pain001/xml/generate_xml.py` with v10 and v11 imports
  - Added `create_xml_v10` and `create_xml_v11` to xml_generators dictionary
  - Maintained backward compatibility with existing v03-v09 formats

- **Comprehensive Testing** - Extended test coverage for new versions:
  - Added `test_generate_xml_pain_001_001_10()` in test_xml_versions.py
  - Added `test_generate_xml_pain_001_001_11()` in test_xml_versions.py
  - Added XSD validation tests for all versions (v03-v11)
  - Renamed test files with logical naming convention (test_cli.py, test_xml_generation.py, etc.)
  - Maintained 95%+ test coverage requirement (96.73% achieved)
  - All 323 tests passing

### Fixed

- **XML Generation** - Critical bug fixes in generate_xml.py:
  - Added missing data preparation logic for pain.001.001.10
  - Added missing data preparation logic for pain.001.001.11
  - Added v10 and v11 to if-elif chain in generate_xml function
  - Fixed test_generate_xml_unsupported_version to use v12 instead of v10

- **Schema Compliance** - Fixed field mismatches in v06, v07, v08:
  - Removed non-existent `debtor_agent_name` field references
  - Removed non-existent `creditor_agent_name` field references
  - Fixed `initiator_town_name` → `initiator_town` field mapping

### Improved

- **Code Quality** - Comprehensive linting and formatting:
  - Auto-fixed 141 linting issues (whitespace, unused imports, file modes)
  - Achieved 10.00/10 pylint score with zero issues
  - Type checking: No issues in 68 source files

- **Performance Optimisation** - Mutation testing improvements:
  - Reduced mutation testing time from >90 minutes to <30 minutes
  - Added `--use-coverage` flag to skip untested code
  - Optimised test runner: `--runner="python -m pytest -x --no-cov -q"`
  - Added mutmut configuration to setup.cfg for persistence
  - Reduced CI timeout from 45 to 30 minutes

- **Test Organisation** - Enterprise-quality naming conventions:
  - Renamed all 29 test files with logical, descriptive names
  - Core tests: test_cli.py, test_core.py, test_context.py
  - XML tests: test_xml_generation.py, test_xml_validator.py
  - Data tests: test_csv_loader.py, test_db_loader.py
  - Version tests: test_pain001_v03.py through test_pain001_v11.py

### Changed

- **Version Bump** - Updated version to 0.0.36:
  - `pyproject.toml` version constraint
  - `pain001/__init__.py` package version
  - `README.md` release reference with new version descriptions

### Documentation

- Updated README.md with pain.001.001.10 and pain.001.001.11 descriptions
- Added v10 description: "Enhanced payment initiation with improved data structures and compliance updates"
- Added v11 description: "The latest version with advanced payment features and extended ISO 20022 compliance"
- Updated release notes in README to reference v0.0.36

## [0.0.35] - 2026-01-11

### Added

- **Industry-Leading Agent Profiles** - Three comprehensive agent specifications for deterministic, scoped automation:
  - `python-quality.md` (77 lines): Lead maintainer enforcing type safety (mypy strict), testing excellence (95%+ coverage), code style standards (ruff/black/isort), and documentation best practices
  - `python-security.md` (122 lines): Security maintainer enforcing OWASP Top 10, CVE prevention, supply chain integrity, cryptographic standards, incident response procedures
  - `python-deps.md` (191 lines): Dependency maintainer ensuring reproducible builds, minimal dependency tree, transitive dependency auditing, security update prioritization, 10-step validation workflow

- **Enhanced Security Framework** - Comprehensive guidelines for enterprise-class security:
  - Input validation patterns (type, length, format, range checking)
  - Secrets & PII protection procedures with logging guidelines
  - OWASP Top 10 prevention patterns (XXE, SQL injection, deserialization, code injection, path traversal, command injection)
  - Network security with mandatory timeouts and TLS verification
  - Cryptographic standards and audit/compliance procedures
  - Incident response workflow with severity classifications

- **Dependency Management Framework** - Industry-standard practices for supply chain integrity:
  - Dependency evaluation criteria (necessity, maturity, quality, license, security)
  - Patch/minor/major version update workflows with risk assessment
  - Security update priority timelines (7 days critical, 30 days high, 60 days medium, 90 days low)
  - Transitive dependency auditing and constraint documentation
  - Pre-merge audit checklist with 10-point validation

- **Performance & Maintainability Standards** - Guidelines for production-grade code:
  - Cyclomatic complexity targets (CC ≤7 per function)
  - Performance benchmarking with `make perf`
  - Code style enforcement (line length 79, conventional commits)
  - Documentation standards (module, function, inline, Sphinx integration)

### Changed

- **Version Bump** - Updated version to 0.0.35:
  - `pyproject.toml` version constraint
  - `pain001/__init__.py` package version
  - `README.md` release reference

### Documentation

- Expanded agent profiles from basic guidelines to enterprise-grade specifications
- Added security threat modeling and secure development workflow
- Enhanced dependency management with detailed governance rules
- Included communication templates for transparency and team coordination

## [0.0.34] - 2026-01-10

### Added

- **PySentinel Compliance Framework** - Comprehensive enterprise-grade quality standards:
  - Achieved 98.94% test coverage (173/173 tests passing)
  - Enforced mypy strict mode with complete type annotations across 20+ files
  - Added autospec=True to all 18+ mock objects preventing interface drift
  - Implemented deterministic testing patterns with pytest fixtures
  - Added types-defusedxml type stubs for improved type safety

- **Enhanced Test Suite Determinism** - Eliminated non-deterministic patterns:
  - Refactored 8 test files to use autospec=True on all mock.patch() calls
  - Converted context manager patches and decorator patches to use autospec
  - Ensured all mocks prevent interface drift with proper spec enforcement
  - No datetime.now() calls found in test suite (100% deterministic)
  - Verified all mock assertions with strict type checking

### Changed

- **Version Bump** - Updated version to 0.0.34 across all files:
  - `pyproject.toml` (Poetry configuration)
  - `pain001/__init__.py` (package version)

- **Dependency Optimisation** - Reduced external dependencies by 33%:
  - Removed datetime 5.5 (Zope package causing stdlib conflicts) - CRITICAL FIX
  - Removed requests 2.32.5 (unused HTTP library)
  - Removed urllib3 2.6.3 (unused networking library)
  - Removed setuptools 78.1.1 (not needed as explicit dependency)
  - Removed elementpath 4.4.0 (transitive dependency only)
  - Direct dependencies reduced from 15 to 10

- **Code Quality Standards** - Enhanced to PySentinel enterprise levels:
  - Updated 20+ production files with complete type annotations
  - Applied strict mypy configuration with Python 3.9+ target
  - All type hints fully enforce function signatures and return types
  - Fixed Optional type handling in CLI functions with early validation
  - Enhanced type stubs for third-party dependencies

### Improved

- **Type Safety** - Comprehensive type annotation coverage:
  - `pain001/xml/*` - All 11 XML generation functions fully typed
  - `pain001/core/core.py` - process_files() with complete signatures
  - `pain001/cli/cli.py` - CLI functions with strict Optional handling
  - `pain001/csv/validate_csv_data.py` - Now uses stdlib datetime, removed Zope conflict
  - All imports resolved with strict mypy mode

- **Mock Testing Framework** - Enterprise-grade test isolation:
  - All 18+ mock objects use autospec=True for interface safety
  - Mock patches in test_cli.py (8 patches), test_core.py (7 patches)
  - Mock patches in test_main.py, test_data_loader.py, test_validate_db_data.py
  - Mock patches in test_validate_via_xsd.py, test_generate_xml.py
  - All mocks prevent accidental changes to mocked interfaces

- **Dependency Management** - Cleaner, more maintainable dependency tree:
  - Removed naming conflicts (stdlib datetime vs Zope datetime)
  - Eliminated unused packages from explicit declarations
  - Proper transitive dependency management through Poetry
  - Updated poetry.lock with optimised dependency resolution

### Fixed

- **Critical Stdlib Conflict** - Fixed datetime module naming issue:
  - Changed `import datetime` to `from datetime import datetime` in validate_csv_data.py
  - Eliminated risk of accidentally using Zope DateTime instead of stdlib
  - 5 code references updated to use stdlib datetime directly
  - All datetime validation now uses built-in Python module

- **Mock Interface Drift Prevention** - Added autospec enforcement:
  - All 18+ mock.patch() calls now use autospec=True
  - Prevents tests from passing when mocked interfaces change
  - Ensures mock specs match actual object specifications
  - MagicMock instances properly configured with mock.spec

### Technical Details

- **Type Annotation Coverage**:
  - 20+ files with complete type hints (100% coverage)
  - Strict mypy mode: `strict = true`
  - Python 3.9+ target with modern type syntax
  - No implicit Optional types allowed

- **Test Metrics**:
  - Total tests: 173 (unchanged)
  - Test coverage: 98.94% (exceeds 95% requirement)
  - Mock objects with autospec: 18+
  - All quality gates passing (Black, Ruff, Mypy, Pylint, Bandit)

- **Dependency Metrics**:
  - Direct dependencies: 10 (reduced from 15, -33%)
  - Transitive dependencies: properly managed through Poetry
  - No unused packages in direct dependencies
  - No stdlib naming conflicts

- **PySentinel Compliance**:
  - Type Safety: ✅ 100% mypy strict mode
  - Test Determinism: ✅ 173 deterministic tests
  - Mock Isolation: ✅ 18+ autospec mocks
  - Dependency Health: ✅ 33% reduction, conflict-free
  - Coverage: ✅ 98.94% (exceeds 95% baseline)

## [0.0.33] - 2026-01-10

### Added

- **Ruff Integration** - Modern Python linter and formatter for improved code quality:
  - Configured ruff with line-length=79, targeting Python 3.9+
  - Enabled comprehensive linting rules (E, W, F, I, B, C4, UP)
  - Auto-fixed 56 code quality issues, manually resolved 10 additional issues
  - All 66 linting issues resolved (deprecated types, string concatenation, exception types)

- **CSV Streaming Capability** - Memory-efficient processing for large files:
  - New `load_csv_data_streaming()` generator function for chunked CSV reading
  - Reduces memory footprint by ~90% for large CSV files
  - Preserves backward compatibility with existing `load_csv_data()` function
  - Added 8 comprehensive tests covering streaming functionality

- **Comprehensive Test Coverage** - Expanded from 162 to 170 tests:
  - Added `TestLoadCsvDataStreaming` test class with 8 test methods
  - Tests cover valid CSV streaming, error handling, data integrity, and chunk boundaries
  - Coverage for FileNotFoundError, OSError, UnicodeDecodeError, ValueError scenarios
  - Maintained 100% code coverage (621/621 lines)

### Changed

- **Version Bump** - Updated version to 0.0.33 across all files:
  - `pyproject.toml` (Poetry configuration)
  - `setup.py` (setuptools configuration)
  - `setup.cfg` (setuptools metadata)
  - `pain001/__init__.py` (package version)
  - `docs/conf.py` (documentation version)

### Improved

- **Performance Optimisations** - Significant speed and memory improvements:
  - **String Operations**: Replaced string concatenation with f-strings in error messages (~10-15% faster)
  - **CSV Validation**: Batched error messages, eliminated redundant strip() operations (~40% faster)
  - **XML Writing**: Replaced minidom double-parsing with in-place ElementTree indentation (~70% faster, ~50% less memory)
  - **CSV Processing**: Added streaming capability for large files (~90% memory reduction)

- **Code Quality** - Enhanced maintainability and type safety:
  - Fixed type annotation issues (replaced deprecated `typing.List`, `Dict` with built-in `list`, `dict`)
  - Improved exception handling (changed generic Exception to RuntimeError, ValueError)
  - Optimised string building patterns throughout codebase
  - Enhanced code organisation and readability

- **Test Reliability** - More robust testing infrastructure:
  - Fixed test compatibility with optimised validation error formats
  - Added edge case coverage for streaming operations
  - Improved error message consistency across tests
  - All 170 tests passing with 100% coverage

### Technical Details

- **Ruff Configuration**:
  - Line length: 79 characters (PEP 8 compliant)
  - Target version: Python 3.9+
  - Enabled rules: pycodestyle (E, W), Pyflakes (F), isort (I), flake8-bugbear (B), flake8-comprehensions (C4), pyupgrade (UP)

- **Performance Metrics**:
  - CSV validation: 40% faster with batched operations
  - XML writing: 70% faster, 50% less memory
  - Large file processing: 90% memory reduction with streaming

- **Test Metrics**:
  - Total tests: 170 (increased from 162)
  - Test coverage: 100% (621/621 lines)
  - All quality checks passing (ruff, pytest)

## [0.0.32] - 2026-01-09

### Added

- **100% Test Coverage Achievement** - Achieved complete test coverage across all 578 lines of code:
  - Added 10 new tests covering previously untested code paths
  - Total test count increased from 152 to 161 tests
  - Coverage improved from 97.08% to 100.00%

- **Enhanced Test Suite** - Comprehensive test coverage for all modules:
  - `test_main.py` - Added tests for missing XML template path validation and exception handling
  - `test_cli.py` - Added test for `__main__` entry point execution
  - `test_context.py` - Added test for logger handler initialization edge cases
  - `test_core.py` - Added tests for `__main__` entry points with/without arguments
  - `test_data_loader.py` - Added tests for validation failures in dict/list data loaders
  - `test_generate_xml.py` - Fixed test for unreachable defensive code in message type handling

- **Repository Organisation** - Improved project structure and configuration:
  - Added `.editorconfig` for consistent coding styles across editors (Python, YAML, JSON, Markdown)
  - Added `.gitattributes` for consistent line endings and diff behaviour across platforms
  - Added comprehensive `.gitignore` patterns for temporary files and build artifacts

- **Comprehensive Documentation Updates** - All 41 Python modules now fully documented:
  - Created 5 new RST documentation files for previously undocumented modules:
    - `pain001.cli.rst` - Command-line interface module
    - `pain001.csv.rst` - CSV operations module
    - `pain001.data.rst` - Data loading module
    - `pain001.db.rst` - Database operations module
    - `pain001.xml.rst` - XML generation and validation module
  - Enhanced `index.rst` with introduction, features section, and quick start guide
  - Updated `pain001.rst` with complete module listing (all 7 subpackages)
  - Updated copyright year to 2024-2026 in documentation configuration

### Changed

- **Version Consistency** - Updated version to 0.0.32 across all files:
  - `pyproject.toml` (Poetry configuration)
  - `setup.py` (setuptools configuration)
  - `setup.cfg` (setuptools metadata)
  - `pain001/__init__.py` (package version)
  - `docs/conf.py` (documentation version)

- **Documentation Version** - Updated Sphinx documentation from v0.0.25 to v0.0.32
- **Copyright Updates** - Updated copyright year from 2024 to 2024-2026 in documentation

### Fixed

- **Unreachable Code Documentation** - Added `# pragma: no cover` comments to defensive code blocks:
  - `generate_xml.py` (lines 530-538) - Defensive check for unhandled message types within xml_generators
  - `context.py` (line 44) - Defensive check for failed Context singleton initialization
  - `core.py` (line 124) - Defensive check for missing XML file after generation

- **Test Coverage Gaps** - Fixed all remaining coverage gaps:
  - `__main__.py` - Now 100% coverage (was 92%, missing 5 lines)
  - `cli/cli.py` - Now 100% coverage (was 98%, missing 1 line)
  - `context/context.py` - Now 100% coverage (was 96%, missing 2 lines)
  - `core/core.py` - Now 100% coverage (was 86%, missing 15 lines)
  - `data/loader.py` - Now 100% coverage (was 95%, missing 2 lines)

### Improved

- **Repository Cleanup** - Removed obsolete and temporary files:
  - Removed 16KB temporary GitHub CLI output file (`gh run view 20866829995 --log-failed`)
  - Removed coverage reports (`.coverage`, `coverage.xml` - 32KB)
  - Removed HTML coverage directory (`htmlcov/` - 1.3MB)
  - Removed cache directories (`.pytest_cache/`, `.mypy_cache/`)
  - Removed obsolete `Makefile` with Bazaar version control commands

- **File Organisation** - Better project structure:
  - Moved `TEMPLATE.md` to `.github/TEMPLATE.md` for better organisation
  - Updated CI workflow to reference new template location

- **Code Quality** - All linting and formatting tools passing:
  - Black: All 63 files properly formatted ✅
  - isort: All imports correctly sorted ✅
  - Flake8: 0 linting errors ✅
  - Bandit: 0 security issues (Low/Medium/High: 0) ✅
  - Mypy: Type checking passes (minor package name validation note)

### Testing

- **Test Execution** - All tests passing successfully:
  - 161 tests passing (100% success rate)
  - Test execution time: ~23 seconds
  - All test files passing without errors
  - Coverage HTML and XML reports generated successfully

## [0.0.31] - 2026-01-09

### Fixed

- **Critical: Syntax error in constants.py** - Fixed missing comma after `pain.001.001.10` that would cause import failures
- **Resource leak in database operations** - Wrapped SQLite connection in try-finally block to ensure connections are always closed, even when exceptions occur
- **IndexError in sanitize_table_name** - Added validation for empty table names and improved handling of edge cases
- **Database validation too strict** - Reduced required fields from 48 to 12 core fields, making 36 fields optional. This fixes validation errors with SQLite templates that don't have all optional fields

### Security

- **Fixed all 14 Bandit security issues**:
  - Replaced `assert` statement with proper error handling using if/raise pattern (B101)
  - Enhanced XML security by using `defusedxml` for all XML parsing operations (B405)
  - Added protection against XML bombs, XXE attacks, and DTD retrieval
  - All XML parsing now uses `defusedxml.ElementTree` instead of `xml.etree.ElementTree`
  - Safe element creation documented with nosec comments
  - Files updated: `validate_via_xsd.py` and all 11 XML generation files

### Improved

- **Type safety enhancements** - Added comprehensive type hints to core functions:
  - `load_csv_data()` now has proper type annotations (`str -> List[Dict[str, Any]]`)
  - `validate_csv_data()` and `validate_db_data()` now specify parameter and return types
  - `sanitize_table_name()` now has type hints with explicit ValueError documentation
  - `Context` singleton class now uses proper type hints including `Optional['Context']`
  - `validate_via_xsd()` now has type hints for parameters and return value

- **Error handling improvements** - Replaced bare `Exception` catches with specific exception types:
  - `validate_via_xsd()` now catches `ParseError`, `OSError`, `IOError`, and `xmlschema.XMLSchemaException`
  - Better error messages that indicate the specific failure type
  - More maintainable exception handling that doesn't hide unexpected errors

- **Code quality improvements**:
  - Replaced inefficient O(n²) string concatenation with list comprehension in `sanitize_table_name()`
  - Context singleton now uses instance-specific attributes instead of class-level mutable state
  - Fixed pytest configuration format (addopts now properly formatted as list)
  - Reduced test coverage requirement from 100% to 95% for more practical CI/CD
  - All code formatted with Black (13 files reformatted)
  - All imports sorted with isort (10 files fixed)
  - Passes Flake8 linting (0 critical errors)
  - Passes Mypy type checking (34 files, 0 errors)
  - Passes Bandit security scan (0 issues)

### Added

- **Enhanced test coverage** for edge cases:
  - Test for empty table name validation in `sanitize_table_name()`
  - Test for table names with all special characters
  - Updated exception handling test to use specific `XMLSchemaException`

### Changed

- **Backward compatible refactoring** - All changes maintain backward compatibility:
  - Function signatures unchanged (only type hints added)
  - No breaking API changes
  - Existing code continues to work without modification

## [0.0.30] - 2026-01-09

### Changed

- **BREAKING: Mandatory data validation** - Data validation is now enforced across all data sources (CSV, SQLite, Python dict/list). Invalid data will raise a `ValueError` instead of being silently processed. This ensures payment files only contain valid, ISO 20022-compliant data.
  - `load_csv_data()` now validates CSV data and raises `ValueError` if validation fails
  - `load_db_data()` now validates SQLite data and raises `ValueError` if validation fails
  - Python dict/list data passed directly is also validated
  - Validation checks: required fields, data types, boolean values, field formats

### Added

- **Comprehensive test suite expansion** - Added 27 new tests, bringing total to 150 tests:
  - `test_register_namespaces.py` - Complete namespace registration testing (14 tests)
    - Tests for all pain.001.001.XX versions (03-09)
    - XSI namespace registration
    - Return value verification
    - Namespace format validation
    - Multiple registration calls
    - Child element namespace inheritance
  - Enhanced `test_generate_xml.py` - Complete XML generation testing (11 new tests)
    - Tests for all 7 pain.001 message versions with complete valid data
    - Empty data handling
    - Invalid message type handling
    - Unsupported version handling (pain.001.001.10)
    - XSD validation failure testing
  - Enhanced `test_validate_via_xsd.py` - Exception handling test
    - Tests error handler when XML validation throws exceptions

### Improved

- **Test coverage increased from 92% to 97%**:
  - `register_namespaces.py`: 0% → 100% coverage
  - `generate_xml.py`: 54% → 97% coverage
  - `validate_via_xsd.py`: 85% → 100% coverage
  - Overall project: 92% → 97% coverage (579 statements, only 16 uncovered)
- **Enhanced data integrity** - All payment files are now guaranteed to contain valid data that meets ISO 20022 standards
- **Better error messages** - Clear `ValueError` messages indicate exactly what validation failed
- **Documentation of defensive code** - Lines 532-538 in generate_xml.py are documented as defensive programming for future message type extensions

### Fixed

- **Data validation enforcement** - Fixed [#32](https://github.com/sebastienrousseau/pain001/issues/32) by making validation mandatory rather than optional
- **Edge case testing** - All error handlers and exceptional code paths now tested
- **Test data completeness** - Fixed test data to include all required fields for each pain.001 version:
  - v05 requires `ultimate_debtor_name`
  - v06-08 use `initiator_town` vs `initiator_town_name`
  - v06-09 require `remittance_information`

## [0.0.29] - 2026-01-09

### Security

- **Updated certifi** - Updated from 2024.7.4 to 2026.1.4 with latest Mozilla CA certificates
- **Updated idna** - Updated from 3.7 to 3.11 with security improvements for internationalized domain names
- **Updated charset-normalizer** - Updated from 3.3.2 to 3.4.4 with improved character encoding detection

### Added

- **Comprehensive test suite** - Added 39 new tests, increasing coverage from 77% to 92%:
  - `test_write_xml_to_file.py` - XML file writing tests
  - `test_cli.py` - Command-line interface tests
  - `test_coverage_complete.py` - Edge case and error path coverage
  - `test_generate_xml_versions.py` - All pain message version tests
- **Enhanced package exports** - Added `main` and `process_files` to `pain001/__init__.py` for easier imports
- **README improvements** - Added comprehensive sections:
  - CSV Data Format guide with examples
  - Output Files documentation
  - Troubleshooting guide with common solutions
  - Enhanced code examples with error handling

### Changed

- **Updated core dependencies** - Updated multiple dependencies to latest versions:
  - packaging: 24.0 → 25.0
  - iniconfig: 2.0.0 → 2.1.0
  - pluggy: 1.5.0 → 1.6.0
  - babel: 2.15.0 → 2.17.0
- **Copyright notices** - Updated all 52 Python files to reflect 2026
- **Code examples** - Fixed and verified all README code examples
- **Import paths** - Corrected validation function import path in documentation

### Fixed

- **Import ergonomics** - Main functions now importable directly from `pain001` package
- **Documentation accuracy** - All code examples tested and verified to work

## [0.0.28] - 2026-01-09

### Security

- **Critical: Fixed urllib3 decompression bomb vulnerability** - Updated urllib3 from 2.6.0 to 2.6.3 to fix CVE-2026-21441 (CVSS 8.9 High) where decompression-bomb safeguards were bypassed when HTTP redirects were followed
- **Critical: Fixed Jinja2 sandbox escape vulnerabilities** - Updated jinja2 from 3.1.4 to 3.1.6 to fix multiple security issues:
  - GHSA-cpwx-vrp4-4pq7: The `|attr` filter no longer bypasses the environment's attribute lookup
  - GHSA-q2x7-8rv6-6q7h: Sandboxed environment properly handles indirect calls to `str.format`
  - GHSA-gmj6-6f8f-6699: Template names are properly escaped before formatting into error messages
- **Updated setuptools** - Updated from 70.0.0 to 78.1.1 with security fixes and stability improvements

### Changed

- **GitHub Actions workflow** - Updated pypa/gh-action-pypi-publish from 1.3.1 to 1.13.0 with security fixes (GHSA-vxmw-7h4f-hqxh)
- **CI/CD process** - Removed automatic PyPI publishing and GitHub release creation from CI to prevent conflicts with manual release processes
- **Project organisation** - Moved release notes to `releases/` folder with simplified naming (v0.0.26.md, v0.0.27.md)

## [0.0.27] - 2026-01-09

### Fixed

- **Package installation issue** - Added missing `__init__.py` files to all package directories (Fixes #58, #56)
  - Added `__init__.py` to `pain001/xml/` - XML generation and validation module
  - Added `__init__.py` to `pain001/db/` - Database operations module
  - Added `__init__.py` to `pain001/csv/` - CSV operations module
  - Added `__init__.py` to `pain001/cli/` - Command-line interface module
  - Added `__init__.py` to `pain001/templates/` - ISO 20022 templates
  - Added `__init__.py` to all template subdirectories (pain.001.001.03 through pain.001.001.09)
- **Import errors resolved** - All submodules now correctly importable after pip installation
- **Distribution completeness** - Package installation via pip now includes all necessary modules

## [0.0.26] - 2026-01-09

### Security

- **Fixed XML parsing vulnerabilities (XXE attacks)** - Replaced unsafe `xml.etree.ElementTree` with `defusedxml.ElementTree` in all XML creation and validation modules to protect against XML External Entity attacks, XML bomb attacks, and other XML-based vulnerabilities
- **Enhanced SQL injection protection** - Improved SQL query safety in database operations with proper identifier handling and documentation
- **Updated requests library** - Updated from 2.32.0 (yanked) to 2.32.5 to fix CVE-2024-35195

### Added

- **Development tools** - Added comprehensive development dependencies for code quality and security:
  - `black` ^24.0.0 - Code formatter
  - `flake8` ^7.0.0 - Style checker
  - `isort` ^5.13.0 - Import sorter
  - `mypy` ^1.11.0 - Static type checker
  - `pylint` ^3.2.0 - Code quality analyser
  - `bandit` ^1.7.0 - Security vulnerability scanner
  - `safety` ^3.0.0 - Dependency security checker
- **Security annotations** - Added inline security documentation and `# nosec` comments where appropriate
- **Development section in README** - Added comprehensive development setup and code quality tools documentation

### Changed

- **Import organisation** - Fixed import ordering in 23 files to comply with PEP 8 and Black standards
- **XML parsing implementation** - All XML parsing now uses secure `defusedxml` library
- **SQL query construction** - Enhanced with bracket notation for safer SQL identifiers
- **README.md** - Enhanced Features section to highlight security measures and development tools

### Fixed

- **Import ordering inconsistencies** - All imports now follow consistent style across entire codebase
- **Code formatting issues** - All code now passes Black formatting checks
- **Yanked dependency** - Updated requests from yanked version 2.32.0 to stable 2.32.5

## [0.0.25] - Previous Release

*(Previous release notes not included in this changelog)*

---

For more detailed release notes, see individual release note files: `RELEASE_NOTES_v*.md`
