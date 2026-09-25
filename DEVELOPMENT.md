<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Development

The single entry point for working on `pain001`: toolchain, how to
reproduce every CI gate locally, where tests live, and how a release
happens. [CONTRIBUTING.md](https://github.com/sebastienrousseau/pain001/blob/main/CONTRIBUTING.md) covers the etiquette (DCO,
commit format, review); this file covers the mechanics.

## Toolchain

| Tool | Version | Where it is pinned |
| :--- | :--- | :--- |
| Python | 3.12 for development; 3.10 is the floor | `.mise.toml` (dev), `pyproject.toml` `python = "^3.10"` (floor), CI matrix 3.10–3.14 |
| Poetry | 2.x | `poetry.lock` is committed; CI installs with the lock |
| Node | any current LTS | only for `markdownlint-cli2` in the docs-lint job |
| Docker | any | only for the image smoke test |

```bash
git clone https://github.com/sebastienrousseau/pain001
cd pain001
mise install                 # picks up Python from .mise.toml (optional)
poetry install --all-extras --with dev,docs
poetry run pre-commit install   # optional: runs ruff, codespell, hygiene hooks on commit
```

A [devcontainer](https://github.com/sebastienrousseau/pain001/blob/main/.devcontainer/devcontainer.json) does the same in a
Codespace or VS Code container and boots to a working `make`.

## Reproducing every CI gate

Each workflow maps onto a `make` target so a red CI job can be
reproduced without reading YAML.

| Gate | Local command | CI workflow |
| :--- | :--- | :--- |
| Lint (ruff, ruff format, interrogate 100 %, pydoclint) | `make lint` | `quality.yml`, `pr.yml` |
| Types (mypy `--strict`) | `make type` | `quality.yml` |
| Tests with the 100 % line + branch coverage floor | `make test` | `ci.yml` (matrix) |
| Security (bandit, pip-audit) | `make sec` | `security.yml` |
| Docs lint (codespell, markdownlint) | `uvx codespell` · `npx markdownlint-cli2 "**/*.md"` | `docs-lint.yml` |
| Docs build | `make docs` | `docs.yml` |
| Tollgates (dependency, XSD, idempotency, env parity) | `make tollgates` | `ci.yml` |
| Benchmarks (kept compiling, not asserted) | `make perf` | `nightly.yml` |
| Fuzzing (Atheris harness in `fuzz/`) | `python fuzz/fuzz_validation.py -max_total_time=60` | `nightly.yml` |
| Suite conformance (this repo against the family rules) | `poetry run pytest tests/test_suite_conformance.py` | `ci.yml` |
| Suite consistency (published versions across the family) | `python3 scripts/check_suite_consistency.py` | `suite-consistency.yml` (daily) |
| Combined local gate (types separately) | `make check` and `make type` | — |

The coverage floor is 100 % and deliberately so: the rationale is in
[CONTRIBUTING.md](https://github.com/sebastienrousseau/pain001/blob/main/CONTRIBUTING.md#quality-gates-the-pysentinel-zero-trust-model).
`# pragma: no cover` is reserved for entry-point guards and defensive
barriers that cannot be reached by a test.

## Test layout

```
tests/
  test_<module>.py            unit tests, one file per module or concern
  test_golden_files.py        byte-exact rendering of the first two rows of every template.csv
  golden/                     the golden XML, regenerate with scripts/generate_golden_files.py
  test_suite_conformance.py   the family-wide rules; a vendored, byte-identical copy — do not edit here
  test_suite_consistency.py   the PyPI version-lockstep checker, tested with stubbed metadata
  test_docker_smoke.py        builds the image and runs the CLI inside it (skipped without Docker)
  data/                       small fixtures (CSV, JSON)
examples/                     numbered, self-checking scripts; every one runs in CI
benches/                      pytest-benchmark suites
fuzz/                         Atheris harness for the raw-input validators
```

Conventions that bite: sample CSVs under `pain001/templates/` and
`examples/data/` are linted for IBAN, BIC and currency validity; any
column ending in `IBAN` or `BIC` is checked by suffix. Changing a
template, a preparer or a sample CSV requires regenerating the golden
files (`scripts/generate_golden_files.py`) and the bundled examples and
SQLite mirrors (`make xml-examples`); `tests/test_bundled_examples.py`
fails until you do.

## Documentation

Sphinx with MyST under `docs/`; `make docs` builds to
`docs/_build/html`. Root Markdown files (`ARCHITECTURE.md`, this file,
`SCHEMES.md`, …) are included into the rendered manual by thin chapter
files under `docs/`, so they are edited in one place. Architecture
decisions live in [`docs/adr/`](https://github.com/sebastienrousseau/pain001/blob/main/docs/adr/README.md).

README is generated from the canonical `docs/readme-template.md` and reviewed
`docs/readme-values.json`. Run `poetry run python scripts/render_readme.py`
after editing its values; CI checks the output, headings, local links and
executes its Quick Start. Run documentation lint and a warnings-as-errors
Sphinx build before claiming documentation is ready.

## Versioning and release

- One version number, restated in `pyproject.toml`, `pain001/__init__.py`,
  `pain001/constants.py`, `CITATION.cff` and the `SECURITY.md` support
  table; `scripts/preflight_release.py` refuses to proceed when they
  disagree.
- The line is `0.0.x` and every release is one step up; every member of
  the suite ships the same number ([ADR-0001](https://github.com/sebastienrousseau/pain001/blob/main/docs/adr/0001-monotonic-versioning-and-suite-lockstep.md)).
- Releases are cut by tag; the tag is SSH-signed; `ci.yml` builds,
  attests and publishes to PyPI with trusted publishing.
  [RELEASING.md](https://github.com/sebastienrousseau/pain001/blob/main/RELEASING.md) is the checklist, `make release-check`
  its executable form.
- Commits need a `Signed-off-by` trailer (DCO) and are expected to be
  signed; see [KEYS.asc](https://github.com/sebastienrousseau/pain001/blob/main/KEYS.asc) for the maintainer key.
