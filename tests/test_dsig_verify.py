# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""``verify_signature`` and the signature algorithms (0.0.83).

``_sign`` below writes an enveloped signature the way other
implementations do (signxml, xmlsec1): exclusive C14N over the parsed
document, the document's own prefixes kept, the Signature wherever the
caller puts it. pain001 0.0.82 rejected such signatures with a digest
mismatch; these tests hold the verifier to the specification instead of
to pain001's own signer.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from lxml import etree

from pain001.security import _dsig_algorithms as algs
from pain001.security.dsig import (
    SignatureReport,
    XmlSignatureError,
    sign_xml_document,
    verify_signature,
)

DS = "http://www.w3.org/2000/09/xmldsig#"
EXC = "http://www.w3.org/2001/10/xml-exc-c14n#"
ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"

DOC = (
    '<p:Document xmlns:p="urn:iso:std:iso:20022:tech:xsd:pain.001.001.09" '
    'xmlns:unused="urn:example:unused">\n'
    "  <p:CstmrCdtTrfInitn>\n"
    "    <p:GrpHdr><p:MsgId>M-1</p:MsgId></p:GrpHdr>\n"
    "  </p:CstmrCdtTrfInitn>\n"
    "</p:Document>\n"
)

_RSA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_P256 = ec.generate_private_key(ec.SECP256R1())
_P384 = ec.generate_private_key(ec.SECP384R1())


def _pem(key: Any) -> bytes:
    return bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def _private_pem(key: Any) -> bytes:
    return bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )


def _c14n(node: Any, prefixes: list[str] | None = None) -> bytes:
    return bytes(
        etree.tostring(
            node,
            method="c14n",
            exclusive=True,
            with_comments=False,
            inclusive_ns_prefixes=prefixes,
        )
    )


def _sign(
    xml: str = DOC,
    key: Any = _RSA,
    name: str = "rsa-sha256",
    *,
    at: int | None = None,
    prefixes: list[str] | None = None,
    empty_prefix_list: bool = False,
    second_transform: bool = True,
) -> bytes:
    """An enveloped signature written to the specification, not by pain001."""
    tree = etree.ElementTree(etree.fromstring(xml.encode("utf-8")))
    root = tree.getroot()
    digest = base64.b64encode(
        hashlib.sha256(_c14n(tree, prefixes)).digest()
    ).decode()
    sig = etree.Element(f"{{{DS}}}Signature", nsmap={"ds": DS})
    info = etree.SubElement(sig, f"{{{DS}}}SignedInfo")
    c14n = etree.SubElement(
        info, f"{{{DS}}}CanonicalizationMethod", Algorithm=EXC
    )
    if prefixes or empty_prefix_list:
        etree.SubElement(
            c14n,
            f"{{{EXC}}}InclusiveNamespaces",
            nsmap={"ec": EXC},
            PrefixList=" ".join(prefixes or []),
        )
    algorithm = algs.ALGORITHMS[name]
    etree.SubElement(info, f"{{{DS}}}SignatureMethod", Algorithm=algorithm.uri)
    ref = etree.SubElement(info, f"{{{DS}}}Reference", URI="")
    transforms = etree.SubElement(ref, f"{{{DS}}}Transforms")
    etree.SubElement(transforms, f"{{{DS}}}Transform", Algorithm=ENVELOPED)
    if second_transform:
        t = etree.SubElement(transforms, f"{{{DS}}}Transform", Algorithm=EXC)
        if prefixes:
            etree.SubElement(
                t,
                f"{{{EXC}}}InclusiveNamespaces",
                nsmap={"ec": EXC},
                PrefixList=" ".join(prefixes),
            )
    etree.SubElement(ref, f"{{{DS}}}DigestMethod", Algorithm=SHA256)
    etree.SubElement(ref, f"{{{DS}}}DigestValue").text = digest
    if at is None:
        root.append(sig)
    else:
        # Split the whitespace already there, so the signed text is
        # unchanged and some of it follows the Signature as its tail.
        if at == 0:
            space, root.text = root.text or "", (root.text or "")[:1]
            tail = space[1:]
        else:
            tail, root[at - 1].tail = root[at - 1].tail or "", ""
        assert tail, "the case needs text after the Signature"
        root.insert(at, sig)
        sig.tail = tail
    value = algs.sign_bytes(key, algorithm, _c14n(info, prefixes))
    etree.SubElement(sig, f"{{{DS}}}SignatureValue").text = base64.b64encode(
        value
    ).decode()
    return bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8"))


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("rsa-sha256", _RSA),
        ("rsa-pss-sha256", _RSA),
        ("ecdsa-sha256", _P256),
        ("ecdsa-sha384", _P384),
    ],
)
def test_a_specification_signature_verifies(name: str, key: Any) -> None:
    """Prefixes kept, exclusive C14N: what 0.0.82 rejected now verifies."""
    report = verify_signature(
        _sign(key=key, name=name), trust_anchor=_pem(key)
    )
    assert report == SignatureReport(
        valid=True, trust="anchor", algorithm=name
    )


