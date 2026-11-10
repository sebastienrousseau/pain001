<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Build your own bank profile

A bank's usage guideline adds rules to the ISO 20022 schema: a field
made mandatory, a code list narrowed, a limit on amounts or name
lengths. Pain001's open core checks the ISO schema, the message
definition's rules and public scheme rulebooks. Your bank's own rules
are layer three, and you can check them too, with a profile your team
builds and keeps in-house.

Everything below runs on your own machines. The guideline, the profile
and your payment files never leave your network, and Pain001 makes no
network connection while it checks them.

A profile is two files:

| File | Holds | Used by |
| :--- | :--- | :--- |
| `rules.yaml` | Record-level rules as CEL predicates: amounts, currencies, dates, field values | `--rules` on `check`, `validate` and `generate` (the `rules` extra) |
| `profile.sch` | Document-level rules as ISO Schematron assertions: which elements must be present, how long a name may be, which codes are allowed | `--schematron` on `check`, `validate` and `generate` |

A template for a fictional "Example Bank" is in
[`examples/bank-profile/`](https://github.com/sebastienrousseau/pain001/tree/main/examples/bank-profile),
and [`examples/29_private_bank_profile.py`](https://github.com/sebastienrousseau/pain001/blob/main/examples/29_private_bank_profile.py)
runs it.

## 1. Install

```sh
pip install "pain001[rules]"
```

## 2. List what the guideline changes

If your bank publishes its guideline as an XSD, the repository's author
tool lists every way it differs from the ISO edition it is based on:
removed elements, elements made mandatory, repeats capped, code lists
narrowed, lengths shortened, patterns changed. It reads the XSD from
wherever you keep it and writes nothing.

```sh
git clone https://github.com/sebastienrousseau/pain001
cd pain001
poetry install
poetry run python scripts/derive_overlay.py /path/to/guideline.xsd \
  --base pain.001.001.09
```

Add `--as-rules` to print the differences in rule syntax as a starting
point. Keep the guideline and this output inside your network if the
guideline's terms restrict them.

Most guidelines are PDF documents rather than XSDs. Then read the
guideline and list its rules by hand; the next two steps are the same.

## 3. Write the record-level rules

Each rule is a CEL predicate over a payment's fields (`payment_amount`,
`payment_currency`, `requested_execution_date`, `debtor_account_IBAN`
and the others in the [input-column reference](input-columns.md)). A
true predicate is a finding; only `error` severity fails a check.

```yaml
- id: EXB-LIMIT
  where: payment_amount > decimal("50000")
  severity: error
  message: "Example Bank accepts single payments up to 50,000 in one file."
```

Give every rule a stable id from your bank's guideline, so a finding
names the rule it broke. The helpers, limits and safety rules are in
[request-local payment policies](custom-rules.md).

## 4. Write the document-level rules

Rules about the XML itself go in an ISO Schematron file. Bind a prefix
to the pain.001 namespace; Pain001 rebinds it to the version of each
document it checks, within the same message family.

```xml
<schema xmlns="http://purl.oclc.org/dsdl/schematron" queryBinding="xslt2">
  <ns prefix="pain" uri="urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"/>
  <pattern id="EXB-PAYMENT">
    <rule context="//pain:PmtInf">
      <assert test="boolean(pain:PmtTpInf/pain:SvcLvl/pain:Cd)" id="EXB-SVCLVL">
        Example Bank requires a service level code on every payment block.
      </assert>
    </rule>
  </pattern>
</schema>
```

The bundled SEPA, FedNow and CBPR+ rulebooks in
[`pain001/schematron/rules/`](https://github.com/sebastienrousseau/pain001/tree/main/pain001/schematron/rules)
are worked examples of the same format.

## 5. Check files against the profile

Check files you already have:

```sh
pain001 check payments.xml \
  --rules rules.yaml --schematron profile.sch
```

It exits 0 when every file passes, 1 when one has an error finding and
2 when a file cannot be checked; `--format sarif` writes a report for
code scanning. To apply the profile while generating, pass the same
options to `validate` and `generate`:

```sh
pain001 generate -t pain.001.001.09 -d payments.csv -o out \
  --rules rules.yaml --schematron profile.sch
```

`validate` and `generate` read file paths only inside the working
directory, so run them from the directory that holds the profile (or
below it). From Python, `check_document(xml, policy=rules_text,
schematron="profile.sch")` returns the same findings.

## 6. Test the profile

Keep a few known-good files and one broken file per rule, and check
that each rule fires on its broken file and stays quiet on the good
ones. [`tests/test_bank_profile_template.py`](https://github.com/sebastienrousseau/pain001/blob/main/tests/test_bank_profile_template.py)
does this for the template. Always send a test file to your bank before
going live: a profile checks the rules you wrote down, not the bank's
own systems.

## 7. Package it (optional)

To share a profile across teams as a named scheme (`--scheme
example-bank`), wrap its rules in a `ValidationProfile` and publish it
as a `pain001.schemes` plugin; see [Adding a
profile](https://github.com/sebastienrousseau/pain001/blob/main/SCHEMES.md#adding-a-profile)
and the [plugin contract](plugins.md). The two files above need no
packaging.

## Contributing a profile

A profile built from public, non-confidential rules may be contributed
to the repository. Never contribute rules taken from a guideline whose
terms restrict it, and never include real account numbers or personal
data; see
[CONTRIBUTING.md](https://github.com/sebastienrousseau/pain001/blob/main/CONTRIBUTING.md#contributing-a-bank-profile).
