<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Security Policy

## Supported versions

Security patches are issued for the latest minor of the latest major.
While the project is pre-`1.0`, that means **the latest released
0.0.x and the immediately prior 0.0.x** receive security fixes; older
0.0.x versions do not.

| Version | Status | Receives security fixes? |
| :--- | :--- | :--- |
| `0.0.53` (latest) | Current | ✅ Yes |
| `0.0.52` | Prior | ✅ Yes (best effort, until v0.0.54 ships) |
| `≤ 0.0.51` | Old | ❌ No — upgrade |

Pre-1.0 deprecation runway: at least 6 weeks between announcing
end-of-support for a 0.0.x release and the next coordinated release.
1.0+ runway: at least 6 months.

## Reporting a vulnerability

**Do not open a public issue for security reports.**

Use one of the following private channels, in this order of
preference:

1. **GitHub Private Vulnerability Reporting**
   <https://github.com/sebastienrousseau/pain001/security/advisories/new>
   (the maintainers are notified automatically; do this first)
2. **Email**: `security@pain001.com` (PGP available on request)
3. **Direct message** to a maintainer listed in
   [MAINTAINERS.md](MAINTAINERS.md)

Please include:
- A description of the vulnerability and its potential impact
- A minimal reproducer (preferably a failing test case)
- The version(s) affected (`python -c "import pain001; print(pain001.__version__)"`)
- Any proposed remediation, if known

**Acknowledgement timeline**: within 48 hours.
**Triage**: a severity assessment and remediation plan within 7 days.
**Fix windows**: critical 7 days, high 30 days, medium 60 days, low
best-effort. The clock starts at triage, not at report.

We publish a CVE through GitHub Security Advisories (the GitHub
Advisory Database mirrors into OSV/PyPI) when the issue is fixed.
Reporters are credited unless they ask to remain anonymous.

## Security posture (current, as of v0.0.53)

### Input handling

- **XML parsing** (`pain.002`, `camt.053` inbound) is routed through
  [`defusedxml`](https://pypi.org/project/defusedxml/); XXE,
  billion-laughs, and external-entity resolution are rejected.
- **Path handling** uses a path validator (`pain001.security.path_validator`)
  that blocks traversal outside permitted directories. The
  v0.0.53-NEW REST API output directory is gated against the cwd
  and the system tmpdir only.
- **Schema validation** is mandatory. Output that does not validate
  against the official XSD is never written as a success.
- **Amounts** are `decimal.Decimal` end-to-end. Control sums
  (`CtrlSum`, `NbOfTxs`) are recomputed from the data, never echoed
  from input.
- **ISO 20022 charset guard** transliterates accented Latin and
  refuses characters outside the permitted set; the `sepa-b2b`
  profile additionally enforces FRST/RCUR sequence types and a
  mandatory creditor identifier.

### Template + Jinja safety

- XML templates render through a sandboxed Jinja environment.
- Filesystem-expanding Jinja directives (`include`, `import`,
  `extends` against arbitrary paths) are blocked. Bundled templates
  live under `pain001/templates/<message_type>/` and are guard-railed
  against template/XSD-version drift.

### Secrets handling

- The library ships no credentials, tokens, or example IBANs that
  resolve to real accounts.
- Structured logging redacts IBAN / BIC / name fields by default
  (`pain001.logging_schema.redaction`). Validation errors carry
  the rule id + field name; **never** the raw row value.
- The REST API's `PAIN001_API_KEY` is read from the environment,
  not from disk; tokens never persist beyond the process.

### Network surface

The REST API ships with:

- Bearer-token auth gated on `PAIN001_API_KEY` (off when unset —
  the install assumption is "behind a reverse proxy that handles
  auth").
- Configurable rate limiting (`PAIN001_RATE_LIMIT`) with both an
  in-process default and a v0.0.53-NEW Redis-backed distributed
  backend so caps survive multi-replica deployments.
- A versioned `/api/v1/*` surface; the unversioned `/api/*` alias
  is retained for backwards compatibility but **will be deprecated
  in v0.1**.
- Async-job state can be stored in-process (default), on disk
  (`PAIN001_JOB_STORE_DIR`), or in Redis (`PAIN001_JOB_STORE_URL`).
  No backend exposes job data over the network beyond the REST
  endpoints' bearer-gated paths.

### Dependency hygiene (CI-enforced on every commit)

| Tool | Scope | Cadence |
| :--- | :--- | :--- |
| **`pip-audit`** (migrated from `safety` in v0.0.53) | OSV + PyPI advisory feed against `poetry.lock` | every push + PR + daily cron |
| **Bandit** | Static analysis of Python source | every push + PR |
| **CodeQL** | GitHub-managed semantic analysis | every push + PR |
| **Dependabot** | Dependency PRs + advisory notifications | continuous |
| **License audit** | `pip-licenses` SPDX manifest in CI | every push + PR + per release |
| **SBOM** (v0.0.53-NEW) | CycloneDX (JSON + XML) attached to every GitHub Release | per tag |

The `make sec` target runs the same scanners locally so developers
get the same signal CI does.

### Supply chain

- **PyPI Trusted Publishing** (OIDC, no long-lived tokens) for all
  four packages in the suite.
- **Sigstore attestations** generated for every wheel + sdist
  uploaded via `pypa/gh-action-pypi-publish`.
- **Multi-arch Docker image** at `ghcr.io/sebastienrousseau/pain001`
  built with `docker/build-push-action` provenance attestations
  (SLSA Level 3-equivalent for the build step).
- **Signed git tags**: every release tag is signed with the
  maintainer's SSH key (verifiable with
  `git tag --verify v0.0.53`).
- **No `--no-verify` or `--allow-unverified` shortcuts** are used
  in any release workflow.

## Cryptography status

The library uses `cryptography` only as a transitive package
constraint. **pain001 does not implement payment signing,
encryption, certificate validation, or password hashing itself.**
Anyone signing or encrypting payment payloads should use a
dedicated library (`python-gnupg` for OpenPGP, `cryptography` for
X.509) outside pain001.

## Continuous integration

Every push to `main` and every PR runs the full quality gate:

- `make lint` — ruff + ruff format + pydoclint + interrogate
- `make type` — `mypy --strict`
- `make test` — `pytest --cov-fail-under=100`
- `make sec` — bandit + pip-audit
- Docker image build + multi-arch publish to GHCR (on tag pushes)

Release tags additionally fire:

- PyPI publish via OIDC trusted publishing
- SBOM generation + upload as Release assets (v0.0.53-NEW)
- Sigstore attestations for sdist + wheel

## Threat model — what this library is *not*

- **Not a HSM substitute.** Don't store unencrypted IBANs or
  account numbers on disk for longer than the validation pass.
- **Not a transport.** pain001 produces and validates files; it
  does not send them. Use your bank's EBICS/SFTP/API channel; the
  v0.0.56 roadmap's `pain001 upload --sftp` is the planned
  closest-to-built-in path.
- **Not a settlement engine.** XSD-valid does not mean the bank
  will accept the file (different settlement systems have different
  business rules; the `--scheme` rulebook flag covers the major
  SEPA ones).

## Contact

- **GitHub Private Vulnerability Reporting (preferred):**
  <https://github.com/sebastienrousseau/pain001/security/advisories/new>
- **Email:** `security@pain001.com`
- **GitHub Discussions (non-security questions):**
  <https://github.com/sebastienrousseau/pain001/discussions>
