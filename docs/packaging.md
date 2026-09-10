<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Packaging notes for distribution maintainers

This page is for people packaging `pain001` for a distribution, an
internal artifact repository, or a container base. Users install from
PyPI; see the README.

## Licence grant

Dual-licensed `Apache-2.0 OR MIT` at your option. The wheel carries the
PEP 639 expression `License-Expression: Apache-2.0 OR MIT` and all
three licence files (`LICENSE`, `LICENSE-APACHE`, `LICENSE-MIT`). Every
source file has an SPDX header. The bundled ISO 20022 XSD schemas under
`pain001/templates/` are published by ISO 20022 RA for implementation
use and are redistributed unchanged.

## Minimum toolchain

Python 3.10 or later; policy in
[ADR-0004](adr/0004-python-floor-policy.md). Pure Python, no compiled
extensions, no C dependencies. Optional extras pull in third-party
packages (`fastapi`/`uvicorn`, `pyarrow`, `redis`, `mcp`, `pygls`,
`python-gnupg`, the OpenTelemetry SDK, `lxml`); the core installs without
any of them.

## Dependency pin model

- `pyproject.toml` declares ranges; `poetry.lock` pins the development
  and test environment and is what CI installs.
- `requirements.txt` and `.github/requirements/*.txt` are hash-pinned
  (`pip install --require-hashes`) for the Docker image and CI jobs
  and are regenerated with `pip-compile`.
- The lock is audited on every push (`pip-audit`) and reviewed on
  dependency changes (GitHub dependency review).

## Building from source

```bash
git clone https://github.com/sebastienrousseau/pain001
cd pain001
git checkout v0.0.66            # a signed tag; see KEYS.asc
python -m pip install build
python -m build                 # produces dist/*.whl and dist/*.tar.gz
```

The sdist contains everything needed to run the tests offline once the
test dependencies are present:

```bash
python -m pip install "pain001[api,parquet,gpg,otel]" pytest pytest-cov hypothesis
python -m pytest -q --no-cov      # the coverage gate is a repo policy, not a package requirement
```

`tests/test_docker_smoke.py` needs a Docker daemon and skips otherwise;
`tests/test_suite_consistency.py` uses stubbed metadata and never
touches the network; `scripts/check_suite_consistency.py` does query
PyPI and is not part of the test run.

## Runtime data

The wheel bundles the templates, XSD schemas, JSON schemas and sample
data under `pain001/templates/` and `pain001/schemas/`. They are read
with package-relative paths, so the package works from any working
directory and from zipped installs is not supported (the XSD loader
needs real files).

## Signature and provenance verification

Release tags are SSH-signed with the key in [KEYS.asc](../KEYS.asc).
Release assets on GitHub carry SHA-256 sums, a CycloneDX SBOM and SLSA
provenance; the container image on GHCR carries a build attestation.
Commands are in [pkg/VERIFY.md](../pkg/VERIFY.md).

## What is not shipped

There are no deb, rpm, Homebrew, AUR or Nix packages maintained by the
project yet, and no pre-built single-file binaries: the CLI is a Python
entry point. The container image is the supported non-PyPI channel.
If you package `pain001` for a distribution, please open an issue so
the README can point at it.
