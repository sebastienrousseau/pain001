# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""Verify an enveloped XML-DSig signature on the parsed document.

The document is parsed once, with lxml, and every digest is taken over
that tree with exclusive C14N 1.0, the algorithm the signature declares.
pain001 0.0.82 and earlier serialised the tree with ElementTree and
canonicalised it with C14N 2.0, so a valid signature from another signer
(signxml, xmlsec1, a bank) failed with a digest mismatch whenever the two
canonical forms differed.

The checks run in this order, and the first that fails is the report's
``reason``: exactly one ``ds:Signature`` (found by namespace and name,
not by substring); ``SignedInfo``, ``SignatureValue`` and the reference's
``DigestValue`` present; a key, from the trust anchor or, when the caller
allows it, the certificate in ``KeyInfo``; the declared algorithms on the
allow-lists; the payload digest; the signature over ``SignedInfo``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass
from typing import Any

import defusedxml.ElementTree as defused_et
from defusedxml import DefusedXmlException

from pain001.security._dsig_algorithms import (
    ALLOWED_SIGNATURE_METHODS,
    verify_bytes,
)

XMLDSIG_NS = "http://www.w3.org/2000/09/xmldsig#"
C14N_EXCLUSIVE = "http://www.w3.org/2001/10/xml-exc-c14n#"
TRANSFORM_ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
EXC_C14N_NS = "http://www.w3.org/2001/10/xml-exc-c14n#"

#: Digest methods a Reference may use, and the hash each one names.
ALLOWED_DIGEST_METHODS = {
    "http://www.w3.org/2001/04/xmlenc#sha256": "sha256",
    "http://www.w3.org/2001/04/xmldsig-more#sha384": "sha384",
    "http://www.w3.org/2001/04/xmlenc#sha512": "sha512",
}


def _ds(name: str) -> str:
    """``name`` in the XML-DSig namespace, as lxml spells a tag."""
    return f"{{{XMLDSIG_NS}}}{name}"


@dataclass(frozen=True)
class SignatureReport:
    """What verifying a signed document found.

    Attributes:
        valid: Whether the digest and the signature both verify.
        trust: ``"anchor"`` when the key came from the caller's trust
            anchor, ``"embedded"`` when it came from the document's own
            certificate (an integrity check only: anyone can sign a
            document with a certificate they made).
        algorithm: The signature algorithm's short name, when declared
            and allowed.
        signer: The subject of the certificate in ``KeyInfo``, if any.
        reason: Why the document did not verify; None when it did.
    """

    valid: bool
    trust: str
    algorithm: str | None = None
    signer: str | None = None
    reason: str | None = None


class _Invalid(Exception):
    """A check failed; the message is the report's reason."""


def _etree() -> Any:
    """``lxml.etree``, or an error naming the ``sign`` extra."""
    try:
        from lxml import etree  # noqa: PLC0415
    except ImportError as err:  # pragma: no cover - lxml ships in [sign]
        from pain001.security.dsig import XmlSignatureError  # noqa: PLC0415

        raise XmlSignatureError(
            "The 'lxml' package is required to verify XML signatures. "
            "Install it via `pip install pain001[sign]`."
        ) from err
    return etree


def _parse(raw: bytes) -> Any:
    """The document tree, refusing DTDs and entities like ``pain001 check``."""
    etree = _etree()
    try:
        defused_et.fromstring(raw)
    except DefusedXmlException as exc:
        raise _Invalid(
            f"refused: DTDs and entities are not allowed ({exc!r})"
        ) from exc
    except defused_et.ParseError as exc:
        raise _Invalid(f"not well-formed XML: {exc}") from exc
    parser = etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        huge_tree=False,
    )
    tree = etree.ElementTree(etree.fromstring(raw, parser))
    if tree.docinfo.doctype:
        raise _Invalid("refused: DTDs and entities are not allowed")
    return tree


def _one(parent: Any, path: str, missing: str) -> Any:
    """The element at ``path``; ``missing`` is the reason when absent."""
    found = parent.find(path)
    if found is None:
        raise _Invalid(missing)
    return found


def _text(parent: Any, path: str, missing: str) -> str:
    """The element's text without whitespace; ``missing`` when empty."""
    found = parent.find(path)
    if found is None or not (found.text or "").strip():
        raise _Invalid(missing)
    return "".join(found.text.split())


