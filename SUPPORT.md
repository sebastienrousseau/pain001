<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Getting support

Thanks for using Pain001. Here's the fastest way to get help, by need.

## Read first

90% of questions are answered in one of:

- **[README.md](README.md)** — install, quick start, every CLI flag,
  REST endpoint reference, env-var matrix.
- **[docs/quickstart.md](docs/quickstart.md)** — 10-minute first-success
  tutorial (CSV → validated XML, no prior ISO 20022 knowledge).
- **[`examples/`](examples/)** — 14 runnable, self-checking scripts,
  one per feature. Every one is exercised in CI; they cannot rot.
- **[SCHEMES.md](SCHEMES.md)** — the full scheme-validation
  catalogue (`sepa-sct`, `sepa-sdd`, `sepa-inst`, `sepa-b2b`,
  `xborder-ct`) with every rule id and its remediation.
- **[OPERATIONS.md](OPERATIONS.md)** — production runbook for the
  REST API (config, scrape, alerts, scaling, incident playbook).
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — module map and extension
  points.

## Questions & how-to

Open a [GitHub Discussion](https://github.com/sebastienrousseau/pain001/discussions)
in the **Q&A** category. Include:

- Your Python version + OS
- `pain001` version (`python -c "import pain001; print(pain001.__version__)"`)
- A minimal reproducer (CLI invocation or short Python snippet)
- The full error output

Discussions are usually answered within a few business days.

## Bugs

Open a [bug report](https://github.com/sebastienrousseau/pain001/issues/new?template=bug_report.yml)
with:

- The same triage data as above
- A failing input file (any sensitive values redacted with `XXXX…`)
- The expected vs. actual behaviour

If your bug also affects v0.0.52 or earlier, please mention so —
backport eligibility depends on the supported-version window in
[SECURITY.md](SECURITY.md#supported-versions).

## Feature requests

Open a [feature request](https://github.com/sebastienrousseau/pain001/issues/new?template=feature_request.yml).
Especially welcome:

- **New scheme profiles** — see [SCHEMES.md](SCHEMES.md) for the
  `ValidationProfile` extension shape.
- **New input loaders** — the v0.0.54+ plugin contract
  ([`docs/plugins.md`](docs/plugins.md)) lets you ship one as an
  external package (canonical example:
  [`pain001-loader-xlsx`](https://github.com/sebastienrousseau/pain001-loader-xlsx)).
- **Additional message types** — open a discussion first to gauge
  demand, then a tracking issue.

Check the open milestones first to avoid duplication:
[v0.0.54 - Plugin substrate + table-stakes formats](https://github.com/sebastienrousseau/pain001/milestone/6),
[v0.0.55 - Validation depth](https://github.com/sebastienrousseau/pain001/milestone/7),
[v0.0.56 - End-to-end workflow](https://github.com/sebastienrousseau/pain001/milestone/8).

## Security

**Do not** open public issues for vulnerabilities. Follow the
private disclosure process in [SECURITY.md](SECURITY.md):

- **Preferred:** [GitHub Private Vulnerability Reporting](https://github.com/sebastienrousseau/pain001/security/advisories/new)
- **Email:** `security@pain001.com`

## Support tiers

Pain001 is open source under Apache-2.0 / MIT. There is **no paid
support tier today**.

- **Community support** (issues / discussions / PRs): best effort
  by the maintainers and other contributors. Most questions get a
  response within a few business days; bugs are triaged within a
  week.
- **Commercial support**: not available today. If your organisation
  needs an SLA, contact `support@pain001.com` so we can gauge
  demand. (No promises; this signal directly informs whether a paid
  tier is worth standing up.)

The single maintainer note: pain001 has one maintainer today. That
is the project's #1 risk and the headline item on the
[ROADMAP.md](ROADMAP.md). If you rely on the suite and can help
triage / review / co-maintain, see
[GOVERNANCE.md#becoming-a-maintainer](GOVERNANCE.md#becoming-a-maintainer).

## Contributing & maintaining

See [CONTRIBUTING.md](CONTRIBUTING.md) and
[GOVERNANCE.md](GOVERNANCE.md). The most valuable contributions are:

1. **Co-maintainership** (see above).
2. **External plugins** (loaders, validators, scheme profiles).
3. **Docs improvements** — especially feedback on
   [`docs/quickstart.md`](docs/quickstart.md) from new users.
4. **Bug reports with reproducers**.

## Companion packages

If you're using a sibling package, check its repo first:

- [`pain001-mcp`](https://github.com/sebastienrousseau/pain001-mcp)
  — MCP server for AI agents
- [`pain001-lsp`](https://github.com/sebastienrousseau/pain001-lsp)
  — Language Server for editor diagnostics
- [`pain001-loader-xlsx`](https://github.com/sebastienrousseau/pain001-loader-xlsx)
  — Excel (.xlsx) loader plugin

Issues that span multiple packages can be filed against
`pain001` (the core); the maintainer will route them.

## Supported versions

Fixes land on the latest release line; see
[SECURITY.md#supported-versions](SECURITY.md#supported-versions)
for the exact policy. Pain001 requires **Python 3.10+**.

| Version | Supported? |
| :--- | :--- |
| 0.0.53 (latest) | ✅ |
| 0.0.52 | ✅ best effort until v0.0.54 |
| ≤ 0.0.51 | ❌ upgrade |
