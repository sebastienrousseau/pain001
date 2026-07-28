<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Releasing Pain001

This document defines **what merits a release** and **how to cut one**, so
versions are deliberate rather than ad-hoc.

## Versioning scheme

Pain001 uses a **monotonic pre-1.0 version line**: the patch position of
`0.0.x` advances one step at a time (`0.0.51` → `0.0.52` → …). The line
rolls to `0.1.0` only after `0.0.999`, and `1.0.0` is deliberately a long
way off. The same step is used regardless of whether a release contains a
fix or a feature — the *number* does not signal the kind of change; the
`CHANGELOG.md` does. **The maintainer decides when to increment.**

## What merits a release

Cut a new version only when there is user-visible change to ship — bug
fixes, security/dependency patches, new features, new message types or
input formats, new public API, or documentation that ships in the package.

**Do not** cut a release that contains only a version-number bump with no
functional, security, or documentation change.

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

The checklist above is **executable** — do not eyeball it:

```bash
make release-check           # items 5, 6, 7 + tree/branch/tag/signing state
make release-check FULL=1    # additionally runs tests, build and pip-audit
```

Item 7 is the one that bites: the publish job enforces it too, but only
*after* a tag has been pushed, and a rejected tag then has to be deleted
locally and on the remote before you can retry.

## Cutting the release

1. Bump the version in the three files above and add the `CHANGELOG.md`
   section and `releases/vX.Y.Z.md` note in a single PR.
2. Merge the PR to `main` once CI is green.
3. Pre-flight, then tag:

   ```bash
   make release-check FULL=1
   python3 scripts/preflight_release.py --tag   # re-checks, then signs the tag
   git push origin vX.Y.Z
   ```

4. The tag triggers the `publish` job in `ci.yml`, which **fails fast** if
   the tag does not match the package version or the `releases/vX.Y.Z.md`
   note is missing, then builds, runs `twine check`, creates the GitHub
   release from the note, and publishes to PyPI via OIDC trusted publishing
   (no long-lived token).

## After releasing

- Confirm the version is live on
  [PyPI](https://pypi.org/project/pain001/) and the GitHub release is
  published (not draft).
- Verify a clean install: `pip install pain001==X.Y.Z`.
