<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0004. Python floor policy

- **Status:** Accepted
- **Date:** 2026-09-10
- **Deciders:** maintainer

## Context

`pyproject.toml` declares `python = "^3.10"` and the CI matrix runs
3.10 through 3.14. The README stated the floor as a number without a
policy, and the family standard asks for the policy: when the floor may
rise, on which version axis, and where the reason is recorded. It also
warns against claiming distribution compatibility without a table.

## Options considered

1. **Track the newest Python only.** Simplest code, but excludes every
   long-term-support deployment and most bank estates.
2. **Follow upstream end-of-life.** Raise the floor one release after a
   Python version leaves upstream support, announced one release ahead.
3. **Freeze the floor at 3.10 indefinitely.** Predictable, but accrues
   compatibility shims forever.

## Decision

Option 2. The floor rises only when a Python version reaches upstream
end-of-life, in the first release opened after that date, with the
change announced under "Changed" in the CHANGELOG of the release before
it. On the `0.0.x` line this is still a single-step release, called out
as breaking. No claim is made about any distribution's system Python;
the documented install path is a virtual environment or the container
image.

## Consequences

- The CI matrix is the enforcement: the floor version must stay in
  `ci.yml` until it is dropped here first.
- Each rise gets its own ADR entry appended below, so the history is
  in one place.

| Floor | From release | Reason |
| :--- | :--- | :--- |
| 3.10 | until 0.0.74 | The oldest version in the CI matrix; 3.9 reached upstream end-of-life in October 2025. |
| 3.11 | 0.0.75 (current) | 3.10 reaches upstream end-of-life in October 2026, and current `hypothesis` releases require 3.11, so a lock that still admits 3.10 cannot take them. The maintainer dropped 3.10 in 0.0.75 across the suite without the one-release announcement this policy asks for; the 0.0.75 CHANGELOG records it as breaking for 3.10 users. |
