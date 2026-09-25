<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# ADR-0007: Built-in rules do not depend on registry dispatch

## Status

Proposed — implemented on feat/v0.0.71 for maintainer review.

## Context

The registry discovers built-in adapters, but built-in rules and GPG dispatch
also imported the registry. Once scheme validation used registered plugins,
the same scheme module both supplied built-in rules and consumed the registry.
Lazy imports avoided startup failures but retained structural cycles reported
by CodeQL. The GPG adapter also selected inner loaders from the global
singleton even when registered in an independent registry.

## Decision

Keep registration dependencies one-way. Built-ins accept a private structural
registry interface; GPG receives its owning registry. Pure rule definitions
live in `_scheme_rules.py`, which imports neither the registry nor dispatch.
Rails and built-in adapters depend on those rules. The existing `schemes.py`
surface re-exports the same objects and owns registry-backed validation.

Preserve public import paths, signatures, shared dictionaries, qualified class
names and pickle resolution. Do not change the external plugin protocols,
contract version, rule behavior or generated payment XML. Regression tests
enforce the dependency boundary and compatibility identities.

## Alternatives

- Dismissing all cycle findings would leave the ownership problem intact.
- Dynamic imports to evade the scanner would hide the same dependency cycle.
- Eager initialization would undermine optional dependencies and library startup.

## Consequences

There is one additional private rule module and a thin compatibility surface.
Class metadata explicitly retains the established public module name. Internal
callers must import rules from the private module, not through the public
dispatch facade; the architecture regression test enforces this distinction.
