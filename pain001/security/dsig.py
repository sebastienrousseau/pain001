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

"""W3C XML Digital Signature (XML-DSig) for ISO 20022 financial messages.

``sign_xml_document`` writes an enveloped signature with RSA-SHA256,
RSA-PSS or ECDSA (the algorithm follows the key, or ``algorithm``).
``verify_signature`` checks one and returns a ``SignatureReport``; it
needs a trust anchor, or ``trust_embedded_cert=True`` for an
integrity-only check. ``verify_xml_signature`` is the older boolean form.

Announced for 0.0.84: ``verify_xml_signature`` without a key or
certificate is refused instead of trusting the document's own
certificate, and ``sign_xml_document`` signs the parsed document with
exclusive C14N 1.0 and keeps its namespace prefixes instead of rewriting
the tree through ElementTree (``ns0:``).
"""

from __future__ import annotations

import base64
import hashlib
import warnings
import xml.etree.ElementTree as et  # nosec B405
from typing import Any

import defusedxml.ElementTree as defused_et

from pain001.security._dsig_algorithms import (
    SIG_RSA_SHA256,
    SignatureAlgorithm,
    algorithm_for_key,
    sign_bytes,
)
from pain001.security._dsig_verify import (
    C14N_EXCLUSIVE,
    TRANSFORM_ENVELOPED,
    XMLDSIG_NS,
    SignatureReport,
    verify_signature,
)

DIGEST_SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"

__all__ = [
    "C14N_EXCLUSIVE",
    "DIGEST_SHA256",
    "SIG_RSA_SHA256",
    "TRANSFORM_ENVELOPED",
    "XMLDSIG_NS",
    "SignatureReport",
    "XmlSignatureError",
    "canonicalize_xml",
    "compute_sha256_digest",
    "sign_xml_document",
    "verify_signature",
    "verify_xml_signature",
]


class XmlSignatureError(Exception):
    """Raised when XML digital signature generation or verification fails."""


