<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Architecture decision records

One file per decision that a future contributor is likely to question.
An ADR records the context at the time, the options that were on the
table, the choice, and what it costs. ADRs are never edited after
acceptance except to mark them superseded; a change of mind is a new
ADR that supersedes the old one.

| ADR | Title | Status |
| :--- | :--- | :--- |
| [0001](0001-monotonic-versioning-and-suite-lockstep.md) | Monotonic `0.0.x` versioning and suite lockstep | Accepted |
| [0002](0002-dual-licence-apache-2-or-mit.md) | Dual licence, Apache-2.0 OR MIT, declared with PEP 639 | Accepted |
| [0003](0003-example-corpus-two-corpora-one-engine.md) | Example corpus: two corpora, one engine, twelve scoped decisions | Accepted |
| [0004](0004-python-floor-policy.md) | Python floor policy | Accepted |

Template: copy [`template.md`](template.md), number it next, add a row
here, and open it in the pull request that implements the decision.
