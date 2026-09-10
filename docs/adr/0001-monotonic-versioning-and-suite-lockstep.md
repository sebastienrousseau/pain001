<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0001. Monotonic `0.0.x` versioning and suite lockstep

- **Status:** Accepted
- **Date:** 2026-08-29 (practised since 0.0.51; written down 2026-09-10)
- **Deciders:** maintainer

## Context

`pain001` is one of five packages that ship together: the core, an MCP
server, a language server and two loader plugins. Users install the
members separately and combine them, and the failure they hit when the
numbers diverge is a version they cannot reason about: is
`pain001-loader-xlsx==0.0.54` meant to work with `pain001==0.0.60`? By
0.0.62 the five packages had drifted to four different numbers with no
breakage, which is exactly why it went unnoticed.

The project is pre-1.0 and its public surface (CLI flags, CSV column
contract, generated XML, plugin protocols) still moves.

## Options considered

1. **Independent SemVer per package** with compatibility ranges. Precise,
   but every member needs its own release judgement and the ranges are
   what users cannot reason about.
2. **One number across the suite, advancing one `0.0.x` step at a time.**
   Coarse, but a version pin on one package is a pin on all, and a
   release is one coordinated event.
3. **Jump to 1.0** and use minor/patch semantics. Premature while the
   output contract and plugin protocol are still being shaped; a 1.0
   promise that has to be broken is worse than none.

## Decision

Option 2. Every member ships the same `0.0.x` number; releases advance
by exactly one step; `0.1.0` follows `0.0.999`, never `0.0.60`. The
maintainer decides when the next number opens for work; contributors
never bump it. Inside the line, breaking changes are still called out
in the CHANGELOG and announced one release ahead (see the stability
section of the README).

## Consequences

- `pain001/suite.py` lists the members; `scripts/check_suite_consistency.py`
  queries PyPI daily and fails when any member lags the core or declares
  a floor the core has not published.
- `tests/test_suite_conformance.py`, a byte-identical file vendored in
  every repository, checks that the version is restated consistently and
  that the CHANGELOG's newest heading is the declared version.
- A change that adds a message type or alters the required-field set is
  a five-repository release. That cost is accepted because the
  alternative was users guessing.
- `scripts/preflight_release.py` additionally checks `CITATION.cff` and
  the `SECURITY.md` support table.
