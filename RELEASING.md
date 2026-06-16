<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Releasing Pain001

This document defines **what merits a release** and **how to cut one**, so
versions are deliberate rather than ad-hoc.

## What merits a release

Cut a new version only when there is user-visible change to ship:

- **PATCH** (`0.0.X`) — bug fixes, security/dependency patches, internal
  refactors that change no public behaviour, or documentation that ships
  in the package.
- **MINOR** (`0.X.0`) — new features, new message types or input formats,
  new public API, or new CLI/REST surface (backward compatible).
- **MAJOR** (`X.0.0`) — any backward-incompatible change to the public API,
  CLI flags, REST contract, or the minimum Python version.

**Do not** cut a release that contains only a version-number bump with no
functional, security, or documentation change. (Pre-`0.1.0`, MINOR-type
changes are released as PATCH bumps; this is intentional during `0.0.x`.)

## Pre-flight checklist

A release is ready only when **all** of the following hold on `main`:

1. `make check` is green (lint + coverage + security).
2. Coverage is at or above the enforced floor (see `pyproject.toml`).
3. `mypy --strict`, `interrogate` (100%), and `pydoclint` are clean.
4. Every Dependabot / CodeQL / Snyk alert is resolved or has a documented,
   expiring suppression.
5. `CHANGELOG.md` has a dated section for the new version describing the
   change set (this is the single source of truth for the release).
6. The version is identical in `pyproject.toml`, `pain001/__init__.py`,
   and `pain001/constants.py` (enforced by the `version-sync` CI check).
7. A `releases/vX.Y.Z.md` note exists (used as the GitHub release body).

## Cutting the release

1. Bump the version in the three files above and add the `CHANGELOG.md`
   section and `releases/vX.Y.Z.md` note in a single PR.
2. Merge the PR to `main` once CI is green.
3. Push a signed tag:

   ```bash
   git tag -s vX.Y.Z -m "Pain001 vX.Y.Z" <merge-commit>
   git push origin vX.Y.Z
   ```

4. The tag triggers the `publish` job in `ci.yml`, which builds, runs
   `twine check`, creates the GitHub release from `releases/vX.Y.Z.md`,
   and publishes to PyPI via trusted publishing.

## After releasing

- Confirm the version is live on
  [PyPI](https://pypi.org/project/pain001/) and the GitHub release is
  published (not draft).
- Verify a clean install: `pip install pain001==X.Y.Z`.
