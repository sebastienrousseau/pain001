<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# The example corpus

Two corpora, one engine ([ADR-0003](adr/0003-example-corpus-two-corpora-one-engine.md)):

- the **schema coverage corpus** proves what each bundled XSD can express:
  every element path and every choice branch of all thirteen editions appears
  in at least one file of that edition's set, every file is schema-valid and
  passes the ISO MDR cross-element rules;
- the **market corpus** is what a bank accepts: one scenario per country and
  rail, rendered into every edition it lists, validated on a four-rung ladder
  and shipped with a provenance record.

Both ship in the wheel under `pain001/corpus/data/` (230 KB compressed of a
400 KB budget) and are read through `pain001.corpus`:

```python
from pain001.corpus import list_files, get_file, provenance, coverage_report

for entry in list_files("market"):
    print(entry.scenario_id, entry.version, entry.country, entry.family)

xml = get_file("gb.chaps.property-purchase", "pain.001.001.09")
record = provenance("gb.chaps.property-purchase", "pain.001.001.09")
print(record["provenance"]["confidence"], record["validation"]["profiles"])
print(coverage_report("pain.001.001.13")["paths"]["percent"])  # 100.0
```

## How to read a scenario

A scenario is a YAML file under `scenarios/<country>/` that says what a
payment *is*; the builder decides how each edition spells it. The schema is
`pain001/corpus/schema/corpus.schema.json`; the loader reports the JSON
pointer of the first problem.

```yaml
id: gb.chaps.property-purchase         # country.rail.name
family: priority-payment               # the rail family overlays target
country: GB
versions: [pain.001.001.03, pain.001.001.09]
seed: 20260912                         # every auto identifier derives from it
profiles: [uk-chaps, purpose-mandate-gb, anti-duplicate]   # rung L2

parties:                               # named parties a ref can point at
  uk-corporate:
    name: Elm Road Developments Ltd
    address: {form: hybrid, street: Elm Road, building_number: "14",
              post_code: SW1A 1AA, town: London, country: GB}
    id: {org: {lei: auto}}             # auto: a checked synthetic LEI

header: {message_id: ELMRD-20260912-0001, created: "2026-09-12T08:30:00",
         initiating_party: {ref: uk-corporate}}
payment:
  type: {priority: HIGH, service_level: SDVA}
  requested_execution_date: "2026-09-12"
  debtor: {ref: uk-corporate}
  debtor_account: {iban: auto}         # a mod-97-valid GB IBAN
  debtor_agent: {bic: auto, clearing: {system: GBDSC, member_id: "040004"}}
  charge_bearer: SHAR
transactions:
  - end_to_end_id: COMPLETION-2026-0912
    uetr: auto
    amount: {ccy: GBP, value: "425000.00"}
    creditor: {ref: uk-solicitor}
    creditor_account: {iban: auto}
    purpose: HLST
    remittance: {unstructured: "Completion 14 Elm Road"}
provenance:
  sources: [{title: "Bank of England: ISO 20022 purpose codes for CHAPS", read: "2026-09-10"}]
  confidence: derived                  # verified | derived | assumed
  evidence: []                         # filled by the evidence workflow
```

Friendly keys cover the blocks every market file needs: header, rail choices,
parties with structured, hybrid or unstructured addresses and organisation or
private identification, accounts, agents, transactions, remittance
(unstructured and structured with creditor references), mandates for direct
debits. A `raw` object at any level carries ISO-named elements verbatim for
the long tail, and is fitted to the edition like everything else.

The builder fits one tree to each edition from the schema inventory:
`BIC`/`BICFI` and `BICOrBEI`/`AnyBIC` are renamed, scalars are wrapped into
the choices later editions introduced (`AdrTp`, `ReqdExctnDt`, `Frqcy`),
repeats are cut to the edition's cap, elements the edition lacks are dropped,
and every move is written into the provenance sidecar's `build` block.

Identifiers marked `auto` are synthetic but structurally valid: IBANs in the
country's BBAN shape with its national check digits, test-form BICs (`0` as
the eighth character), ISO 17442 LEIs under an unassigned prefix, v4-shaped
UETRs. Real public routing codes (sort codes, BLZ, ABA numbers) are fine to
use and the scenarios do; account parts are synthetic.

## The validation ladder

