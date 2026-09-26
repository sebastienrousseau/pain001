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

"""Integration tests for BAH enveloping and XML-DSig signing in core and CLI."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pain001.cli.cli import cli
from pain001.core.core import process_files, process_files_streaming
from pain001.security.dsig import verify_xml_signature
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.xml.envelope import (
    BusinessApplicationHeader,
    unpack_iso20022_message,
)


@pytest.fixture
def rsa_test_keys(tmp_path: Path) -> tuple[str, str, str]:
    """Generate temporary PEM files for private key, public key, and certificate."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "test")]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(priv.public_key())
        .serial_number(100)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .sign(priv, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)

    key_file = tmp_path / "test_key.pem"
    pub_file = tmp_path / "test_pub.pem"
    cert_file = tmp_path / "test_cert.pem"

    key_file.write_bytes(key_pem)
    pub_file.write_bytes(pub_pem)
    cert_file.write_bytes(cert_pem)

    return str(key_file), str(pub_file), str(cert_file)


@pytest.fixture
def sample_csv_data(tmp_path: Path) -> str:
    """Create a minimal valid CSV input file by reading bundled template.csv."""
    bundled_csv = (
        Path(__file__).parent.parent
        / "pain001"
        / "templates"
        / "pain.001.001.03"
        / "template.csv"
    )
    csv_file = tmp_path / "payments.csv"
    csv_file.write_text(
        bundled_csv.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return str(csv_file)


def test_process_files_envelop_bah(
    sample_csv_data: str, tmp_path: Path
) -> None:
    """Verify process_files produces valid BAH envelope when envelop_bah=True."""
    tmpl, schema = DEFAULT_TEMPLATE_REGISTRY.resolve_paths("pain.001.001.03")
    out_file = tmp_path / "enveloped.xml"

    header = BusinessApplicationHeader(
        from_bic="DEUTDEDDXXX",
        to_bic="BNPAFRPPXXX",
        biz_msg_idr="BAH-TEST-001",
    )
    res = process_files(
        "pain.001.001.03",
        tmpl,
        schema,
        sample_csv_data,
        output_path=str(out_file),
        envelop_bah=True,
        bah_header=header,
    )
    assert os.path.exists(res)
    content = out_file.read_text(encoding="utf-8")

    assert "BizData" in content
    assert "DEUTDEDDXXX" in content
    assert "BNPAFRPPXXX" in content
    assert "BAH-TEST-001" in content

    unpacked_hdr, unpacked_doc = unpack_iso20022_message(content)
    assert unpacked_hdr is not None
    assert unpacked_hdr.from_bic == "DEUTDEDDXXX"
    assert unpacked_hdr.biz_msg_idr == "BAH-TEST-001"
    assert "CstmrCdtTrfInitn" in unpacked_doc


def test_process_files_xml_sign(
    sample_csv_data: str, rsa_test_keys: tuple[str, str, str], tmp_path: Path
) -> None:
    """Verify process_files signs output XML using XML-DSig."""
    tmpl, schema = DEFAULT_TEMPLATE_REGISTRY.resolve_paths("pain.001.001.03")
    key_file, pub_file, cert_file = rsa_test_keys
    out_file = tmp_path / "signed.xml"

    key_pem = Path(key_file).read_bytes()
    cert_pem = Path(cert_file).read_bytes()

    res = process_files(
        "pain.001.001.03",
        tmpl,
        schema,
        sample_csv_data,
        output_path=str(out_file),
        xml_sign_key=key_pem,
        xml_sign_cert=cert_pem,
    )
    assert os.path.exists(res)
    content = out_file.read_text(encoding="utf-8")
    assert "Signature" in content
    assert verify_xml_signature(content) is True


def test_process_files_streaming_bah_and_sign(
    sample_csv_data: str, rsa_test_keys: tuple[str, str, str], tmp_path: Path
) -> None:
    """Verify streaming mode envelopes and signs each chunk."""
    tmpl, schema = DEFAULT_TEMPLATE_REGISTRY.resolve_paths("pain.001.001.03")
    key_file, _, cert_file = rsa_test_keys
    key_pem = Path(key_file).read_bytes()
    cert_pem = Path(cert_file).read_bytes()

    chunk_files = process_files_streaming(
        "pain.001.001.03",
        tmpl,
        schema,
        sample_csv_data,
        chunk_size=10,
        output_dir=str(tmp_path),
        envelop_bah=True,
        xml_sign_key=key_pem,
        xml_sign_cert=cert_pem,
    )
    assert len(chunk_files) == 1
    chunk_content = Path(chunk_files[0]).read_text(encoding="utf-8")
    assert "BizData" in chunk_content
    assert "Signature" in chunk_content
    assert verify_xml_signature(chunk_content) is True


def test_cli_generate_with_bah_and_dsig(
    sample_csv_data: str, rsa_test_keys: tuple[str, str, str], tmp_path: Path
) -> None:
    """Verify CLI generate command with --envelop-bah and --xml-sign-key."""
    key_file, _, cert_file = rsa_test_keys
    out_dir = tmp_path / "cli_out"
    out_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "generate",
            "-t",
            "pain.001.001.03",
            "-d",
            sample_csv_data,
            "-o",
            str(out_dir),
            "--envelop-bah",
            "--bah-sender",
            "TESTBIC1XXX",
            "--bah-receiver",
            "TESTBIC2XXX",
            "--bah-msg-id",
            "CLI-BAH-001",
            "--xml-sign-key",
            key_file,
            "--xml-sign-cert",
            cert_file,
        ],
    )
    assert result.exit_code == 0, result.output
    generated = out_dir / "pain.001.001.03.xml"
    assert generated.exists()
    content = generated.read_text(encoding="utf-8")

    assert "BizData" in content
    assert "TESTBIC1XXX" in content
    assert "CLI-BAH-001" in content
    assert "Signature" in content
    assert verify_xml_signature(content) is True


