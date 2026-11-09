#!/usr/bin/env python3
# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Check pain001's XML signatures against other implementations.

For every algorithm pain001 signs with, with a throwaway key and
self-signed certificate made for the run:

* pain001 signs a bundled sample and signxml verifies it;
* signxml signs the sample and pain001 verifies it;
* when ``xmlsec1`` is on PATH, xmlsec1 verifies pain001's signature and
  pain001 verifies one xmlsec1 made.

signxml and xmlsec1 are not pain001 dependencies; the CI job installs
them (``.github/requirements/interop.txt`` and the distribution's
``xmlsec1``). Exits 1 on the first disagreement, naming it.

Usage::

    python scripts/dsig_interop.py [--sample FILE] [--require-xmlsec1]
"""

from __future__ import annotations

import argparse
import datetime
import shutil
import subprocess  # nosec B404 - runs xmlsec1 with fixed arguments
import sys
import tempfile
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID

from pain001.security.dsig import sign_xml_document, verify_signature

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = (
    ROOT
    / "pain001/corpus/data/coverage/pain.001.001.09"
    / "01-transfer-every-element.xml"
)

#: pain001 name -> (key factory, signxml SignatureMethod member).
CASES: dict[str, tuple[Any, str]] = {
    "rsa-sha256": (
        lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048),
        "RSA_SHA256",
    ),
    "rsa-pss-sha256": (
        lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048),
        "SHA256_RSA_MGF1",
    ),
    "ecdsa-sha256": (
        lambda: ec.generate_private_key(ec.SECP256R1()),
        "ECDSA_SHA256",
    ),
    "ecdsa-sha384": (
        lambda: ec.generate_private_key(ec.SECP384R1()),
        "ECDSA_SHA384",
    ),
}


def _material(key: Any) -> tuple[bytes, bytes]:
    """PEM private key and a one-day self-signed certificate for it."""
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "dsig interop")])
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
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return key_pem, cert.public_bytes(serialization.Encoding.PEM)


def _signxml_sign(
    xml: bytes, key_pem: bytes, cert_pem: bytes, method: str
) -> bytes:
    from lxml import etree
    from signxml import XMLSigner, methods
    from signxml.algorithms import (
        CanonicalizationMethod,
        DigestAlgorithm,
        SignatureMethod,
    )

    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm=getattr(SignatureMethod, method),
        digest_algorithm=DigestAlgorithm.SHA256,
        c14n_algorithm=CanonicalizationMethod.EXCLUSIVE_XML_CANONICALIZATION_1_0,
    )
    signed = signer.sign(
        etree.fromstring(xml), key=key_pem, cert=cert_pem.decode()
    )
    return bytes(
        etree.tostring(signed, xml_declaration=True, encoding="UTF-8")
    )


def _signxml_verify(signed: bytes, cert_pem: bytes) -> None:
    from signxml import XMLVerifier

    XMLVerifier().verify(
        signed, x509_cert=cert_pem.decode(), ignore_ambiguous_key_info=True
    )


def _xmlsec1(*args: str) -> None:
    done = subprocess.run(  # nosec B603 - fixed program, local files
        ["xmlsec1", *args], capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip() or done.stdout.strip())


def _check_xmlsec1(
    name: str, ours: bytes, theirs: bytes, work: Path, cert_pem: bytes
) -> None:
    """xmlsec1 verifies ours, and pain001 verifies one xmlsec1 signs.

    ``--insecure`` skips xmlsec1's certificate-chain check for the
    self-signed test certificate; the signature itself is still checked.
    """
    (work / "ours.xml").write_bytes(ours)
    _xmlsec1(
        "--verify",
        "--insecure",
        "--pubkey-cert-pem",
        str(work / "cert.pem"),
        str(work / "ours.xml"),
    )
    print(f"  {name}: pain001 signs, xmlsec1 verifies")
    (work / "theirs.xml").write_bytes(theirs)
    _xmlsec1(
        "--sign",
        "--privkey-pem",
        f"{work / 'key.pem'},{work / 'cert.pem'}",
        "--output",
        str(work / "resigned.xml"),
        str(work / "theirs.xml"),
    )
    report = verify_signature(
        (work / "resigned.xml").read_bytes(), trust_anchor=cert_pem
    )
    if not report.valid:
        raise RuntimeError(f"pain001 rejected xmlsec1's {name}: {report}")
    print(f"  {name}: xmlsec1 signs, pain001 verifies")


def _check_case(name: str, sample: bytes, work: Path, xmlsec1: bool) -> None:
    factory, method = CASES[name]
    key_pem, cert_pem = _material(factory())
    (work / "key.pem").write_bytes(key_pem)
    (work / "cert.pem").write_bytes(cert_pem)

    ours = sign_xml_document(
        sample.decode("utf-8"), key_pem, cert_pem, algorithm=name
    ).encode("utf-8")
    _signxml_verify(ours, cert_pem)
    print(f"  {name}: pain001 signs, signxml verifies")

    theirs = _signxml_sign(sample, key_pem, cert_pem, method)
    report = verify_signature(theirs, trust_anchor=cert_pem)
    if not report.valid or report.algorithm != name:
        raise RuntimeError(f"pain001 rejected signxml's {name}: {report}")
    print(f"  {name}: signxml signs, pain001 verifies")

    if xmlsec1:
        _check_xmlsec1(name, ours, theirs, work, cert_pem)


def main(argv: list[str] | None = None) -> int:
    """Run every case; 0 when all agree, 1 on the first disagreement."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sample", type=Path, default=SAMPLE)
    parser.add_argument("--require-xmlsec1", action="store_true")
    args = parser.parse_args(argv)
    # Every case runs against xmlsec1 when it is installed: a case it
    # cannot check is a failure to look at, never a silent skip.
    xmlsec1 = shutil.which("xmlsec1") is not None
    if args.require_xmlsec1 and not xmlsec1:
        print("xmlsec1 is not on PATH", file=sys.stderr)
        return 1
    if not xmlsec1:
        print("xmlsec1 not found: checking against signxml only")
    sample = args.sample.read_bytes()
    with tempfile.TemporaryDirectory(prefix="pain001-dsig-") as name:
        for case in CASES:
            try:
                _check_case(case, sample, Path(name), xmlsec1)
            except Exception as exc:  # noqa: BLE001 - report and stop
                print(f"FAIL {case}: {exc}", file=sys.stderr)
                return 1
    print("every case agrees")
    return 0


if __name__ == "__main__":
    sys.exit(main())