@pytest.mark.parametrize("at", [0, 1])
def test_whitespace_after_the_signature_survives_its_removal(at: int) -> None:
    """The enveloped transform drops the element, not the text after it.

    First child (the text joins the parent's) and after a sibling (the
    text joins that sibling's tail).
    """
    signed = _sign(at=at)
    assert verify_signature(signed, trust_anchor=_pem(_RSA)).valid


def test_an_inclusive_prefix_list_is_honoured() -> None:
    signed = _sign(prefixes=["unused"])
    assert verify_signature(signed, trust_anchor=_pem(_RSA)).valid
    empty = _sign(empty_prefix_list=True)
    assert verify_signature(empty, trust_anchor=_pem(_RSA)).valid


def test_one_enveloped_transform_is_enough() -> None:
    signed = _sign(second_transform=False)
    assert verify_signature(signed, trust_anchor=_pem(_RSA)).valid


def test_text_input_and_the_wrong_key() -> None:
    signed = _sign().decode("utf-8")
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    report = verify_signature(signed, trust_anchor=_pem(other))
    assert not report.valid
    assert report.reason is not None
    assert report.reason.startswith("Cryptographic signature verification")


def test_a_changed_payload_is_a_digest_mismatch() -> None:
    signed = _sign().replace(b"M-1", b"M-2")
    report = verify_signature(signed, trust_anchor=_pem(_RSA))
    assert report.reason is not None and "Digest mismatch" in report.reason


def test_a_trust_choice_is_required() -> None:
    with pytest.raises(ValueError, match="trust_embedded_cert=True"):
        verify_signature(_sign())


def test_a_bad_anchor_is_refused() -> None:
    with pytest.raises(ValueError, match="neither a PEM certificate"):
        verify_signature(_sign(), trust_anchor="not a key")


def _reason(signed: bytes | str) -> str:
    report = verify_signature(signed, trust_anchor=_pem(_RSA))
    assert not report.valid and report.reason is not None
    return report.reason


@pytest.mark.parametrize(
    ("document", "reason"),
    [
        (b"<a", "not well-formed XML"),
        (
            b'<!DOCTYPE a [<!ENTITY x "y">]><a>&x;</a>',
            "DTDs and entities are not allowed",
        ),
        (b"<!DOCTYPE a><a/>", "DTDs and entities are not allowed"),
        (b"<a/>", "No XML-DSig <Signature>"),
    ],
)
def test_documents_that_cannot_be_checked(
    document: bytes, reason: str
) -> None:
    assert reason in _reason(document)


def test_two_signatures_are_refused() -> None:
    once = _sign()
    twice = once.replace(
        b"</p:Document>",
        once[once.index(b"<ds:Signature") : once.index(b"</ds:Signature>")]
        + b"</ds:Signature></p:Document>",
    )
    assert "exactly one" in _reason(twice)


_EDITS = [
    (
        b'<ds:Reference URI="">',
        b'<ds:Reference URI="#x">',
        "whole document",
    ),
    (
        b'Algorithm="' + ENVELOPED.encode() + b'"',
        b'Algorithm="urn:x"',
        "transforms",
    ),
    (
        b'Algorithm="' + SHA256.encode() + b'"',
        b'Algorithm="urn:x"',
        "digest method",
    ),
    (
        b'<ds:CanonicalizationMethod Algorithm="' + EXC.encode() + b'"',
        b'<ds:CanonicalizationMethod Algorithm="urn:x"',
        "exclusive C14N",
    ),
    (
        algs.SIG_RSA_SHA256.encode(),
        b"http://www.w3.org/2000/09/xmldsig#rsa-sha1",
        "is not allowed",
    ),
]


@pytest.mark.parametrize(("old", "new", "reason"), _EDITS)
def test_declared_methods_off_the_allow_list(
    old: bytes, new: bytes, reason: str
) -> None:
    assert reason in _reason(_sign().replace(old, new, 1))