def test_process_files_envelop_bah_default(
    sample_csv_data: str, tmp_path: Path
) -> None:
    """Verify process_files with envelop_bah=True and default header."""
    tmpl, schema = DEFAULT_TEMPLATE_REGISTRY.resolve_paths("pain.001.001.03")
    out_file = tmp_path / "enveloped_default.xml"
    res = process_files(
        "pain.001.001.03",
        tmpl,
        schema,
        sample_csv_data,
        output_path=str(out_file),
        envelop_bah=True,
    )
    assert os.path.exists(res)
    content = out_file.read_text(encoding="utf-8")
    assert "BizData" in content


def test_cli_generate_with_passphrase_env(
    sample_csv_data: str,
    rsa_test_keys: tuple[str, str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify CLI generate command with encrypted key and passphrase env var."""
    key_file, pub_file, _ = rsa_test_keys
    priv_bytes = Path(key_file).read_bytes()
    priv = serialization.load_pem_private_key(priv_bytes, password=None)
    enc_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(
            b"testpass123"
        ),
    )
    enc_key_file = tmp_path / "enc_key.pem"
    enc_key_file.write_bytes(enc_pem)

    monkeypatch.setenv("TEST_KEY_PW", "testpass123")
    out_dir = tmp_path / "cli_pw_out"
    out_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "generate",
            "-t",
            "pain.001.001.03",
            "-d",
            sample_csv_data,
            "-o",
            str(out_dir),
            "--xml-sign-key",
            str(enc_key_file),
            "--xml-sign-passphrase-env",
            "TEST_KEY_PW",
        ],
    )
    assert result.exit_code == 0, result.output
    generated = out_dir / "pain.001.001.03.xml"
    assert generated.exists()
    content = generated.read_text(encoding="utf-8")
    assert "Signature" in content
    pub_pem = Path(pub_file).read_bytes()
    assert verify_xml_signature(content, public_key_pem=pub_pem) is True
