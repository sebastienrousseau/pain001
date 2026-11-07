<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Faces: pain.001 projected for another standard, with its losses listed

A **face** projects a pain.001 document into the JSON shape of another
compatible standard and reports, element by element, what the projection
did not carry ([ADR-0005](adr/0005-twins-and-faces.md)). Where a
[twin](twins.md) is lossless, a face is a projection: it maps what the
target can hold, lists the rest, and never invents a value. When the
target requires an element the source lacks, the face refuses the
document and names the element.

Faces are outbound only. Nothing here reads a face back into pain.001.

## The faces

| Face | Target | Takes |
| :--- | :--- | :--- |
| `uk_open_banking` | UK Open Banking Read/Write API v4.0.1: the `OBWriteDomesticConsent4` body of `POST /domestic-payment-consents`, or `OBWriteDomestic2` for `POST /domestic-payments` when a `ConsentId` is bound | one payment information block with one transaction, an `InstrId`, an `InstdAmt`, an IBAN creditor account and a creditor name |
| `berlin_group` | Berlin Group NextGenPSD2 XS2A Framework v1.3.16: `paymentInitiation_json` for one transaction, `bulkPaymentInitiation_json` for several | one payment information block, an IBAN or BBAN debtor and creditor account, an `InstdAmt` and a creditor name per transaction |
| `iso_2018` | ISO 20022 message element names in snake_case | any bundled pain.001 edition |

```python
from pain001.corpus import get_file
from pain001.faces import project_face

xml = get_file("de.sepa.sct-salary", "pain.001.001.09")
result = project_face(xml, face="berlin_group")
result.payload["payments"]            # one element per transaction
result.loss_report.unmapped_paths     # what the target cannot carry
```

From the command line:

```bash
pain001 face payment.xml --face berlin_group --loss-report
pain001 face payment.xml --face uk_open_banking --bindings private/bindings.json -o body.json
```

## Over REST

`pain001 serve` exposes the same faces (install `pain001[api]`):

* `GET /api/v1/faces` lists each face, its target and the binding keys
  it accepts.
* `POST /api/v1/faces/{face}` takes the document as XML text in a JSON
  body, with an optional `version` and `bindings`, and returns the
  `face`, the source `version`, the `payload` and the `loss_report`.

```bash
jq -n --rawfile xml payment.xml '{xml: $xml}' |
  curl -s -X POST http://127.0.0.1:8000/api/v1/faces/berlin_group \
    -H 'Content-Type: application/json' -d @-
```

A face that refuses the document, or a binding it does not accept,
answers `422` with the face's reason; an unknown face answers `404`.
The routes honour `PAIN001_API_KEY` like every other route.

## From an agent or an editor

* [pain001-mcp](https://github.com/sebastienrousseau/pain001-mcp) has
  two tools: `list_faces`, and `project_face` with `xml_content`,
  `face`, and optional `version` and `bindings`. A refusal comes back
  as an `{"error": ...}` payload.
* [pain001-lsp](https://github.com/sebastienrousseau/pain001-lsp) has
  two `workspace/executeCommand` commands: `pain001.faces.list`, and
  `pain001.faces.project` with `{"xml", "face", "version"?,
  "bindings"?}`. The editor sends the open buffer's text as `xml`.

Every surface that takes a document from a client (REST, the MCP
server, the language server) calls `project_face_text`, never
`project_face`: it accepts XML text only, so a string naming a file on
the server is refused rather than read; it refuses entity declarations
and external references; and it caps the document at 10 MiB.

## Loss reports

The loss report lists source leaves by **indexed path**, relative to
`Document`: `CstmrCdtTrfInitn/PmtInf[0]/CdtTrfTxInf[1]/Amt/InstdAmt`.
Every occurrence of a repeated element is its own entry, so a payment a
face leaves out can never be reported as carried. An amount is one leaf
plus its `/@Ccy`. `mapped_paths` and `unmapped_paths` partition the
document's leaves; `loss_ratio` is the share not carried.

## What each payment face maps

Only properties the target's request schema defines are produced, and
only from the element that means the same thing:

* **UK Open Banking**: `PmtId/InstrId` and `EndToEndId`, `InstdAmt`, the
  debtor and creditor IBAN accounts (`UK.OBIE.IBAN`) with the party
  names, the creditor agent's BIC (`UK.OBIE.BICFI`), the creditor's postal
  address, the ultimate creditor and debtor names, unstructured
  remittance lines and structured creditor references. The local
  instrument, purpose, charge bearer and execution date have no
  counterpart that means the same thing, so they are reported, not
  translated.
* **Berlin Group**: `EndToEndId`, `InstdAmt`, the debtor and creditor
  accounts (IBAN, or a BBAN when `Othr` carries scheme code `BBAN`), the
  creditor agent's BIC and name, the creditor name and address (only
  with a country, which the target requires), and the first unstructured
  remittance line. A bulk adds `batchBookingPreferred` from `BtchBookg`,
  the category purpose and the requested execution date. The payment
  product (`sepa-credit-transfers`, …) belongs to the request path and is
  the caller's choice.

Both refuse documents with more than one payment information block.

## Bindings

Some target fields have no pain.001 source: the UK Open Banking
`ConsentId` and `Risk` object are agreed with the bank, not carried in
the message. A face takes these as **bindings**, a private JSON object
passed beside the document. Each face states the keys it accepts
(`list_supported_faces()`), and any other key is refused. Bindings hold
per-customer values: keep the file out of version control. The
repository's compliance test fails if a bindings file is tracked.

## The ISO 2018 face and its name table

The `iso_2018` face renames each tag to its ISO 20022 message element
name in snake_case (`GrpHdr` to `group_header`), keeps repeatable
elements as arrays, writes amounts as `{"amount", "currency"}` and omits
the `Document` root.

The names come from `pain001/faces/iso_names.json`, derived from the
ISO 20022 Registration Authority's Message Definition Reports (Part 2,
Payments Initiation), which state every element with its XML tag. The
table records the report files it was built from and the read date.
`scripts/build_iso_name_table.py` rebuilds it from a directory of those
reports held outside the repository, and fails if two reports give one
tag different names. The reports themselves are never committed.

Five tags have no name in the available reports and are listed in the
table as unresolved, with the reason: `BIC` and `BICOrBEI`, used only
by pain.001.001.03 (2009), and three elements new in pain.001.001.13.
They are left out of the payload and appear in the loss report rather
than receiving a guessed name. Content inside `SplmtryData/Envlp` is
schema-free and has no element name either.

## Proof against the targets

`make face-contracts` downloads each target specification at a pinned
revision, refuses it unless its SHA-256 matches, and validates the
face's payload for every pain.001 file in the corpus the face accepts
against the request-body schema: `OBWriteDomesticConsent4` and
`OBWriteDomestic2` for UK Open Banking, `paymentInitiation_json` and
`bulkPaymentInitiation_json` for the Berlin Group. CI runs it on every
pull request. The specifications are read, not vendored.

## Licences of the targets

* UK Open Banking specifications: Open Banking Limited, MIT Open
  Licence.
* Berlin Group NextGenPSD2: the OpenAPI file states Creative Commons
  Attribution 4.0; the repository's licence file is Creative Commons
  Attribution-NoDerivatives 4.0. Producing a body in the published shape
  is interoperability; the specification is not copied or adapted here.
* ISO 20022 Message Definition Reports: public Registration Authority
  material; only the derived tag-to-name table ships.
