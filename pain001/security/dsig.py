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

"""W3C XML Digital Signature (XML-DSig) for ISO 20022 financial messages."""

from __future__ import annotations

import base64
import hashlib
import xml.etree.ElementTree as et  # nosec B405
from typing import Any

import defusedxml.ElementTree as defused_et

C14N_EXCLUSIVE = "http://www.w3.org/2001/10/xml-exc-c14n#"
DIGEST_SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"
SIG_RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
TRANSFORM_ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
XMLDSIG_NS = "http://www.w3.org/2000/09/xmldsig#"


class XmlSignatureError(Exception):
    """Raised when XML digital signature generation or verification fails."""


def canonicalize_xml(xml_content: str | et.Element) -> str:
    """Produce W3C Exclusive Canonicalized XML (c14n) string.

    Args:
        xml_content: An XML string or ElementTree.Element.

    Returns:
        The canonicalized XML string.
    """
    if isinstance(xml_content, et.Element):
        raw_xml = et.tostring(xml_content, encoding="unicode")
    else:
        raw_xml = xml_content
    return et.canonicalize(raw_xml, with_comments=False)


def compute_sha256_digest(canonical_xml: str) -> str:
    """Compute base64-encoded SHA-256 digest of canonical XML.

    Args:
        canonical_xml: The canonical XML string.

    Returns:
        The base64-encoded digest string.
    """
    digest_bytes = hashlib.sha256(canonical_xml.encode("utf-8")).digest()
    return base64.b64encode(digest_bytes).decode("ascii")