@pytest.mark.parametrize(
    ("element", "reason"),
    [
        ("Reference", "Missing <Reference>"),
        ("DigestMethod", "Missing <DigestMethod>"),
        ("CanonicalizationMethod", "Missing <CanonicalizationMethod>"),
        ("SignatureMethod", "Missing <SignatureMethod>"),
    ],
)
def test_missing_signed_info_parts(element: str, reason: str) -> None:
    tree = etree.fromstring(_sign())
    for found in tree.iter(f"{{{DS}}}{element}"):
        if element == "Reference":
            found.getparent().remove(found)
            break
        found.getparent().remove(found)
    if element == "Reference":
        digest = etree.SubElement(
            tree.find(f".//{{{DS}}}SignedInfo"), f"{{{DS}}}DigestValue"
        )
        digest.text = "AAAA"
    assert reason in _reason(etree.tostring(tree))


def test_an_undecodable_signature_value() -> None:
    signed = etree.fromstring(_sign())
    signed.find(f".//{{{DS}}}SignatureValue").text = "not base64!"
    assert "not valid base64" in _reason(etree.tostring(signed))


def _with_cert(text: str | None) -> bytes:
    signed = etree.fromstring(_sign())
    sig = signed.find(f"{{{DS}}}Signature")
    data = etree.SubElement(
        etree.SubElement(sig, f"{{{DS}}}KeyInfo"), f"{{{DS}}}X509Data"
    )
    etree.SubElement(data, f"{{{DS}}}X509Certificate").text = text
    return bytes(etree.tostring(signed))


def test_embedded_certificates() -> None:
    assert "not a certificate" in _reason(_with_cert("AAAA"))
    empty = verify_signature(_with_cert(None), trust_embedded_cert=True)
    assert empty.reason is not None and "No public key" in empty.reason


def test_the_embedded_certificate_names_the_signer(
    rsa_cert_pem: tuple[bytes, bytes],
) -> None:
    key_pem, cert_pem = rsa_cert_pem
    signed = sign_xml_document(
        DOC, key_pem, cert_pem, algorithm="rsa-pss-sha256"
    )
    report = verify_signature(signed, trust_embedded_cert=True)
    assert report.valid and report.trust == "embedded"
    assert report.signer == "CN=dsig test"
    anchored = verify_signature(signed, trust_anchor=cert_pem)
    assert anchored.valid and anchored.trust == "anchor"
    assert anchored.signer == "CN=dsig test"


@pytest.fixture
def rsa_cert_pem() -> tuple[bytes, bytes]:
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import NameOID

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "dsig test")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(_RSA.public_key())
        .serial_number(7)
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(_RSA, hashes.SHA256())
    )
    return _private_pem(_RSA), cert.public_bytes(serialization.Encoding.PEM)


@pytest.mark.parametrize(
    ("key", "name"),
    [(_P256, "ecdsa-sha256"), (_P384, "ecdsa-sha384")],
)
def test_pain001_signs_with_ecdsa(key: Any, name: str) -> None:
    signed = sign_xml_document(DOC, _private_pem(key))
    report = verify_signature(signed, trust_anchor=_pem(key))
    assert report.valid and report.algorithm == name


def test_an_ecdsa_value_of_the_wrong_length() -> None:
    signed = etree.fromstring(_sign(key=_P256, name="ecdsa-sha256"))
    signed.find(f".//{{{DS}}}SignatureValue").text = "AAAA"
    report = verify_signature(etree.tostring(signed), trust_anchor=_pem(_P256))
    assert report.reason is not None and "raw r || s" in report.reason


def test_algorithm_for_key() -> None:
    assert algs.algorithm_for_key(_RSA).name == "rsa-sha256"
    assert (
        algs.algorithm_for_key(_RSA, "rsa-pss-sha256").name == "rsa-pss-sha256"
    )
    assert algs.algorithm_for_key(_P384.public_key()).name == "ecdsa-sha384"
    with pytest.raises(ValueError, match="unsupported EC curve"):
        algs.algorithm_for_key(ec.generate_private_key(ec.SECP521R1()))
    with pytest.raises(ValueError, match="unsupported key type"):
        algs.algorithm_for_key(ed25519.Ed25519PrivateKey.generate())
    with pytest.raises(ValueError, match="does not fit"):
        algs.algorithm_for_key(_RSA, "ecdsa-sha256")
    with pytest.raises(ValueError, match="does not fit"):
        algs.algorithm_for_key(_RSA, "no-such")
    with pytest.raises(ValueError, match="different curve"):
        algs.algorithm_for_key(_P256, "ecdsa-sha384")


def test_a_mismatched_algorithm_is_a_signing_error() -> None:
    with pytest.raises(XmlSignatureError, match="does not fit"):
        sign_xml_document(DOC, _private_pem(_P256), algorithm="rsa-sha256")
