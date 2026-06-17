<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Pain001 Governance

This document describes how Pain001 is run, how decisions are made, and how
to take on responsibility for it. It exists to make the project legible and
sustainable — and, candidly, to reduce its dependence on any single person.

## Mission and scope

Pain001 generates and validates ISO 20022 payment files (pain.001 / pain.008)
and parses the messages banks send back (pain.002 / camt.053), with a small,
well-tested core and first-class CLI, REST, MCP, and LSP surfaces. Changes
are weighed against that scope: correctness, security, and clarity over
feature breadth.

## Roles

| Role | Who | Can |
| :--- | :--- | :--- |
| **Maintainer** | Listed in [`MAINTAINERS.md`](MAINTAINERS.md) | Merge PRs, cut releases, triage, set direction |
| **Contributor** | Anyone with a merged PR | Propose changes, review, discuss |
| **User** | Everyone | File issues, ask questions, request features |

Maintainers are also listed as code owners in
[`.github/CODEOWNERS`](.github/CODEOWNERS) for review routing.

## Decision making

- **Day-to-day changes** (fixes, docs, tests, additive features within scope)
  proceed by **lazy consensus**: open a PR; if no maintainer objects and CI is
  green, a maintainer merges it.
- **Significant changes** (new public APIs, breaking changes, new
  dependencies, new message types or scheme profiles) need explicit approval
  from a maintainer in the PR, and should start as an issue or discussion.
- **Disagreement** is resolved by discussion aiming for consensus; if none is
  reached, the lead maintainer decides and records the rationale in the issue.

Every change must pass the full quality gate (tests at the coverage floor,
`mypy --strict`, ruff, interrogate, pydoclint, bandit, and the security
scanners) before merge — this is enforced in CI, not by trust.

## Releases

Releases follow [`RELEASING.md`](RELEASING.md). The project uses a
monotonic pre-1.0 version line (`0.0.x`, advancing to `0.1.0` only after
`0.0.999`); the lead maintainer decides when to increment. Only maintainers
publish to PyPI. The release authority (PyPI/Trusted Publisher and
tag-signing keys) currently rests with the lead maintainer; expanding it to
a second maintainer is a standing goal (see below).

## Becoming a maintainer

We actively want more maintainers — it is the single biggest thing that would
de-risk the project.

1. Contribute a few reviewed PRs in an area ([`ARCHITECTURE.md`](ARCHITECTURE.md)
   is the map; good first areas: a new scheme profile, an input loader, docs).
2. Help triage issues and review others' PRs.
3. Open a discussion (or email the lead maintainer) expressing interest.

A maintainer proposes you; with no objection from existing maintainers within
a week, you are added to `MAINTAINERS.md` and `CODEOWNERS` for your area.

## Sustainability (bus factor)

Pain001 today has **one** maintainer, which is a real risk for a library used
in payments. The mitigations in place:

- **The work is legible:** [`ARCHITECTURE.md`](ARCHITECTURE.md) maps the
  codebase, [`RELEASING.md`](RELEASING.md) documents the release process, and
  every public surface ships a runnable example.
- **Quality is enforced by CI,** not by one person's memory.
- **The goal is ≥ 2 maintainers** with independent release authority. If you
  rely on Pain001 and can help, please reach out — see the previous section.

## Code of conduct & security

Participation is governed by [`CODE-OF-CONDUCT.md`](CODE-OF-CONDUCT.md).
Security issues follow the private disclosure process in
[`SECURITY.md`](SECURITY.md) — please do not open public issues for
vulnerabilities.