Every built file passes four rungs before it ships, and the result is written
into its `.provenance.yaml`:

| Rung | What | Where |
| :--- | :--- | :--- |
| L0 | the edition's XSD | `pain001.xml.validate_via_xsd` |
| L1 | the ISO MDR cross-element rules (20 for pain.001, 9 for pain.008) | `pain001.corpus.rules.mdr` |
| L2 | the scheme and rail profiles the scenario lists | `pain001.validation.schemes`, `pain001.validation.rails` via the row projection |
| L3 | the overlays that apply to the scenario or its family | `scenarios/overlays/`, `pain001.corpus.rules.overlays` |

`make corpus-coverage` re-runs L1 to L3 over the shipped files and the
coverage gate in CI; `make corpus-build` regenerates everything and
`scripts/build_corpus.py --check` proves a rebuild is byte-identical.

## How to add a country or rail

1. Write the scenario under `scenarios/<cc>/<rail>.<name>.yaml` from the
   public scheme rules; cite every document under `provenance.sources` with
   the date read.
2. List the rail profile under `profiles:`. If the rail has none yet, add a
   `Rail` to `pain001/validation/rails.py` with its sources; what the scheme
   document states is an error, what is typical bank practice is a warning.
3. Where a public bank guide adds rules, write an overlay under
   `scenarios/overlays/` with `applies_to: [<family or scenario id>]` and a
   `source` block. The grammar is the one `iso20022-bank-profile-mcp` uses,
   extended with `forbidden`, `one_of`, `max_length`, `matches` and `charset`.
4. `make corpus-build`, then `make corpus-coverage`. A file that cannot pass
   the ladder is not shipped; it becomes an open question in the scenario's
   provenance rather than a file with a caveat.

## Evidence policy

XSD validity is necessary, not sufficient. Each market file carries an
evidence state ([ADR-0003](adr/0003-example-corpus-two-corpora-one-engine.md),
decision 7):

- `hsbc-validated`: HSBC's client validation through MyStandards, the only
  gated access the project has; the HSBC usage guidelines themselves stay
  outside the repository;
- `portal-validated`: the public SIX portal (Swiss files) and ValidateFin
  (SEPA files);
- `self-validated`: this repository's ladder only, which every shipped file
  passes; the default for every other market.

`make corpus-evidence` prints, per scenario, the validator the plan expects
and what has been recorded. An external result is recorded into the scenario
file, the source of truth, and copied into the sidecars by the next build:

```bash
poetry run python scripts/corpus_evidence.py record de.sepa.sct-salary \
  --state portal-validated --tool ValidateFin --date 2026-09-12 --result pass
```

## Rulebook watch

The rulebooks moved three times in the three weeks before ADR-0003. Dates
that change what a scenario must carry, and the scenarios each affects:

| Due | Change | Scenarios affected |
| :--- | :--- | :--- |
| Oct 2026 (announced) | EPC sets a new unstructured-address end date | every `sepa-*` scenario's address form |
| 15 Nov 2026 | DK DFÜ-Abkommen Anlage 3 V26.11 (CCU gets its own order type) | `de-ccu`, `de-axz` rails |
| 14 Nov 2026 | SIX Swiss Payment Standards 2026 (v2.3) | `ch-domestic`, `ch-sepa` rails |
| Nov 2026 | Singapore structured town and country | `sg-fast` address rule moves from warning to error |
| Autumn 2026 | Bankgirot platform migration | `se-bankgiro` rail |
| Dec 2026 (announced) | Swift CBPR+ timetable revision | `cbpr-cross-border` rail |
| 30 Sep 2028 | LSV+/BDD end (Switzerland) | Swiss direct-debit scenarios (0.0.69) |

## What ships when

- **0.0.67**: the engine (inventory, builder, identifiers, overlay grammar,
  MDR rules, rail profiles, ladder), the coverage corpus for all thirteen
  editions, three market scenarios (GB CHAPS, DE SEPA SCT, NL SEPA SDD).
- **0.0.68**: tier-1 market packs (UK, SEPA core countries, US, CH, SE) and
  the website corpus page.
- **0.0.69**: tiers 2 and 3 (CZ, LU, HK, SG, MY, QA, AE) with confidence
  chips, and the CSV pipeline extension for the twelve most-used rails.
