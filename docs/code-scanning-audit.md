<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Code-scanning audit: feat/v0.0.71

The 2026-09-25 inventory contained 24 open alerts, all most recently reported
against `main` at `708bf0607d8c21104fcaafae7285defddc06f28e`. Alert numbers below
refer to the [code-scanning dashboard](https://github.com/sebastienrousseau/pain001/security/code-scanning),
not issues. Fixes stay on the feature branch; a valid finding on main is not
dismissed simply because a feature-branch fix exists.

## Branch fixes

| Alerts | Finding | Remediation |
| :--- | :--- | :--- |
| #189–#192 | Built-in/GPG/registry dependency cycle | A private structural registration interface removes imports of the concrete registry from built-ins. GPG receives its owning registry instead of importing the global singleton. Public plugin protocols and API version are unchanged. |
| #237, #238 | Mutable action references | Pin checkout and setup-python to the reviewed full commit hashes already used by the other workflows. |
| #239 | Unhashed spelling tool installation | Generate a hash-locked codespell requirements file from its source input. |
| #219, #222, #223, #224 | Local installs can resolve build dependencies despite no-deps | Hash-lock and preinstall build backends, build local wheels without isolation and with PIP_NO_INDEX=1, then install them with the hash-locked installer tool, which performs no dependency resolution. The fuzz job also installs hash-locked runtime dependencies. |
| #215 | Generated SDK installation resolves arbitrary dependencies | Hash-lock the generated client's runtime dependencies; build and install its reviewed local wheel without build isolation or dependency resolution, then run pip check. |

Regression tests in `tests/test_code_scanning_regressions.py` enforce the
workflow install policy and action references. GPG tests exercise distinct
registries for whole-file and streaming dispatch. CodeQL now also runs on
feature-branch pushes, using the existing query suite without exclusions.

The first fresh branch analysis also exposed a scheme-dispatch cycle
(#245–#251 and #192), a redundant test import (#252), a type-only import the
scanner did not recognize inside a quoted cast (#253), and unparenthesized
test-script concatenation (#254). The follow-up separates pure scheme rules
from dispatch, preserves public aliases and qualified class names, removes the
redundant import, makes the CEL function type explicit in an annotation, and
makes the intended string joining explicit. No findings are hidden with query
exclusions; see [ADR-0007](adr/0007-built-in-plugin-dependency-direction.md).

Generated dependency locks live beside their `.in` inputs in
`.github/requirements/`. Regenerate with Python 3.12 and
`pip-compile --allow-unsafe --generate-hashes --strip-extras --output-file=NAME.txt NAME.in`.
The base `requirements.txt` and `.github/requirements/api.txt` instead derive
directly from `pyproject.toml`, the API file using `--extra=api` and
`--constraint=requirements.txt`. This replaces the stale duplicate `api.in`
input and the base lock's former untracked temporary input. Runtime pins must
satisfy the package metadata; every wheel installation now runs `pip check`.
The allow-unsafe compiler option includes hashes for build tools such as
setuptools; it does not disable pip's installation-time hash verification.

## False-positive review

| Alerts | Evidence |
| :--- | :--- |
| #244 | `pain001.main` is a PEP 562 lazy export implemented by module `__getattr__`. A fresh-interpreter regression verifies every exported name resolves and CLI imports remain lazy. Eagerly importing main would regress browser and library startup. |
| #184–#188 | Ellipses are intentionally empty method bodies in PEP 544 Protocol definitions, not forgotten runtime operations. Existing structural compatibility tests cover positive and negative implementations. The published contract stays unchanged. |
| #193 | `_init_attempted` is read both before and inside the initialization lock. Existing tests prove cached initialization and explicit reset; removing it would break once-only initialization when tracing is disabled. |
| #183 | `pytest.raises(RuntimeError)` catches the deliberately raised exception. The subsequent assertion is reached and verifies plaintext cleanup after a failing inner loader. The targeted test passes. |

These eight findings were individually dismissed as false positives with the
evidence above on 2026-09-25. No directory or query was excluded.

## Findings that code on this branch cannot close

- **#205 and #221:** the SLSA reusable generator is deliberately referenced by
  `v2.1.0`. [Upstream requires an exact version tag](https://github.com/slsa-framework/slsa-github-generator/blob/main/internal/builders/generic/README.md#referencing-the-slsa-generator)
  for trusted builder verification and rejects hash references. Retaining this
  dependency is an explicit maintainer-accepted exception (approved on
  2026-09-25). Both alerts are dismissed as "won't fix", not false positives
  or an untested switch that breaks release provenance.
- **#194:** branch protection is repository state, not branch content.
  With explicit maintainer approval on 2026-09-25, main now requires one
  approving review and CODEOWNERS approval, with administrator enforcement.
  Read-back verified that existing status checks, conversation resolution,
  force-push prohibition and deletion prohibition were preserved. Another
  eligible CODEOWNER is needed for the sole maintainer's own PRs: authors
  cannot approve their own changes. This is not a claim of maximum Scorecard
  protection: stricter review freshness and up-to-date requirements remain
  separate policy choices. A fresh Scorecard run raised the score from 3 to 8,
  but still requests two approvals and misreports administrator enforcement;
  the authenticated protection API confirms enforcement is enabled. The alert
  remains open rather than accepting the remaining governance tradeoff.
- **#199:** historical changesets lack independent approving reviews. A new
  workflow, a self-review, or a bot dismissal cannot create that evidence.
  Future changes need genuine independent approval; historical review cannot
  be retroactively fabricated.

No versions, release tags, public API signatures, generated payment XML or
main-branch content are changed by this remediation.
