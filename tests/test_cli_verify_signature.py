# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""``pain001 verify-signature`` and ``generate --xml-sign-alg``."""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any

import click
import pytest
from click.testing import CliRunner, Result
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID

from pain001.cli import _verify_signature
from pain001.cli.cli import cli
from pain001.security.dsig import XmlSignatureError, sign_xml_document

DOC = (
    '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">'
    "<CstmrCdtTrfInitn><GrpHdr><MsgId>V-1</MsgId></GrpHdr>"
    "</CstmrCdtTrfInitn></Document>"
)
TEMPLATE_CSV = (
    Path(__file__).resolve().parent.parent
    / "pain001/templates/pain.001.001.03/template.csv"
)


def _write_key_and_cert(
    tmp_path: Path, key: Any, stem: str
) -> tuple[Path, Path]:
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, stem)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(3)
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    key_path, cert_path = tmp_path / f"{stem}.key", tmp_path / f"{stem}.crt"
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key_path, cert_path


@pytest.fixture
def signed(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A signed file, its signer's certificate and another certificate."""
    key, cert = _write_key_and_cert(
        tmp_path, ec.generate_private_key(ec.SECP256R1()), "signer"
    )
    _, other = _write_key_and_cert(
        tmp_path, ec.generate_private_key(ec.SECP256R1()), "other"
    )
    path = tmp_path / "signed.xml"
    path.write_text(
        sign_xml_document(DOC, key.read_bytes(), cert.read_bytes()),
        encoding="utf-8",
    )
    return path, cert, other


def _run(*args: str) -> Result:
    return CliRunner().invoke(cli, ["verify-signature", *args])


def test_a_trusted_certificate_verifies(
    signed: tuple[Path, Path, Path],
) -> None:
    path, cert, _ = signed
    result = _run(str(path), "--cert", str(cert))
    assert result.exit_code == 0, result.output
    expected = "valid (ecdsa-sha256, trusted certificate, signer CN=signer)"
    assert expected in result.output


def test_the_embedded_certificate_is_integrity_only(
    signed: tuple[Path, Path, Path],
) -> None:
    path, _, _ = signed
    result = _run(str(path), "--trust-embedded-cert", "--format", "json")
    assert result.exit_code == 0
    (entry,) = json.loads(result.output)
    assert entry["trust"] == "embedded" and entry["valid"] is True
    assert entry["file"] == str(path)


def test_the_wrong_certificate_exits_1(
    signed: tuple[Path, Path, Path],
) -> None:
    path, _, other = signed
    result = _run(str(path), "--cert", str(other))
    assert result.exit_code == 1
    assert ": invalid: Cryptographic signature" in result.output


@pytest.mark.parametrize("both", [True, False])
def test_exactly_one_trust_choice(
    signed: tuple[Path, Path, Path], both: bool
) -> None:
    path, cert, _ = signed
    extra = ["--cert", str(cert), "--trust-embedded-cert"] if both else []
    result = _run(str(path), *extra)
    assert result.exit_code == 2
    assert "exactly one of --cert" in result.output


def test_a_certificate_that_is_not_one_exits_2(
    signed: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    path, _, _ = signed
    junk = tmp_path / "junk.pem"
    junk.write_text("not a key", encoding="utf-8")
    result = _run(str(path), "--cert", str(junk))
    assert result.exit_code == 2
    assert "neither a PEM certificate" in result.output


def test_missing_signing_support_exits_2(
    signed: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    path, cert, _ = signed

    def missing(*args: object, **kwargs: object) -> object:
        raise XmlSignatureError("Install it via `pip install pain001[sign]`.")

    monkeypatch.setattr("pain001.security.dsig.verify_signature", missing)
    result = _run(str(path), "--cert", str(cert))
    assert result.exit_code == 2
    assert "pain001[sign]" in result.output


def test_generate_signs_with_the_chosen_algorithm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--xml-sign-alg rsa-pss-sha256`` reaches the signature."""
    monkeypatch.delenv("PAIN001_XML_SIGN_ALG", raising=False)
    key, cert = _write_key_and_cert(
        tmp_path,
        rsa.generate_private_key(public_exponent=65537, key_size=2048),
        "pss",
    )
    data = tmp_path / "payments.csv"
    data.write_text(TEMPLATE_CSV.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "-t",
            "pain.001.001.03",
            "-d",
            str(data),
            "-o",
            str(out),
            "--xml-sign-key",
            str(key),
            "--xml-sign-cert",
            str(cert),
            "--xml-sign-alg",
            "rsa-pss-sha256",
        ],
    )
    assert result.exit_code == 0, result.output
    signed_file = out / "pain.001.001.03.xml"
    assert "sha256-rsa-MGF1" in signed_file.read_text(encoding="utf-8")
    check = _run(str(signed_file), "--cert", str(cert))
    assert "valid (rsa-pss-sha256" in check.output


def test_the_option_callback_leaves_an_absent_flag_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PAIN001_XML_SIGN_ALG", raising=False)
    context = click.Context(click.Command("generate"))
    option = click.Option(["--xml-sign-alg"])
    assert _verify_signature.xml_sign_alg_option(context, option, None) is None
    assert "PAIN001_XML_SIGN_ALG" not in os.environ
