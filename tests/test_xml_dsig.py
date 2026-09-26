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

"""Unit tests for W3C XML Digital Signature (XML-DSig) for ISO 20022 messages."""

import xml.etree.ElementTree as et
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pain001.security.dsig import (
    XmlSignatureError,
    _get_cryptography_modules,
    canonicalize_xml,
    compute_sha256_digest,
    sign_xml_document,
    verify_xml_signature,
)

SAMPLE_XML = (
    '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">'
    "<CstmrCdtTrfInitn><GrpHdr><MsgId>MSG-100</MsgId></GrpHdr></CstmrCdtTrfInitn>"
    "</Document>"
)


@pytest.fixture
def rsa_key_and_cert() -> tuple[bytes, bytes, bytes]:
    """Generate temporary in-memory RSA keypair and self-signed certificate."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = private_key.public_key()
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "GB"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Bank"),
            x509.NameAttribute(NameOID.COMMON_NAME, "test.bank.org"),
        ]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .sign(private_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    return key_pem, pub_pem, cert_pem


def test_canonicalize_xml_string_and_element() -> None:
    """Verify exclusive canonicalization produces standard deterministic c14n output."""
    xml_str = '<root b="2" a="1"><child>text</child></root>'
    c14n1 = canonicalize_xml(xml_str)
    assert '<root a="1" b="2"><child>text</child></root>' == c14n1

    root_el = et.fromstring(xml_str)
    c14n2 = canonicalize_xml(root_el)
    assert c14n1 == c14n2


def test_compute_sha256_digest() -> None:
    """Verify SHA-256 digest computation matches expected base64 format."""
    digest = compute_sha256_digest("<test/>")
    assert isinstance(digest, str)
    assert len(digest) == 44  # Base64 encoded SHA-256 is 44 characters
    assert digest.endswith("=")


def test_sign_and_verify_with_public_key(
    rsa_key_and_cert: tuple[bytes, bytes, bytes],
) -> None:
    """Verify round-trip signing and verification using RSA public key."""
    key_pem, pub_pem, _ = rsa_key_and_cert
    signed_xml = sign_xml_document(SAMPLE_XML, key_pem.decode("utf-8"))

    assert "Signature" in signed_xml
    assert "SignatureValue" in signed_xml
    assert verify_xml_signature(signed_xml, public_key_pem=pub_pem) is True


def test_sign_and_verify_with_certificate(
    rsa_key_and_cert: tuple[bytes, bytes, bytes],
) -> None:
    """Verify round-trip signing with embedded X.509 cert and verification from KeyInfo."""
    key_pem, _, cert_pem = rsa_key_and_cert
    signed_xml = sign_xml_document(
        SAMPLE_XML,
        private_key_pem=key_pem,
        cert_pem=cert_pem,
    )

    assert "X509Certificate" in signed_xml
    # Verification without explicit public key extracts cert from KeyInfo
    assert verify_xml_signature(signed_xml) is True
    # Verification with explicit certificate
    assert verify_xml_signature(signed_xml, cert_pem=cert_pem) is True


def test_sign_with_passphrase(
    rsa_key_and_cert: tuple[bytes, bytes, bytes],
) -> None:
    """Verify signing with encrypted private key and passphrase."""
    key_pem, pub_pem, _ = rsa_key_and_cert
    priv_key = serialization.load_pem_private_key(key_pem, password=None)
    enc_key_pem = priv_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(
            b"secret123"
        ),
    )

    signed_xml = sign_xml_document(
        SAMPLE_XML,
        private_key_pem=enc_key_pem,
        passphrase="secret123",
    )
    assert verify_xml_signature(signed_xml, public_key_pem=pub_pem) is True


def test_tampered_payload_fails_verification(
    rsa_key_and_cert: tuple[bytes, bytes, bytes],
) -> None:
    """Verify payload tampering after signing is detected via digest mismatch."""
    key_pem, pub_pem, _ = rsa_key_and_cert
    signed_xml = sign_xml_document(SAMPLE_XML, key_pem)

    tampered_xml = signed_xml.replace("MSG-100", "MSG-TAMPERED")
    with pytest.raises(XmlSignatureError, match="Digest mismatch"):
        verify_xml_signature(tampered_xml, public_key_pem=pub_pem)


def test_tampered_signature_fails_verification(
    rsa_key_and_cert: tuple[bytes, bytes, bytes],
) -> None:
    """Verify corrupted signature bytes fail cryptographic verification."""
    key_pem, pub_pem, _ = rsa_key_and_cert
    signed_xml = sign_xml_document(SAMPLE_XML, key_pem)

    root = et.fromstring(signed_xml)
    sig_val = root.find(
        ".//{http://www.w3.org/2000/09/xmldsig#}SignatureValue"
    )
    assert sig_val is not None and sig_val.text is not None
    # Flip the first char of base64 signature
    corrupted_b64 = ("A" if sig_val.text[0] != "A" else "B") + sig_val.text[1:]
    sig_val.text = corrupted_b64
    corrupted_xml = et.tostring(root, encoding="unicode")

    with pytest.raises(
        XmlSignatureError, match="Cryptographic signature verification failed"
    ):
        verify_xml_signature(corrupted_xml, public_key_pem=pub_pem)


def test_verify_missing_signature() -> None:
    """Verify unsigned document raises XmlSignatureError."""
    with pytest.raises(XmlSignatureError, match="No XML-DSig <Signature>"):
        verify_xml_signature(SAMPLE_XML)


def test_verify_malformed_signature_elements(
    rsa_key_and_cert: tuple[bytes, bytes, bytes],
) -> None:
    """Verify malformed Signature elements (missing SignedInfo, SignatureValue, DigestValue)."""
    _, pub_pem, _ = rsa_key_and_cert

    # Missing SignedInfo
    xml_no_si = (
        '<root><Signature xmlns="http://www.w3.org/2000/09/xmldsig#"/></root>'
    )
    with pytest.raises(XmlSignatureError, match="Missing <SignedInfo>"):
        verify_xml_signature(xml_no_si, public_key_pem=pub_pem)

    # Missing SignatureValue
    xml_no_sv = (
        '<root><Signature xmlns="http://www.w3.org/2000/09/xmldsig#">'
        "<SignedInfo/>"
        "</Signature></root>"
    )
    with pytest.raises(
        XmlSignatureError, match="Missing or empty <SignatureValue>"
    ):
        verify_xml_signature(xml_no_sv, public_key_pem=pub_pem)

    # Missing DigestValue
    xml_no_dv = (
        '<root><Signature xmlns="http://www.w3.org/2000/09/xmldsig#">'
        "<SignedInfo><Reference URI=''/></SignedInfo>"
        "<SignatureValue>ABCD</SignatureValue>"
        "</Signature></root>"
    )
    with pytest.raises(
        XmlSignatureError, match="Missing or empty <DigestValue>"
    ):
        verify_xml_signature(xml_no_dv, public_key_pem=pub_pem)


def test_verify_missing_key_and_cert() -> None:
    """Verify XmlSignatureError raised when no key/cert given and no KeyInfo present."""
    xml_no_key = (
        '<root><Signature xmlns="http://www.w3.org/2000/09/xmldsig#">'
        "<SignedInfo><DigestValue>dummy</DigestValue></SignedInfo>"
        "<SignatureValue>AAAA</SignatureValue>"
        "</Signature></root>"
    )
    with pytest.raises(
        XmlSignatureError, match="No public key or certificate supplied"
    ):
        verify_xml_signature(xml_no_key)


def test_invalid_private_key() -> None:
    """Verify invalid private key data raises XmlSignatureError."""
    with pytest.raises(XmlSignatureError, match="Failed to load private key"):
        sign_xml_document(SAMPLE_XML, "NOT-A-KEY")


def test_missing_cryptography_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify clear error message when cryptography import fails."""
    import builtins

    orig_import = builtins.__import__

    def mock_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "cryptography" or name.startswith("cryptography."):
            raise ImportError("No module named 'cryptography'")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    with pytest.raises(
        XmlSignatureError, match="The 'cryptography' package is required"
    ):
        _get_cryptography_modules()


def test_signing_failure_raises_xml_signature_error(
    rsa_key_and_cert: tuple[bytes, bytes, bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify XmlSignatureError when private_key.sign() raises an exception."""
    key_pem, _, _ = rsa_key_and_cert
    from cryptography.hazmat.primitives import serialization

    class BadKey:
        def sign(self, *args: object, **kwargs: object) -> bytes:
            raise ValueError("Simulated signing hardware error")

    monkeypatch.setattr(
        serialization,
        "load_pem_private_key",
        lambda *args, **kwargs: BadKey(),
    )
    with pytest.raises(
        XmlSignatureError,
        match="Signing failed: Simulated signing hardware error",
    ):
        sign_xml_document(SAMPLE_XML, key_pem)