def _b64(value: str, what: str) -> bytes:
    """Strict base64 decoding; ``what`` names the element on failure."""
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise _Invalid(f"{what} is not valid base64") from exc


def _signature(tree: Any) -> Any:
    """The one ``ds:Signature`` in the document."""
    found = list(tree.getroot().iter(_ds("Signature")))
    if not found:
        raise _Invalid("No XML-DSig <Signature> element found in document.")
    if len(found) > 1:
        raise _Invalid(
            f"{len(found)} <Signature> elements: pain001 verifies a "
            "document with exactly one"
        )
    return found[0]


def _embedded_cert(sig: Any) -> Any | None:
    """The X.509 certificate in ``KeyInfo``, or None."""
    from cryptography import x509  # noqa: PLC0415

    path = f"{_ds('KeyInfo')}/{_ds('X509Data')}/{_ds('X509Certificate')}"
    element = sig.find(path)
    if element is None or not (element.text or "").strip():
        return None
    der = _b64("".join(element.text.split()), "<X509Certificate>")
    try:
        return x509.load_der_x509_certificate(der)
    except ValueError as exc:
        raise _Invalid(
            f"<X509Certificate> is not a certificate: {exc}"
        ) from exc


def load_trust_anchor(anchor: str | bytes) -> Any:
    """The public key in a PEM certificate or PEM public key.

    Args:
        anchor: The PEM text.

    Returns:
        The public key.

    Raises:
        ValueError: If the PEM is neither.
    """
    from cryptography import x509  # noqa: PLC0415
    from cryptography.hazmat.primitives import serialization  # noqa: PLC0415

    data = anchor.encode("utf-8") if isinstance(anchor, str) else anchor
    if b"BEGIN CERTIFICATE" in data:
        return x509.load_pem_x509_certificate(data).public_key()
    try:
        return serialization.load_pem_public_key(data)
    except ValueError as exc:
        raise ValueError(
            "the trust anchor is neither a PEM certificate nor a PEM "
            f"public key: {exc}"
        ) from exc


def _c14n(node: Any, method: Any) -> bytes:
    """Exclusive C14N 1.0, honouring an InclusiveNamespaces PrefixList."""
    etree = _etree()
    prefixes = None
    if method is not None:
        inclusive = method.find(f"{{{EXC_C14N_NS}}}InclusiveNamespaces")
        if inclusive is not None:
            prefixes = inclusive.get("PrefixList", "").split() or None
    return bytes(
        etree.tostring(
            node,
            method="c14n",
            exclusive=True,
            with_comments=False,
            inclusive_ns_prefixes=prefixes,
        )
    )


def _check_reference(signed_info: Any) -> tuple[Any, str]:
    """The Reference must cover the whole document, enveloped."""
    reference = _one(signed_info, _ds("Reference"), "Missing <Reference>.")
    if reference.get("URI") != "":
        raise _Invalid(
            'the Reference must sign the whole document (URI=""), '
            f"not {reference.get('URI')!r}"
        )
    transforms = reference.findall(f"{_ds('Transforms')}/{_ds('Transform')}")
    names = [t.get("Algorithm") for t in transforms]
    if names not in (
        [TRANSFORM_ENVELOPED],
        [TRANSFORM_ENVELOPED, C14N_EXCLUSIVE],
    ):
        raise _Invalid(
            "unsupported transforms: pain001 verifies the enveloped "
            f"transform, optionally then exclusive C14N, not {names}"
        )
    method = _one(reference, _ds("DigestMethod"), "Missing <DigestMethod>.")
    digest = ALLOWED_DIGEST_METHODS.get(method.get("Algorithm", ""))
    if digest is None:
        raise _Invalid(
            f"digest method {method.get('Algorithm')!r} is not allowed"
        )
    c14n = transforms[1] if len(transforms) == 2 else None
    return c14n, digest


