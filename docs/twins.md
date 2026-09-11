# Twins: the same pain.001 message, losslessly, in JSON

A **twin** is a representation of a pain.001 document that carries
everything the XML carries and comes back as the same XML, element for
element. Two twins ship in 0.0.69 ([ADR-0005](adr/0005-twins-and-faces.md)):
the **ISO JSON twin**, in the ISO 20022 Registration Authority's JSON
convention, and the **records twin**, the library's own flat input rows
with the list of what they cannot carry. A **face**, which projects a
message for another compatible standard with a loss report, is a later
layer; nothing here is a face.

The scope is pain.001. pain.008 is refused by every entry point until it
is added deliberately.

## The ISO JSON twin

```python
from pain001.corpus import get_file, get_twin
from pain001.twins import to_iso_json, from_iso_json, validate_iso_json

xml = get_file("gb.chaps.property-purchase", "pain.001.001.09")
twin = to_iso_json(xml, "pain.001.001.09")       # {"Document": {...}}
assert validate_iso_json(twin, "pain.001.001.09") == []
assert get_twin("gb.chaps.property-purchase", "pain.001.001.09") == twin
back = from_iso_json(twin, "pain.001.001.09")   # the same document
```

The shape follows the RA's *Generation of JSON Schema Draft 2020-12 for
ISO 20022:2013* (v2.0, June 2025):

| XML | Twin |
| :--- | :--- |
| `<Document xmlns="…"><CstmrCdtTrfInitn>` | `{"Document": {"CstmrCdtTrfInitn": {…}}}`; the namespace is not represented, the edition names the schema |
| `<MsgId>M1</MsgId>` | `"MsgId": "M1"`: tag names unchanged, every value a string |
| `<InstdAmt Ccy="GBP">425000.00</InstdAmt>` | `"InstdAmt": {"amt": "425000.00", "Ccy": "GBP"}` |
| `<BtchBookg>false</BtchBookg>` | `"BtchBookg": "false"` |
| a repeated `<PmtInf>` | `"PmtInf": [ {…}, {…} ]` |
| a choice such as `ReqdExctnDt` | an object with exactly one property, `{"Dt": "2026-09-12"}` |
| an empty component the XSD allows | `{}`, kept so the twin stays lossless; the schema reports it |

**Always-array is this project's rule, not the RA's.** The RA accepts a
bare value for a single occurrence of a repeatable element; the twin
always renders an array so that every twin has one shape. The decoder
accepts both forms, in any key order, and `1`/`0` as well as
`true`/`false` for booleans. Decoding goes through the XSD: a twin that
names an element the edition does not declare, or breaks a facet, raises
`TwinError` rather than producing bad XML.

Namespace declarations repeated on leaves and `xsi` hints, which the
bundled templates write, carry no data and are dropped.

## The JSON Schema per edition

`pain001/schemas/iso-json/<edition>.schema.json` holds one JSON Schema
2020-12 per bundled pain.001 edition, generated from the schema
inventory by the RA's rules and committed byte-stable
(`scripts/generate_iso_json_schemas.py --check` runs with the corpus
gates). No tool generates this from an XSD; the inventory already carries
every facet the rules consume.

| XSD | Schema |
| :--- | :--- |
| a component | `type: object`, `additionalProperties: false`, `required` for children with `minOccurs ≥ 1`, else `minProperties: 1` |
| `xs:choice` | an object with `minProperties: 1` and `maxProperties: 1` |
| `maxOccurs > 1` | `anyOf` a single item and a bounded array (both the RA's forms validate) |
| an amount with `Ccy` | `{"amt", "Ccy"}`, both required |
| `xs:enumeration` | `enum` |
| text lengths | `minLength`, `maxLength` |
| `xs:pattern` | the pattern, anchored |
| `totalDigits`, `fractionDigits`, `minInclusive` | a string pattern that counts digits on both sides of the point and forbids the sign when the lower bound is zero |
| `xs:date`, `xs:dateTime` | the RA's patterns (`format` does not validate in 2020-12) |
| `xs:boolean` | `enum: ["true", "false", "1", "0"]` |
| `SplmtryData/Envlp` (`xs:any`) | an open object |

Definitions are keyed by ISO type name under `$defs`; the RA uses
`$anchor`, the content is the same. `$id` is
`urn:iso:std:iso:20022:tech:json:<edition>`.

`validate_iso_json` reports the deepest finding under a repeatable
element, so a bad amount inside the third transaction is reported at
its own path rather than as the whole array failing.

## The records twin

```python
from pain001.corpus import get_twin

records = get_twin("gb.chaps.property-purchase", "pain.001.001.09", "records")
records.rows              # one flat record per transaction of the first PmtInf
records.gap               # element paths present that no column carries
records.missing_required  # columns the preparer needs that the file lacks
```

The CSV pipeline renders a bundled template from flat records. Which
column lands on which element is not written anywhere, so
`column_paths(edition)` derives it once per edition by rendering the
template with a sentinel per column and reading the sentinels back. The
records twin is therefore true to the template the pipeline actually
uses, and its gap is measured, not assumed:

- `gap` lists every leaf path in the document that no column reaches,
  the elements that share one column and would collapse to one value
  (`PmtInfId` and `EndToEndId` both come from `payment_id`), and payment
  blocks beyond the first.
- `missing_required` lists the columns the edition's preparer refuses
  to render without, learned from the preparer itself, that the document
  gave no value for. With an empty list, generating from `rows` yields a
  document with the same value at every mapped path; the corpus tests
  prove it for every market file that qualifies.

What the twin measures today, and what the 0.0.69 CSV pipeline
extension takes as its input: every `.09` and `.13` file with IBANs on
both sides regenerates; the `.03` template needs address and reference
columns and writes account identifiers under `Othr/Id`; the UK and US
`.09` files carry sort codes and routing numbers, not IBANs; no template
renders `service_level_code` or `forwarding_agent_BIC`, and the `.09`
template renders neither `BtchBookg` nor `CtrlSum`.

## What ships, and where

- Every pain.001 market file has its twin beside it,
  `<stem>.iso.json`, byte-stable, inside the 500 KB compressed budget the
  schemas share; the sidecar's `twins:` block carries the twin's SHA-256
  and schema verdict and the records twin's row count, gap and missing
  columns.
- Coverage files are twinned on demand (`CorpusFile.twin()`) and tested
  the same way; they are not shipped twice.
- `make corpus-build` regenerates twins and schemas; `make corpus-coverage`
  checks them.
