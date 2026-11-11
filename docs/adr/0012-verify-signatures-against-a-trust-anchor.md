<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0012. Verify XML signatures against a trust anchor

- **Status:** Accepted
- **Date:** 2026-11-09
- **Deciders:** Sebastien Rousseau (release 0.0.83, decision D2)

## Context

`verify_xml_signature(signed_xml)` with no key or certificate verified
with the certificate inside the document's `KeyInfo`. Anyone can make a
key and a certificate, sign a payment file, and embed that certificate,
so the call proved the file was unchanged since signing but not who
signed it, while its name and return value (`True`) read as the
latter.

Verification also disagreed with other implementations. It read the
document through ElementTree and canonicalised with C14N 2.0
(`ElementTree.canonicalize`), while the signature declares exclusive
C14N 1.0. A signature signxml 5.2.0 made over a bundled sample, keeping
the document's default namespace, failed with a digest mismatch; so did
any signature whose Signature element is followed by whitespace, since
removing it dropped that text. It found the Signature by a substring
match on the tag.

The signer has its own form of the same problem: it rewrites the
document through ElementTree (a default namespace comes out as `ns0:`)
and digests that with C14N 2.0. Its output does verify with signxml,
because ElementTree only writes the namespaces it uses, but it is not
the document the caller passed in.

The README's stability policy makes a change to generated XML or to an
API's contract breaking, announced one release ahead.

## Options considered

1. Require a trust anchor in 0.0.83, as the implementation plan had it.
   Closes the gap at once, but breaks callers without the notice the
   policy promises.
2. Add the anchored API in 0.0.83, keep the old call working with a
   `DeprecationWarning`, and refuse it in 0.0.84.
3. Require the anchor only in the new API and leave the old call
   trusting the embedded certificate until it is removed.

For the signer: change its output in 0.0.83 as an exception to the
policy, change it in 0.0.84 after announcing it, or add an opt-in now.

## Decision

Option 2, and for the signer, announce in 0.0.83 and change in 0.0.84
(the maintainer's choices on 2026-11-09).

0.0.83 adds `verify_signature(signed_xml, trust_anchor=...,
trust_embedded_cert=...)`, which returns a `SignatureReport` and needs
one of the two: a trust anchor (the signer's certificate or public
key), or an explicit `trust_embedded_cert=True` that the report
records as `trust="embedded"`. `pain001 verify-signature` has the same
rule (`--cert` or `--trust-embedded-cert`). `verify_xml_signature` is a
wrapper over it; without a key it still trusts the embedded
certificate, with a `DeprecationWarning` naming 0.0.84.

Verification parses once with lxml (DTDs and entities refused, as in
`pain001 check`), finds exactly one `ds:Signature` by namespace, and
digests the parsed tree with exclusive C14N 1.0, honouring an
`InclusiveNamespaces` prefix list and keeping the text after the
Signature when the enveloped transform removes it. It accepts only
allow-listed methods: exclusive C14N; exactly one `URI=""` reference with the
enveloped transform, optionally then exclusive C14N; SHA-256, SHA-384
or SHA-512 digests; RSA-SHA256, RSA-PSS (RFC 9231 `sha256-rsa-MGF1`),
and ECDSA-SHA256 and ECDSA-SHA384 with the raw `r || s` value XML-DSig
1.1 requires.

The signer gains those algorithms, chosen by the key or by
`algorithm=` (`--xml-sign-alg`). Its output for an RSA key and the
default algorithm is byte-identical to 0.0.82 across every bundled
coverage document; 0.0.84 moves it to the parsed tree and exclusive
C14N, as the CHANGELOG's `### Announced` section says.

## Consequences

- The `sign` extra installs `lxml` with `cryptography`.
- `scripts/dsig_interop.py` runs in CI (the `XML-DSig interop` job):
  pain001 and signxml, and xmlsec1, sign and verify each other's
  signatures for every algorithm, so the canonical forms cannot drift
  apart again unnoticed. `tests/test_dsig_verify.py` builds signatures
  to the specification without pain001's signer, including the cases
  0.0.82 rejected.
- Certificate chains and validity dates are still not checked; the
  trust anchor is the certificate the caller already trusts.
- Placing the signature in the Business Application Header
  (`AppHdr/Sgntr`) moves to 0.0.84 with the signer change, since it is
  the same rewrite of the signer.
- 0.0.84: `verify_xml_signature` without a key raises; the signer keeps
  the caller's document and prefixes.

## Implementation in 0.0.84

The accepted second stage is implemented: the boolean wrapper requires
an explicit public key or certificate, and signing uses exclusive C14N
1.0 over the parsed document and SignedInfo. Input namespace prefixes are
preserved. A supported head.001.001.03 header carries the signature in
`AppHdr/Sgntr`; the container exists before the payload digest is taken.
An existing signature, ambiguous headers or an occupied container are
refused. Plain documents retain a root-level enveloped signature.

The standalone `canonicalize_xml` C14N 2.0 utility keeps its existing
contract and is no longer used by signing. Tests cover namespace
preservation, explicit trust, header placement, malformed input and all
supported signing algorithms. The interoperability script checks the
result against signxml and xmlsec1. The canonicalization and enveloped
transform rules follow the [W3C XML Signature specification](https://www.w3.org/TR/xmldsig-core1/).
