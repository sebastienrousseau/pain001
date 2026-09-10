<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0002. Dual licence, Apache-2.0 OR MIT, declared with PEP 639

- **Status:** Accepted
- **Date:** 2026-08-20 (release 0.0.60, PR #202)
- **Deciders:** maintainer

## Context

The licence files, the website and the README all said "Apache-2.0 OR
MIT", but PyPI published `Apache-2.0`, `pyproject.toml` declared a
single licence, 167 source headers said Apache alone and 27 files had
no header at all. Poetry maps a compound `license = "..."` string to
`License :: Other/Proprietary License`, which is actively misleading on
an open-source project.

## Options considered

1. Collapse to a single licence. Simplest metadata, but it would take
   away the MIT option that downstream Rust and Python ecosystems in the
   same family rely on.
2. Keep the dual grant and declare it correctly everywhere, using PEP
   639's `license` expression and `license-files` so the wheel carries
   `License-Expression: Apache-2.0 OR MIT` and all three licence files.

## Decision

Option 2. Every Python file opens with the SPDX header
`Apache-2.0 OR MIT`; Markdown files carry it as a comment on line 1;
the wheel metadata comes from the PEP 639 fields in `[project]` while
Poetry stays authoritative for everything else through `dynamic`.

## Consequences

- The corrected metadata only reaches PyPI on release, so 0.0.59 and
  earlier still advertise Apache-2.0 alone.
- Contributions are dual-licensed by default (CONTRIBUTING.md and the
  DCO trailer make the assertion explicit).
- A REUSE-style header check is part of the family standard; the
  conformance test verifies the licence files exist, and the SPDX
  header is required on every new file.
