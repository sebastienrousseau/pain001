# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Signature verification reasons, word for word, and edge documents.

``SignatureReport.reason`` is what an operator reads when a bank's
document does not verify, so each reason is pinned exactly. The edge
documents cover what a specification-following signer may produce:
wrapped base64, comments, a bare ``InclusiveNamespaces`` and a
Signature that is the root's first child with no text before it.
"""

from __future__ import annotations

import base64
import datetime
import sys
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID
from lxml import etree

from pain001.security import _dsig_verify
from pain001.security.dsig import (
    XmlSignatureError,
    sign_xml_document,
    verify_signature,
)
from tests.test_dsig_verify import (
    _RSA,
    DOC,
    DS,
    EXC,
    _pem,
    _private_pem,
    _resigned,
    _sign,
)


def _reason(signed: bytes | str, **trust: Any) -> str:
    """The reason a document fails, verified against the RSA test key."""
    trust = trust or {"trust_anchor": _pem(_RSA)}
    report = verify_signature(signed, **trust)
    assert report.valid is False and report.reason is not None
    return report.reason


def _cert(common_name: str) -> bytes:
    """A self-signed PEM certificate for the RSA test key."""
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.UTC)
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(_RSA.public_key())
        .serial_number(11)
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(_RSA, hashes.SHA256())
        .public_bytes(serialization.Encoding.PEM)
    )


def _without(element: str) -> bytes:
    """A signed document with the first ``ds:<element>`` removed."""
    tree = etree.fromstring(_sign())
    found = tree.find(f".//{{{DS}}}{element}")
    found.getparent().remove(found)
    return bytes(etree.tostring(tree))


def test_lxml_missing_names_the_sign_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without lxml the error says which extra to install."""
    monkeypatch.setitem(sys.modules, "lxml", None)
    with pytest.raises(XmlSignatureError) as error:
        _dsig_verify._etree()
    assert str(error.value) == (
        "The 'lxml' package is required to verify XML signatures. "
        "Install it via `pip install pain001[sign]`."
    )


def test_an_external_dtd_is_never_loaded(tmp_path: Any) -> None:
    """A DOCTYPE naming a local file is refused without reading the file."""
    junk = tmp_path / "junk.dtd"
    junk.write_text("this is not a DTD", encoding="utf-8")
    document = f'<!DOCTYPE a SYSTEM "{junk}"><a/>'.encode()
    assert _reason(document) == "refused: DTDs and entities are not allowed"


@pytest.mark.parametrize(
    ("element", "reason"),
    [
        ("SignedInfo", "Missing <SignedInfo> element in signature."),
        ("SignatureValue", "Missing or empty <SignatureValue> element."),
        ("DigestValue", "Missing or empty <DigestValue> in <Reference>."),
        ("Reference", "Missing <Reference>."),
        ("DigestMethod", "Missing <DigestMethod>."),
        ("CanonicalizationMethod", "Missing <CanonicalizationMethod>."),
        ("SignatureMethod", "Missing <SignatureMethod>."),
    ],
)
def test_missing_parts_are_named_exactly(element: str, reason: str) -> None:
    """Each absent element is reported by name."""
    signed = _without(element)
    if element == "Reference":
        tree = etree.fromstring(signed)
        info = tree.find(f".//{{{DS}}}SignedInfo")
        etree.SubElement(info, f"{{{DS}}}DigestValue").text = "AAAA"
        signed = etree.tostring(tree)
    assert _reason(signed) == reason


def test_an_empty_signature_value_is_missing() -> None:
    """``<SignatureValue/>`` with no text is reported, not a crash."""
    tree = etree.fromstring(_sign())
    tree.find(f".//{{{DS}}}SignatureValue").text = None
    assert _reason(etree.tostring(tree)) == (
        "Missing or empty <SignatureValue> element."
    )


def test_base64_wrapped_over_lines_verifies() -> None:
    """Line breaks inside DigestValue and SignatureValue are ignored.

    The DigestValue is inside SignedInfo, so SignedInfo is signed again
    after wrapping it; the SignatureValue is wrapped afterwards.
    """
    tree = etree.fromstring(_sign())
    _wrap(tree.find(f".//{{{DS}}}DigestValue"))
    tree = etree.fromstring(_resigned(tree))
    _wrap(tree.find(f".//{{{DS}}}SignatureValue"))
    report = verify_signature(etree.tostring(tree), trust_anchor=_pem(_RSA))
    assert report.valid is True


def _wrap(element: Any) -> None:
    """Break ``element``'s base64 text into 16-character lines."""
    text = element.text
    element.text = "\n".join(text[i : i + 16] for i in range(0, len(text), 16))


def test_signature_value_outside_the_alphabet_is_refused() -> None:
    """Strict base64: a stray character is refused, not skipped."""
    tree = etree.fromstring(_sign())
    tree.find(f".//{{{DS}}}SignatureValue").text = "AAAA!"
    assert _reason(etree.tostring(tree)) == (
        "<SignatureValue> is not valid base64"
    )


def test_signature_placement_reasons() -> None:
    """None, two, or a Signature that is the whole document."""
    assert _reason(b"<a/>") == (
        "No XML-DSig <Signature> element found in document."
    )
    once = _sign()
    twice = once.replace(
        b"</p:Document>",
        once[once.index(b"<ds:Signature") : once.index(b"</ds:Signature>")]
        + b"</ds:Signature></p:Document>",
    )
    assert _reason(twice) == (
        "2 <Signature> elements: pain001 verifies a document with exactly one"
    )
    sig = etree.fromstring(once).find(f"{{{DS}}}Signature")
    assert _reason(etree.tostring(sig)) == (
        "the <Signature> must be inside the document it signs, "
        "not the document itself"
    )


