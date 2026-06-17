# Pain001 Roadmap

## Mission

A robust, secure, high-performance ISO 20022 payment library with a small,
well-tested core and first-class developer surfaces (library, CLI, REST,
MCP, LSP).

## Where we are (v0.0.51)

- **Generation:** pain.001.001.03–12 and pain.008.001.02, registry-driven,
  `Decimal` end-to-end, mandatory XSD validation (XXE-safe).
- **Validation:** scheme rulebooks (`sepa-sct`, `sepa-sdd`, `sepa-inst`),
  IBAN/BIC/charset validators, structured per-row violations + remediation.
- **Parsers:** pain.002 status reports and camt.053 statements.
- **Inputs:** CSV, SQLite, JSON, JSON Lines, Parquet; streaming for large
  batches; version migration between pain.001 versions.
- **Surfaces:** CLI command suite; REST `/api/v1` (auth, rate limiting,
  durable jobs, OpenAPI/Scalar, Prometheus `/metrics`); MCP server; LSP
  server with editor diagnostics.
- **Quality:** ~1,150 tests, **100%** coverage (98% enforced floor),
  `mypy --strict`, 100% docstrings, ruff/pydoclint/bandit, CodeQL/Snyk/
  pip-audit clean.

Most of the prior roadmap (v12 support, streaming, CLI/REST, SEPA profiles,
metrics hooks, registry refactor, golden-file + mutation testing) has
**shipped**. The focus now shifts from breadth of *surfaces* to depth of
*domain* and project sustainability.

## Backlog (candidate, unordered)

### Domain depth
- Generate (not just parse) **pain.002** status reports and **camt.053**
  statements — completing the message round-trip for testing/simulation.
- More scheme profiles: SEPA SDD **B2B**, and a cross-border/CBPR+-style
  rulebook (non-EUR, BIC-mandatory).
- Additional message types as demand warrants.

### Operability & distribution
- Official **Docker image** and a published OpenAPI client SDK.
- Optional shared-store (Redis) backends for the job store and rate limiter
  to support multi-replica deployments.

### Project sustainability
- **Recruit a second maintainer** with independent release authority
  (see [GOVERNANCE.md](GOVERNANCE.md)) — the single highest-impact item.
- Keep `examples/`, `SCHEMES.md`, and `OPERATIONS.md` in lockstep with code
  (already enforced for examples in CI).

## How to contribute

1. Read [CONTRIBUTING.md](CONTRIBUTING.md) and [ARCHITECTURE.md](ARCHITECTURE.md).
2. Run the quality gate locally: `make lint && make type && make test`.
3. Good first areas: a new scheme profile ([SCHEMES.md](SCHEMES.md)), an
   input loader, or docs. Open an issue or discussion to claim one.

## Key metrics (current)

| Metric | Value |
| :--- | :--- |
| Tests | ~1,150 passing |
| Coverage | 100% (98% enforced floor) |
| Type checking | `mypy --strict`, clean |
| Docstrings | 100% (interrogate) |
| Security scans | CodeQL, Snyk, bandit, pip-audit — clean |

---

*Roadmap is indicative, not a commitment; the maintainer prioritises.*