def _check_methods(signed_info: Any) -> tuple[Any, Any]:
    """SignedInfo's canonicalisation and allow-listed signature method."""
    c14n = _one(
        signed_info,
        _ds("CanonicalizationMethod"),
        "Missing <CanonicalizationMethod>.",
    )
    if c14n.get("Algorithm") != C14N_EXCLUSIVE:
        raise _Invalid(
            "SignedInfo must use exclusive C14N, not "
            f"{c14n.get('Algorithm')!r}"
        )
    method = _one(
        signed_info, _ds("SignatureMethod"), "Missing <SignatureMethod>."
    )
    algorithm = ALLOWED_SIGNATURE_METHODS.get(method.get("Algorithm", ""))
    if algorithm is None:
        raise _Invalid(
            f"signature method {method.get('Algorithm')!r} is not allowed"
        )
    return c14n, algorithm


def _remove_enveloped(sig: Any) -> None:
    """Drop the Signature but keep the text after it, as the transform does."""
    parent, tail = sig.getparent(), sig.tail
    previous = sig.getprevious()
    parent.remove(sig)
    if tail:
        if previous is not None:
            previous.tail = (previous.tail or "") + tail
        else:
            parent.text = (parent.text or "") + tail


def _verify(tree: Any, key: Any | None, report: dict[str, Any]) -> None:
    """Run every check, filling ``report`` as facts are found."""
    from cryptography.exceptions import InvalidSignature  # noqa: PLC0415

    sig = _signature(tree)
    signed_info = _one(
        sig, _ds("SignedInfo"), "Missing <SignedInfo> element in signature."
    )
    value = _text(
        sig,
        _ds("SignatureValue"),
        "Missing or empty <SignatureValue> element.",
    )
    expected = _text(
        signed_info,
        f".//{_ds('DigestValue')}",
        "Missing or empty <DigestValue> in <SignedInfo>.",
    )
    cert = _embedded_cert(sig)
    if cert is not None:
        report["signer"] = cert.subject.rfc4514_string()
    if key is None and cert is not None and report["trust"] == "embedded":
        key = cert.public_key()
    if key is None:
        raise _Invalid(
            "No public key or certificate supplied and none found in <KeyInfo>."
        )
    c14n, algorithm = _check_methods(signed_info)
    report["algorithm"] = algorithm.name
    ref_c14n, digest_name = _check_reference(signed_info)
    canonical_signed_info = _c14n(signed_info, c14n)
    _remove_enveloped(sig)
    digest = hashlib.new(digest_name, _c14n(tree, ref_c14n)).digest()
    actual = base64.b64encode(digest).decode("ascii")
    if actual != expected:
        raise _Invalid(
            f"Digest mismatch: payload digest {actual} does not match "
            f"{expected}."
        )
    try:
        verify_bytes(
            key,
            algorithm,
            _b64(value, "<SignatureValue>"),
            canonical_signed_info,
        )
    except (InvalidSignature, ValueError, TypeError) as err:
        raise _Invalid(
            f"Cryptographic signature verification failed: {err or 'invalid'}"
        ) from err


def verify_signature(
    signed_xml: str | bytes,
    *,
    trust_anchor: str | bytes | None = None,
    trust_embedded_cert: bool = False,
) -> SignatureReport:
    """Verify an enveloped XML-DSig signature and report what was found.

    Args:
        signed_xml: The signed document.
        trust_anchor: The signer's PEM certificate or PEM public key, the
            key you already trust. The document's own certificate is
            then reported but not used.
        trust_embedded_cert: Without an anchor, verify with the
            certificate in ``KeyInfo``. That proves the document was not
            changed after signing, not who signed it.

    Returns:
        A ``SignatureReport``; ``valid`` is False with a ``reason`` for
        any document that does not verify.

    Raises:
        ValueError: If neither a trust anchor nor ``trust_embedded_cert``
            is given, or the anchor is not a PEM certificate or key.
    """
    if trust_anchor is None and not trust_embedded_cert:
        raise ValueError(
            "pass trust_anchor (the signer's certificate or public key), or "
            "trust_embedded_cert=True for an integrity-only check"
        )
    key = None if trust_anchor is None else load_trust_anchor(trust_anchor)
    report: dict[str, Any] = {
        "trust": "anchor" if key is not None else "embedded"
    }
    raw = (
        signed_xml.encode("utf-8")
        if isinstance(signed_xml, str)
        else signed_xml
    )
    try:
        _verify(_parse(raw), key, report)
    except _Invalid as exc:
        return SignatureReport(valid=False, reason=str(exc), **report)
    return SignatureReport(valid=True, **report)
