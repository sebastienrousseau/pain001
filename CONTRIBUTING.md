<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Contributing to Pain001

Read [DEVELOPMENT.md](DEVELOPMENT.md) for setup and the gate map, and
[AGENTS.md](AGENTS.md) for invariants. Contributions are dual-licensed
Apache-2.0 OR MIT. Discuss new public contracts, message types, dependencies
and breaking changes with the maintainer before implementation.

## Development setup

Python 3.10 is the supported floor; CI tests 3.10–3.14. Development uses 3.12.
Use Poetry and the committed lockfile:

```bash
poetry install --all-extras --with dev,docs
poetry run make check
poetry run make type
```

Work on the maintainer's `feat/v<next-version>` branch. Do not bump versions,
tag releases or rewrite shared history as a side effect of a change.

## Quality gates: the PySentinel zero-trust model

No commit without a successful `poetry run make check`. Before pushing, run
all required gates; failures must be fixed, not hidden:

```bash
poetry run make check
poetry run make type
poetry run make lint
poetry run make sec
```

`make check` runs lint, coverage, security and corpus checks. It does not run
`make type`, so run that separately. `make test` runs the full suite with the
**100% line and branch coverage floor**. Financial-data transformations need
exercised success and failure paths. Coverage is necessary evidence, not proof
of correctness.

Lint uses Ruff (formatting and import ordering), interrogate and pydoclint.
Types use mypy; security uses Bandit and pip-audit. Black and isort are not the
active gates. Type code explicitly; justify unavoidable `Any` and narrowly
scoped suppressions. Never suppress a failure merely to pass CI.

Also run relevant tollgates (`make tollgates`), mutation tests
(`make mutate-fast`), benchmarks (`make perf`) and documentation checks.
CI executes the Python matrix, examples, container and SDK checks. Local
SFTP tests need permission to bind localhost sockets, not a bank connection.

## Tests and generated artefacts

- Add tests in the same commit as behavior changes, including error paths.
- Exercise affected inputs and all affected bundled message types. Use
  `pain001 versions` rather than a copied list of versions.
- Use synthetic payment data only. IBANs must pass mod-97, BICs must be
  structurally valid, and currency codes must be ISO 4217.
- Add type annotations and document public parameters, results and errors.
- Never hand-edit golden files. Regenerate with
  `scripts/generate_golden_files.py`; changed XML bytes for unchanged input
  are a breaking change requiring a maintainer decision.
- Regenerate bundled examples and database mirrors with `make xml-examples`
  when their source changes. Keep generated schemas, SDKs and lockfiles tied
  to their generators, not manual edits.
- Do not modify the vendored `tests/test_suite_conformance.py` locally.

## Documentation

Update the relevant guide and the Unreleased CHANGELOG entry with each change.
`docs/` is the documentation root; root guides are included, not copied.
README is generated: edit `docs/readme-values.json`, then run
`poetry run python scripts/render_readme.py`. Do not hand-edit its output or
change the vendored canonical layout. Record durable decisions in `docs/adr/`.

Use live CLI help, generated OpenAPI and schema-derived field references
instead of duplicate option tables. Verify runnable examples; never advertise
unmeasured performance, bank certification or released availability for
branch-only work.

## Developer Certificate of Origin and signing

Every non-merge commit needs a `Signed-off-by` trailer: this is the
[DCO](DCO.txt), a legal assertion of your right to contribute, not a formality.
Use your real configured author identity and SSH-sign the commit:

```bash
git commit -S -s -m "docs: Clarify contributor checks" \
  -m "Explain the required gates so contributors can reproduce CI."
```

Use imperative conventional subjects of at most 50 characters and a body
explaining what and why, wrapped at 72 columns. Reference relevant issues.
AI-assisted commits identify the assistant in an `Assisted-by` trailer.

Never force-push, amend published commits or rebase shared branches. If a
published commit lacks its DCO trailer, stop for a maintainer-approved repair;
do not rewrite it or disable the gate. Merge commits are exempt from DCO.

## Pull requests and merge policy

Describe changes, actual test results, compatibility and remaining acceptance
criteria. Link companion PRs separately: core PRs cannot contain another
repository's changes. Do not claim completion just because code exists or use
closing keywords for unmet work.

The approved solo-maintainer workflow still requires PRs, status checks,
resolved conversations and administrator enforcement. It requires zero
approving reviews and no CODEOWNER approval; that is not independent review.
See [GOVERNANCE.md](GOVERNANCE.md). Agents need explicit authorization naming
the specific PR before merging into main. Never bypass checks or merge when
a required check is pending or failing.

## Troubleshooting and help

- Inspect `poetry env info` for interpreter mismatches; synchronize from the
  committed lock before diagnosing CI-only failures.
- Use `poetry run make format` for formatting, then rerun the gates.
- Inspect failing XML against its bundled XSD. The data keyword for
  `process_files` is `data_file_path`; see [usage](docs/usage.rst).
- Use [SUPPORT.md](SUPPORT.md) for help and [SECURITY.md](SECURITY.md) for
  private vulnerability reporting. Never post real payment records or secrets.
