<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# AGENTS.md

Invariants for AI-assisted contributors working in this repository. A
human contributor reads [CONTRIBUTING.md](CONTRIBUTING.md) and
[DEVELOPMENT.md](DEVELOPMENT.md); an agent reads those too, plus this
list of things that must never drift, because they are the ones an
automated change is most likely to get wrong.

## Versioning

- The version is `0.0.x` and moves **one step at a time**. Never bump
  it as a side effect of a change; the maintainer decides when a
  release opens (`chore(release): open v0.0.N for work`).
- When it does move, every restatement moves together:
  `pyproject.toml`, `pain001/__init__.py`, `pain001/constants.py`,
  `CITATION.cff`, the `SECURITY.md` support table, and a new
  `## [0.0.N]` heading at the top of `CHANGELOG.md`.
  `scripts/preflight_release.py` and `tests/test_suite_conformance.py`
  check this.
- Every member of the suite (`pain001-mcp`, `pain001-lsp`,
  `pain001-loader-xlsx`, `pain001-loader-mt101`) ships the same version
  as the core. A change that adds a message type or alters the
  required-field set is a coordinated release across all of them.

## Commits and signing

- Conventional commits (`feat:`, `fix:`, `chore(scope):`, …), imperative
  subject, a body that explains why.
- Every commit carries a `Signed-off-by` trailer (DCO, enforced by
  `dco.yml`) and is SSH-signed. Merge commits are exempt from the DCO.
- Never rewrite published history. No `--force`, no `--amend` on pushed
  commits, no rebase of a shared branch.

## CI is the definition of done

- `make lint`, `make type`, `make test` and `make sec` must pass
  locally before a push; "it compiles" is not done.
- The coverage floor is **100 % line and branch** and it is not
  negotiable. Add tests with the change, in the same commit.
- Byte-exact golden files under `tests/golden/` are regenerated with
  `scripts/generate_golden_files.py`, never edited by hand, and a
  regenerated golden file is a **breaking change** unless the input
  changed too.

## Data and licences

- Every source file opens with the SPDX header
  `Apache-2.0 OR MIT`; Markdown files carry it as a comment on line 1.
- No real account numbers, no real personal data, no bank-restricted
  material in the repository. Usage guidelines obtained under a bank's
  MyStandards licence stay outside the tree.
- Sample IBANs must pass mod-97, BICs must be structurally valid, and
  currencies must be ISO 4217; the sample-data gate rejects anything
  else.

## Structure

- `docs/` is the only documentation root; root-level Markdown files
  are included into the manual, not copied.
- Anything placed under `pain001/templates/` becomes a message type at
  import time and ships in the wheel. Do not put fixtures there.
- `tests/test_suite_conformance.py` is a vendored, byte-identical copy
  shared across the family. Change it upstream, not here.
- Decisions that will be questioned later get an ADR in `docs/adr/`.

## When unsure

Prefer the smallest reversible change, state the assumption in the
commit body, and stop for a maintainer decision on anything that
touches the version, the public API, the generated XML, or the plugin
contract.
