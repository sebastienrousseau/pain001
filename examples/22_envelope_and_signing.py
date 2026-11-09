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

"""Wrap a pain.001 in a Business Application Header, then sign it.

1. Generate a validated pain.001.001.03 document in memory.
2. Envelop it in a head.001.001.03 AppHdr inside a head.003 BizData
   envelope, unpack it again, and check the header and document survive.
3. Sign the envelope with an enveloped XML-DSig (RSA-SHA256), verify it,
   then change one amount and show verification refuses the document.
4. Sign with an ECDSA P-256 key and an embedded certificate, check it
   with ``verify_signature`` against that certificate as the trust
   anchor (a ``SignatureReport``), and with ``pain001 verify-signature``.

Signing needs the ``cryptography`` package. The key is generated in
memory for this run and never written to disk.

Run from the repository root::

    python examples/22_envelope_and_signing.py
"""

from __future__ import annotations

import datetime
import re
import tempfile
import xml.etree.ElementTree as et  # nosec B405
from pathlib import Path

from click.testing import CliRunner

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    from cryptography.x509.oid import NameOID
except ImportError as error:
    raise SystemExit(
        "cryptography not installed; run `pip install pain001[sign]`."
    ) from error

from pain001 import (
    BusinessApplicationHeader,
    SignatureReport,
    XmlSignatureError,
    envelop_iso20022_message,
    generate_xml_string,
    sign_xml_document,
    unpack_iso20022_message,
    verify_signature,
    verify_xml_signature,
)
from pain001.cli.cli import cli
from pain001.constants import TEMPLATES_DIR
from pain001.csv.load_csv_data import load_csv_data

MESSAGE_TYPE = "pain.001.001.03"
DATA_FILE = Path(__file__).resolve().parent / "data" / "payments.csv"
AMOUNT = re.compile(r'(<(?:\w+:)?InstdAmt Ccy="EUR">)([^<]+)(<)')


def canonical(xml: str) -> str:
    """Return the C14N form of an XML string, ignoring its declaration."""
    body = xml.split("?>", 1)[1] if xml.startswith("<?xml") else xml
    return et.canonicalize(body.strip(), strip_text=True)


def generate_document() -> str:
    """Render the sample payments to a validated pain.001 string."""
    template_dir = TEMPLATES_DIR / MESSAGE_TYPE
    return generate_xml_string(
        load_csv_data(str(DATA_FILE)),
        MESSAGE_TYPE,
        str(template_dir / "template.xml"),
        str(template_dir / f"{MESSAGE_TYPE}.xsd"),
    )


def envelope_round_trip(document: str) -> str:
    """Envelop the document, unpack it, and return the envelope."""
    header = BusinessApplicationHeader(
        from_bic="BANKDEFFXXX",
        to_bic="ZFUMDE50XXX",
        biz_msg_idr="MSG-EXAMPLE-0001",
        cre_dt="2023-03-10T15:30:47Z",
    )
    envelope = envelop_iso20022_message(document, header)
    assert "<head:AppHdr" in envelope

    unpacked, inner = unpack_iso20022_message(envelope)
    assert unpacked is not None
    assert unpacked.from_bic == "BANKDEFFXXX"
    assert unpacked.to_bic == "ZFUMDE50XXX"
    assert unpacked.biz_msg_idr == "MSG-EXAMPLE-0001"
    assert unpacked.msg_def_idr == MESSAGE_TYPE
    assert unpacked.cre_dt == "2023-03-10T15:30:47Z"
    assert canonical(inner) == canonical(document)
    print(
        f"Envelope: {unpacked.from_bic} -> {unpacked.to_bic}, "
        f"{unpacked.msg_def_idr}, {len(envelope)} chars"
    )
    return envelope


def throwaway_key_pair() -> tuple[bytes, bytes]:
    """Return a fresh RSA private key and its public key, both as PEM."""
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def tamper_first_amount(signed: str) -> str:
    """Return the signed XML with its first amount raised by one."""
    match = AMOUNT.search(signed)
    assert match is not None
    raised = f"{float(match.group(2)) + 1:.2f}"
    print(f"Tampering: amount {match.group(2)} -> {raised}")
    return AMOUNT.sub(rf"\g<1>{raised}\g<3>", signed, count=1)


def sign_and_verify(envelope: str) -> None:
    """Sign the envelope, verify it, and show a tampered copy fails."""
    private_pem, public_pem = throwaway_key_pair()
    signed = sign_xml_document(envelope, private_pem)
    assert "SignatureValue" in signed
    assert verify_xml_signature(signed, public_key_pem=public_pem)
    print("Signature: verified with the matching public key")

    tampered = tamper_first_amount(signed)
    try:
        verify_xml_signature(tampered, public_key_pem=public_pem)
    except XmlSignatureError as err:
        print(f"Tampered copy rejected: {str(err).split(':')[0]}")
    else:
        raise AssertionError("a tampered document must not verify")


def ecdsa_with_certificate() -> tuple[bytes, bytes]:
    """A fresh P-256 key and a one-day self-signed certificate, as PEM."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Example Ltd")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return key_pem, cert.public_bytes(serialization.Encoding.PEM)


def ecdsa_and_trust_anchor(envelope: str) -> None:
    """Sign with ECDSA, verify against the certificate, then from the CLI."""
    key_pem, cert_pem = ecdsa_with_certificate()
    signed = sign_xml_document(envelope, key_pem, cert_pem)
    report: SignatureReport = verify_signature(signed, trust_anchor=cert_pem)
    assert report.valid and report.algorithm == "ecdsa-sha256"
    print(f"ECDSA: {report.algorithm}, signer {report.signer}, {report.trust}")
    with tempfile.TemporaryDirectory(prefix="pain001-example-22-") as work:
        signed_file, cert_file = (
            Path(work, "signed.xml"),
            Path(work, "cert.pem"),
        )
        signed_file.write_text(signed, encoding="utf-8")
        cert_file.write_bytes(cert_pem)
        result = CliRunner().invoke(
            cli,
            ["verify-signature", str(signed_file), "--cert", str(cert_file)],
        )
    assert result.exit_code == 0, result.output
    print("pain001 verify-signature:", result.output.split(": ", 1)[1].strip())


def main() -> None:
    """Generate, envelop, unpack, sign, verify, and tamper."""
    document = generate_document()
    envelope = envelope_round_trip(document)
    sign_and_verify(envelope)
    ecdsa_and_trust_anchor(envelope)
    print("Envelope and signing example completed.")


if __name__ == "__main__":
    main()
