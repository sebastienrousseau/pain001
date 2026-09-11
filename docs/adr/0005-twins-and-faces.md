<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0005. Twins preserve pain.001; faces express it for a compatible standard

- **Status:** Accepted
- **Date:** 2026-09-11
- **Deciders:** maintainer, on a research proposal and a plan reviewed
  decision by decision

## Context

Integrators meet pain.001 as XML, but their counterparties increasingly
speak JSON: the ISO 20022 Registration Authority approved a JSON Schema
generation recommendation in June 2025, Swift's APIs and several schemes
follow the RA's superseded 2018 whitepaper, UK Open Banking and the
Berlin Group publish JSON initiation shapes derived from pain.001, and
payment providers expose resource models of their own. The corpus
(ADR-0003) ships validated XML only, and the library's only JSON is the
flat input record. Research across these conventions is summarised in
the proposal the decisions below refer to.

## Options considered

1. One JSON convention chosen by convenience (the converter's native
   `@Ccy`/`$` shape). Cheapest, but nobody else's, so it helps no
   integration.
2. Every counterparty shape treated alike, as first-class formats.
   Broadest, but it blurs what is still pain.001 and what is a different
   resource model, and invites silent loss.
3. A layered model with a hard boundary: lossless *twins* of the
   pain.001 message, *faces* that project it for a compatible standard
   or rail with an explicit loss report, and *bridges* outside this
   layer for anything else.

## Decision

Option 3. The canonical twin follows the ISO RA 2025 recommendation
(XML tag names, `Document` root, amounts as `{"amt", "Ccy"}`, decimals
and booleans as strings, choices as single-property objects). The twin
is normalised to arrays for every repeatable element; that is this
project's rule for determinism, not the RA wire convention, and the
decoder accepts both forms. A face belongs in this layer only if it is
meaningfully a projection of a pain.001 payment instruction; every
source element is either mapped or listed in a loss report, targets come
only from openly licensed specifications, side inputs live in a private
bindings file that is never committed, and faces are outbound only until
a later decision defines reversibility. Provider APIs with a different
resource model (recipients by reference, one payment per call,
provider-side scheduling) are bridges, out of this layer. The scope is
pain.001; pain.008 is excluded until decided deliberately. The wheel
budget for shipped schemas and market twins is 500 KB, a guardrail, not
a target; everything else is generated on demand.

## Consequences

- `pain001.twins` ships the ISO JSON twin, one JSON Schema 2020-12 per
  pain.001 edition generated from the schema inventory by the RA rules,
  the records twin with its gap list, and the ISO 2018 compatibility
  face backed by a versioned name table derived from the ISO 20022
  e-Repository (release and read date recorded; the repository itself
  is not vendored).
- Every twin is round-trip tested on every corpus and coverage file and
  validated against its schema; `build_corpus.py --check` proves the
  shipped twins byte-stable.
- The compliance test extends to vendored specifications (licence file
  and read date required, restricted licences refused) and to bindings
  files.
- The Swift Payment Initiation face waits until its API Restricted
  License and portal terms are read; Stripe is a future bridge ADR.
- Phases: A1 (0.0.69) the twin foundation; A2 and B (0.0.70) surfaces
  and the face engine with UK Open Banking and Berlin Group; C (0.0.71)
  gated faces; D import, after its own ADR.
