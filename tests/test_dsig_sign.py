# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The 0.0.84 signer keeps parsed XML and the announced trust boundary."""

from __future__ import annotations

import base64
import hashlib

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from lxml import etree

from pain001.security.dsig import (
    XMLDSIG_NS,
    XmlSignatureError,
    sign_xml_document,
    verify_signature,
    verify_xml_signature,
)
from pain001.xml.envelope import (
    BAH_NAMESPACE,
    BusinessApplicationHeader,
    envelop_iso20022_message,
)

DOC = (
    '<Document xmlns="urn:synthetic:document"><Amount>1.00</Amount></Document>'
)


@pytest.fixture(scope="module")
def signing_material() -> tuple[bytes, bytes]:
    """Generate a throwaway key pair; no private material is committed."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
    )


@pytest.mark.parametrize(
    "payload",
    [
        DOC,
        '<p:Document xmlns:p="urn:synthetic:document" xmlns:unused="urn:unused">'
        '<p:Message xml:space="preserve">  Café &amp; tea  </p:Message>'
        "</p:Document>",
    ],
)
def test_signer_preserves_payload_namespaces(
    signing_material: tuple[bytes, bytes], payload: str
) -> None:
    """Signing must retain the caller's namespace bindings and prefixes."""
    key, public = signing_material
    original = etree.fromstring(payload.encode())
    signed = sign_xml_document(payload, key)
    tree = etree.fromstring(signed.encode())
    assert tree.prefix == original.prefix
    assert tree.nsmap == original.nsmap
    assert tree[0].text == original[0].text
    assert verify_signature(signed, trust_anchor=public).valid


def test_payload_digest_is_exclusive_c14n(
    signing_material: tuple[bytes, bytes],
) -> None:
    """The digest must match the declared algorithm on the parsed XML."""
    key, _ = signing_material
    raw = (
        '<root xmlns:unused="urn:unused"><child a="1">synthetic</child></root>'
    )
    canonical = etree.tostring(
        etree.fromstring(raw.encode()), method="c14n", exclusive=True
    )
    expected = base64.b64encode(hashlib.sha256(canonical).digest()).decode()
    signed = etree.fromstring(sign_xml_document(raw, key).encode())
    digest = signed.find(f".//{{{XMLDSIG_NS}}}DigestValue")
    assert digest is not None and digest.text == expected
    assert signed.nsmap == {"unused": "urn:unused"}


def test_legacy_verifier_requires_an_explicit_anchor() -> None:
    """Missing trust is a caller error, even before XML parsing."""
    with pytest.raises(ValueError, match="public_key_pem or cert_pem"):
        verify_xml_signature("not a signed document")


@pytest.mark.parametrize("wrapped", [True, False])
def test_signature_is_placed_in_bah(
    signing_material: tuple[bytes, bytes], wrapped: bool
) -> None:
    """Both supported BizData layouts put the signature in AppHdr/Sgntr."""
    key, public = signing_material
    header = BusinessApplicationHeader(
        from_id="SYNTHETIC-SENDER",
        to_id="SYNTHETIC-RECEIVER",
        biz_msg_idr="SIGNATURE-84",
        cre_dt="2026-11-09T00:00:00Z",
    )
    raw = envelop_iso20022_message(DOC, header, wrapped=wrapped)
    signed = sign_xml_document(raw, key)
    tree = etree.fromstring(signed.encode())
    signature = tree.find(
        f".//{{{BAH_NAMESPACE}}}AppHdr/{{{BAH_NAMESPACE}}}Sgntr/{{{XMLDSIG_NS}}}Signature"
    )
    assert signature is not None
    assert tree.find(f"{{{XMLDSIG_NS}}}Signature") is None
    assert verify_signature(signed, trust_anchor=public).valid


def test_existing_empty_signature_container_is_reused(
    signing_material: tuple[bytes, bytes],
) -> None:
    """The container is part of the payload before its digest is computed."""
    key, public = signing_material
    raw = (
        f'<h:AppHdr xmlns:h="{BAH_NAMESPACE}"><h:Sgntr> </h:Sgntr></h:AppHdr>'
    )
    signed = sign_xml_document(raw, key)
    tree = etree.fromstring(signed.encode())
    containers = tree.findall(f"{{{BAH_NAMESPACE}}}Sgntr")
    assert len(containers) == 1
    assert containers[0].find(f"{{{XMLDSIG_NS}}}Signature") is not None
    assert verify_signature(signed, trust_anchor=public).valid


def test_header_signature_precedes_related_header(
    signing_material: tuple[bytes, bytes],
) -> None:
    """An existing related-header field keeps its position after Sgntr."""
    key, public = signing_material
    raw = f'<h:AppHdr xmlns:h="{BAH_NAMESPACE}"><h:Rltd/></h:AppHdr>'
    signed = sign_xml_document(raw, key)
    tree = etree.fromstring(signed.encode())
    assert [child.tag for child in tree] == [
        f"{{{BAH_NAMESPACE}}}Sgntr",
        f"{{{BAH_NAMESPACE}}}Rltd",
    ]
    assert verify_signature(signed, trust_anchor=public).valid


@pytest.mark.parametrize(
    "raw, reason",
    [
        (
            f'<root xmlns:ds="{XMLDSIG_NS}"><ds:Signature/></root>',
            "already contains",
        ),
        (
            f'<root xmlns:h="{BAH_NAMESPACE}"><h:AppHdr/><h:AppHdr/></root>',
            "one AppHdr",
        ),
        (
            f'<h:AppHdr xmlns:h="{BAH_NAMESPACE}"><h:Sgntr/><h:Sgntr/></h:AppHdr>',
            "one Sgntr",
        ),
        (
            f'<h:AppHdr xmlns:h="{BAH_NAMESPACE}"><h:Sgntr><other/></h:Sgntr></h:AppHdr>',
            "empty",
        ),
        (
            f'<h:AppHdr xmlns:h="{BAH_NAMESPACE}"><h:Sgntr>occupied</h:Sgntr></h:AppHdr>',
            "empty",
        ),
        ('<root xmlns="relative"/>', "C14N"),
        (
            '<!DOCTYPE root [<!ENTITY x "synthetic">]><root>&x;</root>',
            "DTDs and entities",
        ),
        ("<root>", "not well-formed"),
    ],
)
def test_signer_refuses_ambiguous_or_unsafe_input(
    signing_material: tuple[bytes, bytes], raw: str, reason: str
) -> None:
    """Invalid input cannot produce a document this verifier would reject."""
    key, _ = signing_material
    with pytest.raises(XmlSignatureError, match=reason):
        sign_xml_document(raw, key)