def test_a_second_reference_reason() -> None:
    """Two References are refused with the count."""
    tree = etree.fromstring(_sign())
    info = tree.find(f".//{{{DS}}}SignedInfo")
    extra = etree.fromstring(etree.tostring(info.find(f"{{{DS}}}Reference")))
    info.append(extra)
    assert _reason(_resigned(tree)) == (
        "2 <Reference> elements: pain001 verifies SignedInfo with exactly "
        "one <Reference>"
    )


def _with_keyinfo(signed: bytes, text: str) -> bytes:
    """``signed`` with ``text`` as its KeyInfo certificate."""
    tree = etree.fromstring(signed)
    sig = tree.find(f"{{{DS}}}Signature")
    data = etree.SubElement(
        etree.SubElement(sig, f"{{{DS}}}KeyInfo"), f"{{{DS}}}X509Data"
    )
    etree.SubElement(data, f"{{{DS}}}X509Certificate").text = text
    return bytes(etree.tostring(tree))


def test_embedded_certificate_base64_rules() -> None:
    """Wrapped base64 is read; characters outside the alphabet are not."""
    der = x509.load_pem_x509_certificate(_cert("Wrapped")).public_bytes(
        serialization.Encoding.DER
    )

    text = base64.b64encode(der).decode()
    wrapped = "\n".join(text[i : i + 64] for i in range(0, len(text), 64))
    report = verify_signature(
        _with_keyinfo(_sign(), wrapped), trust_embedded_cert=True
    )
    assert report.valid is True and report.signer == "CN=Wrapped"
    assert _reason(_with_keyinfo(_sign(), "AAAA!")) == (
        "<X509Certificate> is not valid base64"
    )


def test_a_bad_trust_anchor_message() -> None:
    """The anchor refusal says what it accepts."""
    with pytest.raises(ValueError) as error:
        _dsig_verify.load_trust_anchor("not a key")
    assert str(error.value).startswith(
        "the trust anchor is neither a PEM certificate nor a PEM public key: "
    )


def test_inclusive_namespaces_without_a_prefix_list() -> None:
    """A bare ``InclusiveNamespaces`` means no extra prefixes."""
    tree = etree.fromstring(_sign(empty_prefix_list=True))
    for found in tree.iter(f"{{{EXC}}}InclusiveNamespaces"):
        del found.attrib["PrefixList"]
    report = verify_signature(_resigned(tree), trust_anchor=_pem(_RSA))
    assert report.valid is True


def test_comments_are_not_signed_over() -> None:
    """Exclusive C14N without comments: a commented document verifies."""
    commented = DOC.replace("<p:GrpHdr>", "<!-- prepared by ops --><p:GrpHdr>")
    report = verify_signature(_sign(commented), trust_anchor=_pem(_RSA))
    assert report.valid is True


_ALG = 'Algorithm="'


@pytest.mark.parametrize(
    ("old", "new", "reason"),
    [
        (
            b'<ds:Reference URI="">',
            b'<ds:Reference URI="#x">',
            "the Reference must sign the whole document (URI=\"\"), not '#x'",
        ),
        (
            b'<ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#'
            b'enveloped-signature"',
            b'<ds:Transform Algorithm="urn:x"',
            "unsupported transforms: pain001 verifies the enveloped "
            f"transform, optionally then exclusive C14N, not ['urn:x', '{EXC}']",
        ),
        (
            b'<ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"',
            b'<ds:DigestMethod Algorithm="urn:x"',
            "digest method 'urn:x' is not allowed",
        ),
        (
            b'<ds:CanonicalizationMethod Algorithm="' + EXC.encode() + b'"',
            b'<ds:CanonicalizationMethod Algorithm="urn:x"',
            "SignedInfo must use exclusive C14N, not 'urn:x'",
        ),
        (
            b"http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
            b"http://www.w3.org/2000/09/xmldsig#rsa-sha1",
            "signature method 'http://www.w3.org/2000/09/xmldsig#rsa-sha1' "
            "is not allowed",
        ),
    ],
)
def test_declared_method_reasons_are_exact(
    old: bytes, new: bytes, reason: str
) -> None:
    """Each refused declaration quotes the value it found."""
    signed = _sign()
    assert old in signed
    assert _reason(signed.replace(old, new, 1)) == reason


def test_signature_first_with_no_text_before_it() -> None:
    """Removing a first-child Signature keeps its tail as the root text."""
    tree = etree.fromstring(_sign(at=0))
    sig = tree.find(f"{{{DS}}}Signature")
    sig.tail = (tree.text or "") + (sig.tail or "")
    tree.text = None
    report = verify_signature(etree.tostring(tree), trust_anchor=_pem(_RSA))
    assert report.valid is True


def test_the_anchor_subject_wins_over_a_matching_keyinfo() -> None:
    """Same key, two names: the trusted anchor's subject is reported."""
    signed = sign_xml_document(DOC, _private_pem(_RSA), _cert("In KeyInfo"))
    report = verify_signature(signed, trust_anchor=_cert("The Anchor"))
    assert report.valid is True
    assert report.signer == "CN=The Anchor"
    assert report.keyinfo_mismatch is False


def test_no_key_anywhere_and_no_trust_choice() -> None:
    """Embedded trust with no certificate, and no trust choice at all."""
    assert _reason(_sign(), trust_embedded_cert=True) == (
        "No public key or certificate supplied and none found in <KeyInfo>."
    )
    with pytest.raises(ValueError) as error:
        verify_signature(_sign())
    assert str(error.value) == (
        "pass trust_anchor (the signer's certificate or public key), or "
        "trust_embedded_cert=True for an integrity-only check"
    )