def canonicalize_xml(xml_content: str | et.Element) -> str:
    """Canonicalise XML the way ``sign_xml_document`` has since 0.0.60.

    This is ElementTree's C14N 2.0, kept so 0.0.83 signs byte for byte
    as 0.0.82 did; verification uses exclusive C14N 1.0 on the parsed
    tree instead. 0.0.84 signs with exclusive C14N too (announced).

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
            "Install it via `pip install pain001[sign]`."
        ) from err
    return serialization, hashes, padding, x509


def _load_signing_key(
    private_key_pem: str | bytes,
    passphrase: str | bytes | None,
    algorithm: str | None,
) -> tuple[Any, SignatureAlgorithm]:
    """The private key and the algorithm it signs with.

    Args:
        private_key_pem: The PEM private key.
        passphrase: Its passphrase, if any.
        algorithm: The requested algorithm name, or None for the key's.

    Returns:
        The key and its algorithm.

    Raises:
        XmlSignatureError: If the key does not load or does not fit.
    """
    serialization, _, _, _ = _get_cryptography_modules()
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
    try:
        return private_key, algorithm_for_key(private_key, algorithm)
    except ValueError as err:
        raise XmlSignatureError(str(err)) from err


def _signed_info_xml(digest_value: str, signature_method: str) -> str:
    """SignedInfo as 0.0.82 wrote it: one enveloped whole-document reference."""
    return (
        f'<ds:SignedInfo xmlns:ds="{XMLDSIG_NS}">'
        f'<ds:CanonicalizationMethod Algorithm="{C14N_EXCLUSIVE}"/>'
        f'<ds:SignatureMethod Algorithm="{signature_method}"/>'
        f'<ds:Reference URI="">'
        f"<ds:Transforms>"
        f'<ds:Transform Algorithm="{TRANSFORM_ENVELOPED}"/>'
        f'<ds:Transform Algorithm="{C14N_EXCLUSIVE}"/>'
        f"</ds:Transforms>"
        f'<ds:DigestMethod Algorithm="{DIGEST_SHA256}"/>'
        f"<ds:DigestValue>{digest_value}</ds:DigestValue>"
        f"</ds:Reference>"
        f"</ds:SignedInfo>"
    )


def _append_key_info(sig_el: et.Element, cert_pem: str | bytes) -> None:
    """Embed the certificate's base64 body in KeyInfo/X509Data."""
    cert_str = (
        cert_pem.decode("utf-8") if isinstance(cert_pem, bytes) else cert_pem
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


def sign_xml_document(
    xml_content: str,
    private_key_pem: str | bytes,
    cert_pem: str | bytes | None = None,
    passphrase: str | bytes | None = None,
    algorithm: str | None = None,
) -> str:
    """Sign an XML document with a W3C XML-DSig enveloped signature.

    Args:
        xml_content: The raw XML document string.
        private_key_pem: RSA or EC (P-256, P-384) private key in PEM.
        cert_pem: Optional X.509 certificate in PEM format to embed in KeyInfo.
        passphrase: Optional passphrase for the private key.
        algorithm: ``rsa-sha256``, ``rsa-pss-sha256``, ``ecdsa-sha256``
            or ``ecdsa-sha384``; None follows the key (RSA keys sign
            ``rsa-sha256``, as before 0.0.83).

    Returns:
        The signed XML document string.

    Raises:
        XmlSignatureError: If key loading or signing fails, or the
            algorithm does not fit the key.
    """
    private_key, chosen = _load_signing_key(
        private_key_pem, passphrase, algorithm
    )
    root = defused_et.fromstring(xml_content)
    et.register_namespace("ds", XMLDSIG_NS)

    # Digest the payload, then sign the canonical SignedInfo naming it.
    digest_val = compute_sha256_digest(canonicalize_xml(root))
    signed_info_xml = _signed_info_xml(digest_val, chosen.uri)
    canonical_signed_info = canonicalize_xml(signed_info_xml)
    try:
        sig_bytes = sign_bytes(
            private_key, chosen, canonical_signed_info.encode("utf-8")
        )
    except Exception as err:
        raise XmlSignatureError(f"Signing failed: {err}") from err

    sig_el = et.Element(f"{{{XMLDSIG_NS}}}Signature")
    sig_el.append(defused_et.fromstring(signed_info_xml))
    sig_val_el = et.SubElement(sig_el, f"{{{XMLDSIG_NS}}}SignatureValue")
    sig_val_el.text = base64.b64encode(sig_bytes).decode("ascii")
    if cert_pem is not None:
        _append_key_info(sig_el, cert_pem)

    root.append(sig_el)
    body = et.tostring(root, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{body}'


def verify_xml_signature(
    signed_xml: str | bytes,
    public_key_pem: str | bytes | None = None,
    cert_pem: str | bytes | None = None,
) -> bool:
    """Verify an enveloped XML-DSig signature; True or an exception.

    The boolean form of ``verify_signature``. With ``public_key_pem`` or
    ``cert_pem`` that key is the trust anchor. With neither, it trusts
    the certificate inside the document, which proves integrity but not
    who signed: that emits a ``DeprecationWarning``, and pain001 0.0.84
    refuses it.

    Args:
        signed_xml: The signed XML document string or bytes.
        public_key_pem: Optional public key in PEM format.
        cert_pem: Optional X.509 certificate in PEM format.

    Returns:
        True if the signature is valid.

    Raises:
        XmlSignatureError: If the signature is missing or does not verify.
    """
    _get_cryptography_modules()
    anchor = public_key_pem if public_key_pem is not None else cert_pem
    if anchor is None:
        warnings.warn(
            "verify_xml_signature() without public_key_pem or cert_pem "
            "trusts the certificate inside the document, so anyone can "
            "sign a document that passes; pain001 0.0.84 refuses this. "
            "Pass the signer's certificate, or call verify_signature(..., "
            "trust_embedded_cert=True) for an integrity-only check.",
            DeprecationWarning,
            stacklevel=2,
        )
    report = verify_signature(
        signed_xml, trust_anchor=anchor, trust_embedded_cert=anchor is None
    )
    if not report.valid:
        raise XmlSignatureError(report.reason)
    return True
