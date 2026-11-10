<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# DORA evidence map

The EU Digital Operational Resilience Act (Regulation (EU) 2022/2554)
asks a financial entity to manage the risk of the ICT services and
software it uses. This page maps the questions a reviewer typically asks
about a third-party component to the evidence Pain001 publishes.

**This is not a claim of compliance.** DORA obligations fall on the
financial entity, not on an open-source project. Pain001 has no
contract with you, offers no service, and is not certified against
DORA or any other standard. The map only shows where to find evidence
for your own assessment.

| What the reviewer asks | Evidence | Where |
| :--- | :--- | :--- |
| What does the component do, and what data does it touch? | Data-handling statement: runs on your infrastructure, no hosted service, no telemetry, network use only by explicit command or configuration | [Data handling](data-handling.md) |
| Is there a provider relationship or contract? | None. Free open-source software under Apache-2.0 or MIT; no paid tier, no SLA, no commercial partners | [Licence summary](licence-summary.md), [`SUPPORT.md`](https://github.com/sebastienrousseau/pain001/blob/main/SUPPORT.md) |
| Where is data processed and stored? | Only where you run it; Pain001 operates no servers | [Data handling](data-handling.md) |
| What does the component depend on? | CycloneDX SBOM and licence report for every release | `pain001-<version>.cdx.json`, `pain001-<version>.spdx-licenses.json` |
| Can we verify what we install? | Signed tags, SHA256SUMS, GitHub build attestations, SLSA Build Level 3 provenance, PyPI trusted publishing with attestations | [Verify a release](verify-a-release.md) |
| How are vulnerabilities reported and handled? | Private disclosure through GitHub, published advisories, acknowledgement goal of 5 working days (a goal, not a guarantee) | [`SECURITY.md`](https://github.com/sebastienrousseau/pain001/blob/main/SECURITY.md), [Maintenance policy](../maintenance-policy.md) |
| How is the software kept secure? | CI on every change: pip-audit, Bandit, CodeQL, secret scanning with push protection, Dependabot, OpenSSF Scorecard; 100% line and branch test coverage | [`SECURITY.md`](https://github.com/sebastienrousseau/pain001/blob/main/SECURITY.md), [`.github/workflows/`](https://github.com/sebastienrousseau/pain001/tree/main/.github/workflows) |
| What maintenance can we expect? | Fixes ship in the next release and arrive by upgrading; no long-term support line at present; no SLA | [Maintenance policy](../maintenance-policy.md) |
| What happens if the maintainer stops? | Permissive licence, public source and history, a documented release process in CI, a written continuity plan | [`GOVERNANCE.md`](https://github.com/sebastienrousseau/pain001/blob/main/GOVERNANCE.md), [`RELEASING.md`](https://github.com/sebastienrousseau/pain001/blob/main/RELEASING.md) |
| Can we exit or replace it? | Outputs are standard ISO 20022 XML validated against the official schemas; inputs are CSV, SQLite, JSON and Parquet; nothing is proprietary or hosted | [`README.md`](https://github.com/sebastienrousseau/pain001/blob/main/README.md) |
| Can we audit it? | The full source, tests, CI logs and design decisions (ADRs) are public | [Repository](https://github.com/sebastienrousseau/pain001), [`docs/adr/`](https://github.com/sebastienrousseau/pain001/tree/main/docs/adr) |
| Are there subcontractors? | No. Third-party code is listed in the SBOM; build and hosting run on GitHub Actions and PyPI | SBOM, [Verify a release](verify-a-release.md) |
| How is incident information shared? | Fixed vulnerabilities are published as GitHub Security Advisories, mirrored to OSV and the PyPI advisory database | [`SECURITY.md`](https://github.com/sebastienrousseau/pain001/blob/main/SECURITY.md) |
