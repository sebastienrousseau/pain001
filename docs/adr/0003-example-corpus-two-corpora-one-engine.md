<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0003. Example corpus: two corpora, one engine, twelve scoped decisions

- **Status:** Accepted
- **Date:** 2026-09-10
- **Deciders:** maintainer, on a plan reviewed decision by decision

## Context

The project needs example files that exercise every element of every
bundled XSD, and bank-acceptable example files per payment rail for
sixteen countries. The two goals conflict: a file that uses every
element is by construction not a file any bank accepts, and a
bank-acceptable file uses a small, tightly constrained subset. The
bundled example XML covered 15–26 % of each schema and nothing
validated it; anything placed under `pain001/templates/` becomes a
message type at import time and ships in the wheel; three
required-column definitions disagreed.

Research across ISO 20022 releases, the EPC 2025 rulebooks, CGI-MP,
UK, US, ten European markets and five Asian and Gulf markets is
summarised in the implementation plan the decisions below refer to.

## Decisions

1. **Scope.** "HDD Statements" is read as bank statements and left to
   the `camt053` repository; "SW" covers both Switzerland and Sweden.
2. **Coverage** means every element declaration and every `xs:choice`
   branch of an XSD appears in at least one file of a documented
   coverage set, and every file in the set is XSD-valid and passes the
   MDR cross-element rules. One instance cannot hold every branch.
3. **Location.** The corpus is package data under `pain001/corpus/`,
   shipped in the wheel with a compressed-size budget, because every
   suite member imports from the installed package and none bundles
   its own data. Not under `pain001/templates/`.
4. **Versions.** The coverage corpus covers all thirteen XSDs (twelve
   bundled plus pain.008.001.08, which the SEPA 2025 rulebook needs and
   which becomes a bundled message type). The market corpus ships
   pain.001.001.03 and .09 only, plus pain.008.001.02 and .08 for
   debits, because no community uses .10 through .13 in production.
5. **Identifiers.** Real public routing codes, synthetic accounts,
   mod-97-valid IBANs, ISO 17442-valid LEIs with a reserved prefix,
   fictional party names. Bank names appear only as overlay
   identifiers that cite the public document they implement.
6. **Generation.** A dict-to-XML builder on `xmlschema` produces both
   corpora first; the CSV pipeline is extended afterwards for the
   twelve most-used rails, with the corpus as the golden target.
7. **Evidence.** Every market file carries a provenance record with an
   evidence state: `hsbc-validated` where HSBC's client validation was
   used, `portal-validated` for the public SIX and ValidateFin
   validators, `self-validated` otherwise. No other gated access exists.
8. **Tiers.** Tier 3 (Singapore, Malaysia, Qatar, UAE) ships with an
   explicit confidence chip rather than being deferred.
9. **Virtual accounts** are an overlay dimension on any rail, not a
   rail.
10. **Addresses** default to the hybrid form; structured and
    unstructured variants live in the coverage corpus only. The
    deadlines moved three times in the three weeks before this
    decision.
11. **Website.** A generated corpus page with downloads first; more
    XSDs in the browser demo later.
12. **Releases.** 0.0.67 engine and coverage corpus; 0.0.68 tier 1
    packs and ecosystem tools; 0.0.69 tiers 2–3 and the CSV pipeline.

## Consequences

- Bank-restricted usage guidelines used for evidence stay outside the
  repository; only the derived overlay rules, with citations, are
  committed.
- The corpus gains its own registry, tests, size gate and coverage
  gate; the stale bundled example XML is regenerated from it.
- Adding pain.008.001.08 is a coordinated suite release.
