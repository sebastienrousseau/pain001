<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Open-issue audit for feat/v0.0.71

Audit date: 2026-09-25. The six open issues were checked against core
source, tests, the published companion source and their issue discussions.
The implementation deliberately preserves the published version and the
pre-1.0 plugin contract. No issue is closed solely because code exists.

| Issue | Initial validation | Feature-branch implementation |
| :--- | :--- | :--- |
| [#179](https://github.com/sebastienrousseau/pain001/issues/179) | Discovery and protocols existed, but execution bypassed some plugins and failure logs lacked structured metadata. | Whole-file/streaming loaders, scheme overrides, validator batches and the XML writer now use registered plugins. Safe structured warnings and named disable instructions are tested. The separate Cookiecutter scaffold is implemented; independent external-author review still gates any v1.0 contract lock. |
| [#180](https://github.com/sebastienrousseau/pain001/issues/180) | The published XLSX plugin already handled numeric IBAN and temporal-cell refusal. | Fixed workbook cleanup in the companion and added installed-plugin CSV/XLSX byte-exact XML comparison. Its 105 tests pass with 100% line and branch coverage. No duplicate loader was added to core. |
| [#184](https://github.com/sebastienrousseau/pain001/issues/184) | CEL policy gates were missing from CLI and REST. | Bounded CEL policies implement request-local AbstractScheme composition across CLI, validation and synchronous/background generation. An IBAN cannot supply account currency; callers must use the explicit currency field. |
| [#185](https://github.com/sebastienrousseau/pain001/issues/185) | The tool was absent; IBAN whitespace edits conflicted with the explicit hard-refusal criterion. | Core and companion MCP expose deterministic, review-only suggestions. Financial fields are always refused; lengths come from schemas, ambiguous dates are refused, and missing values receive marked placeholders. |
| [#186](https://github.com/sebastienrousseau/pain001/issues/186) | Explicit SFTP delivery was absent. | Optional upload extra provides pre-authentication known-host/pin checks, exclusive staging, no-clobber rename, hash-based retry reuse and cleanup. Unit and real localhost SFTP tests cover byte-exact delivery and wrong-key refusal. |
| [#187](https://github.com/sebastienrousseau/pain001/issues/187) | The requested mockbank repository was absent. | Separate service and local container are implemented. Real SFTP tests produce matching ACCP or RJCT/NARR within one second. Local gates pass with 100% coverage. The maintainer explicitly approved recurring GHCR publication; the companion workflow now builds amd64 and arm64 images and publishes on main and feature-branch pushes after quality gates. |

The literal demand in #180 to reject every General-format cell is narrower
than its stated data-loss concern: text-valued IBANs retain their characters
even with General formatting. The companion's accepted ADR deliberately
rejects numeric IBAN cells. Preserve that decision rather than rejecting
uncorrupted text.

No issue is considered complete solely because a file or adapter exists.
Acceptance tests, coverage, documentation, and any external publication
criteria remain part of the assessment.

The maintainer explicitly included the named companions on 2026-09-25.
Existing companion changes use `feat/v0.0.71`; new repositories start at
unreleased `0.0.1` on `feat/v0.0.1`, following the portfolio's initial-version
rule. Existing local companion edits were preserved through isolated clones.
No release tags, public version bumps or merges into main are part of this work.

Companion implementation branches:

- [pain001-loader-xlsx](https://github.com/sebastienrousseau/pain001-loader-xlsx/tree/feat/v0.0.71)
- [pain001-mcp](https://github.com/sebastienrousseau/pain001-mcp/tree/feat/v0.0.71)
- [pain001-plugin-template](https://github.com/sebastienrousseau/pain001-plugin-template/tree/feat/v0.0.1)
- [pain001-mockbank](https://github.com/sebastienrousseau/pain001-mockbank/tree/feat/v0.0.1)

The authorized mockbank destination is
`ghcr.io/sebastienrousseau/pain001-mockbank`, using `edge` and
`sha-<full-commit-id>` development tags, not versioned releases.