def _get_cryptography_modules() -> tuple[Any, Any, Any, Any]:
    """Import and return cryptography modules, raising XmlSignatureError if missing.

    Returns:
        Tuple of (serialization, hashes, padding, x509).

    Raises:
        XmlSignatureError: If cryptography library is not installed.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError as err:
        raise XmlSignatureError(
            "The 'cryptography' package is required for XML-DSig RSA signing. "
            "Install it via `pip install cryptography`."
        ) from err
    return serialization, hashes, padding, x509


def sign_xml_document(
    xml_content: str,
    private_key_pem: str | bytes,
    cert_pem: str | bytes | None = None,
    passphrase: str | bytes | None = None,
) -> str:
    """Sign an XML document using W3C XML-DSig Enveloped RSA-SHA256 signature.

    Args:
        xml_content: The raw XML document string.
        private_key_pem: RSA private key in PEM format (string or bytes).
        cert_pem: Optional X.509 certificate in PEM format to embed in KeyInfo.
        passphrase: Optional passphrase for the private key.

    Returns:
        The signed XML document string.

    Raises:
        XmlSignatureError: If key loading or signing fails.
    """
    serialization, hashes, padding, _ = _get_cryptography_modules()

    key_bytes = (
        private_key_pem.encode("utf-8")
        if isinstance(private_key_pem, str)
        else private_key_pem
    )
    pw_bytes = (
        passphrase.encode("utf-8")
        if isinstance(passphrase, str)
        else passphrase
    )

    try:
        private_key = serialization.load_pem_private_key(
            key_bytes, password=pw_bytes
        )
    except Exception as err:
        raise XmlSignatureError(f"Failed to load private key: {err}") from err

    root = defused_et.fromstring(xml_content)

    et.register_namespace("ds", XMLDSIG_NS)

    # 1. Canonicalize payload before signature insertion
    canonical_payload = canonicalize_xml(root)
    digest_val = compute_sha256_digest(canonical_payload)

    # 2. Build SignedInfo element
    signed_info_xml = (
        f'<ds:SignedInfo xmlns:ds="{XMLDSIG_NS}">'
        f'<ds:CanonicalizationMethod Algorithm="{C14N_EXCLUSIVE}"/>'
        f'<ds:SignatureMethod Algorithm="{SIG_RSA_SHA256}"/>'
        f'<ds:Reference URI="">'
        f"<ds:Transforms>"
        f'<ds:Transform Algorithm="{TRANSFORM_ENVELOPED}"/>'
        f'<ds:Transform Algorithm="{C14N_EXCLUSIVE}"/>'
        f"</ds:Transforms>"
        f'<ds:DigestMethod Algorithm="{DIGEST_SHA256}"/>'
        f"<ds:DigestValue>{digest_val}</ds:DigestValue>"
        f"</ds:Reference>"
        f"</ds:SignedInfo>"
    )
    canonical_signed_info = canonicalize_xml(signed_info_xml)

    # 3. Sign canonical SignedInfo
    try:
        sig_bytes = private_key.sign(
            canonical_signed_info.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except Exception as err:
        raise XmlSignatureError(f"Signing failed: {err}") from err

    sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

    # 4. Build Signature Element
    sig_el = et.Element(f"{{{XMLDSIG_NS}}}Signature")
    signed_info_el = defused_et.fromstring(signed_info_xml)
    sig_el.append(signed_info_el)

    sig_val_el = et.SubElement(sig_el, f"{{{XMLDSIG_NS}}}SignatureValue")
    sig_val_el.text = sig_b64

    if cert_pem is not None:
        cert_str = (
            cert_pem.decode("utf-8")
            if isinstance(cert_pem, bytes)
            else cert_pem
        )
        cert_clean = (
            cert_str.replace("-----BEGIN CERTIFICATE-----", "")
            .replace("-----END CERTIFICATE-----", "")
            .replace("\n", "")
            .replace("\r", "")
            .strip()
        )
        key_info_el = et.SubElement(sig_el, f"{{{XMLDSIG_NS}}}KeyInfo")
        x509_data_el = et.SubElement(key_info_el, f"{{{XMLDSIG_NS}}}X509Data")
        x509_cert_el = et.SubElement(
            x509_data_el, f"{{{XMLDSIG_NS}}}X509Certificate"
        )
        x509_cert_el.text = cert_clean

    root.append(sig_el)
    body = et.tostring(root, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{body}'


def verify_xml_signature(
    signed_xml: str | bytes,
    public_key_pem: str | bytes | None = None,
    cert_pem: str | bytes | None = None,
) -> bool:
    """Verify a W3C XML-DSig Enveloped RSA-SHA256 digital signature.

    Args:
        signed_xml: The signed XML document string or bytes.
        public_key_pem: Optional public key in PEM format.
        cert_pem: Optional X.509 certificate in PEM format.

    Returns:
        True if signature is valid.

    Raises:
        XmlSignatureError: If signature verification fails or signature is missing.
    """
    serialization, hashes, padding, x509 = _get_cryptography_modules()

    raw_str = (
        signed_xml.decode("utf-8")
        if isinstance(signed_xml, bytes)
        else signed_xml
    )
    et.register_namespace("ds", XMLDSIG_NS)
    root = defused_et.fromstring(raw_str)

    # Locate Signature element
    sig_el = None
    for el in root.iter():
        if el.tag.endswith("Signature") and (
            el.tag == f"{{{XMLDSIG_NS}}}Signature" or "Signature" in el.tag
        ):
            sig_el = el
            break

    if sig_el is None:
        raise XmlSignatureError(
            "No XML-DSig <Signature> element found in document."
        )

    # Extract SignedInfo, SignatureValue, and DigestValue
    signed_info_el = sig_el.find(f"{{{XMLDSIG_NS}}}SignedInfo")
    if signed_info_el is None:
        signed_info_el = sig_el.find(".//SignedInfo")
    if signed_info_el is None:
        raise XmlSignatureError("Missing <SignedInfo> element in signature.")

    sig_val_el = sig_el.find(f"{{{XMLDSIG_NS}}}SignatureValue")
    if sig_val_el is None:
        sig_val_el = sig_el.find(".//SignatureValue")
    if sig_val_el is None or not sig_val_el.text:
        raise XmlSignatureError("Missing or empty <SignatureValue> element.")

    digest_val_el = signed_info_el.find(f".//{{{XMLDSIG_NS}}}DigestValue")
    if digest_val_el is None:
        digest_val_el = signed_info_el.find(".//DigestValue")
    if digest_val_el is None or not digest_val_el.text:
        raise XmlSignatureError(
            "Missing or empty <DigestValue> in <SignedInfo>."
        )

    expected_digest = digest_val_el.text.strip()
    signature_bytes = base64.b64decode(sig_val_el.text.strip())

    # Resolve public key
    public_key = None
    if public_key_pem is not None:
        pk_bytes = (
            public_key_pem.encode("utf-8")
            if isinstance(public_key_pem, str)
            else public_key_pem
        )
        public_key = serialization.load_pem_public_key(pk_bytes)
    elif cert_pem is not None:
        c_bytes = (
            cert_pem.encode("utf-8") if isinstance(cert_pem, str) else cert_pem
        )
        cert = x509.load_pem_x509_certificate(c_bytes)
        public_key = cert.public_key()
    else:
        # Extract from KeyInfo
        x509_cert_el = sig_el.find(f".//{{{XMLDSIG_NS}}}X509Certificate")
        if x509_cert_el is None:
            x509_cert_el = sig_el.find(".//X509Certificate")
        if x509_cert_el is not None and x509_cert_el.text:
            cert_b64 = x509_cert_el.text.strip()
            cert_der = base64.b64decode(cert_b64)
            cert = x509.load_der_x509_certificate(cert_der)
            public_key = cert.public_key()

    if public_key is None:
        raise XmlSignatureError(
            "No public key or certificate supplied and none found in <KeyInfo>."
        )

    # Verify digest of document excluding the Signature
    root.remove(sig_el)
    canonical_payload = canonicalize_xml(root)
    actual_digest = compute_sha256_digest(canonical_payload)

    if actual_digest != expected_digest:
        raise XmlSignatureError(
            f"Digest mismatch: payload digest {actual_digest} does not match {expected_digest}."
        )

    # Verify signature over canonical SignedInfo
    canonical_signed_info = canonicalize_xml(signed_info_el)
    try:
        public_key.verify(
            signature_bytes,
            canonical_signed_info.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except Exception as err:
        raise XmlSignatureError(
            f"Cryptographic signature verification failed: {err}"
        ) from err

    return True
