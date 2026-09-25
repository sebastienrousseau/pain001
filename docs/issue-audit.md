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

## Acceptance and closure checklist

This is an implementation inventory, not a statement that all issues are
closed or released. All six issues were still open at the 2026-09-25 audit.
PR #297 contains core changes; companion commits cannot appear in its diff.

| Issue | Evidence | Remaining before closure |
| :--- | :--- | :--- |
| #179 | Protocols/discovery, dispatch and structured-error tests; plugin CLI; worked guide and separate Cookiecutter repository; ten-plugin discovery benchmark | Independent external contributor validation is not available. Do not lock a v1.0 contract or close the issue on the strength of maintainer-authored tests. |
| #180 | Companion workbook cleanup and installed-plugin CSV/XLSX XML equivalence tests; core ecosystem README now lists the loader and safety limitations | Merge the companion and core integration changes after green checks and explicit authorization; retain the documented numeric-cell interpretation rather than claiming every General-format text cell is rejected. |
| #184 | tests/test_custom_policy.py and tests/test_policy_interfaces.py cover CLI/REST composition and fail-closed policy handling | Merge core; document that currency_of_iban cannot infer account currency and is deliberately refused. This deviation is explicit, not an implemented helper. |
| #185 | tests/test_record_corrections.py and companion MCP tests cover suggestions and the hard financial-field refusal | Merge core and MCP companion; the contradictory IBAN-WHITESPACE request is not implemented because the issue also explicitly forbids financial-field patches. |
| #186 | CLI/unit tests and real localhost SFTP round-trip, retry and changed-host tests | Merge core; no real-bank certification is claimed. Unique staging names preserve atomic/no-clobber delivery instead of a shared fixed temporary name. |
| #187 | Published multi-architecture development image; exact-image ACCP/RJCT-NARR round-trip smoke evidence | Verify the latest published image after companion documentation pushes; no core merge can merge this separate repository. |

For the latest state, consult each PR's checks rather than interpreting a
historical test count as current verification. Issue closing comments must
name the actual implementation commits and acceptance evidence. The approved
solo-maintainer branch policy does not waive #179's external-author criterion.
