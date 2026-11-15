# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""SSH identity contract: exact refusals, file sniffing and time bounds.

Every refusal here is printed to an operator before any connection is
opened, so the wording and the key's filename in it are pinned.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dsa, ed25519, rsa

# paramiko is the optional "upload" extra; skip, not fail, without it.
paramiko = pytest.importorskip("paramiko")
identity = pytest.importorskip("pain001.transport.identity")

PASSPHRASE = b"test-passphrase"


@pytest.fixture
def tokyo(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Run with a local time zone nine hours ahead of UTC."""
    monkeypatch.setenv("TZ", "Asia/Tokyo")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def _openssh_text(key: ed25519.Ed25519PrivateKey) -> str:
    """An unencrypted OpenSSH-format private key, as ssh-keygen writes."""
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    ).decode("ascii")


def test_a_corrupted_openssh_body_declares_no_type(tmp_path: Path) -> None:
    """A stray non-base64 character makes the key unreadable, not guessed."""
    text = _openssh_text(ed25519.Ed25519PrivateKey.generate())
    lines = text.splitlines()
    lines[1] = lines[1][:10] + "!" + lines[1][10:]
    path = tmp_path / "id_ed25519"
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    assert identity.key_type(str(path)) is None
    intact = tmp_path / "intact"
    intact.write_text(text, encoding="ascii")
    assert identity.key_type(str(intact)) == "ssh-ed25519"


def test_key_type_of_a_binary_file_is_unknown(tmp_path: Path) -> None:
    """A DER or other binary key is read without a decoding error."""
    path = tmp_path / "id_der"
    path.write_bytes(b"\x30\x82\xff\xfe\x80 not text at all \xc3")
    assert identity.key_type(str(path)) is None


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        (
            "sk-ssh-ed25519@openssh.com",
            "id_sk is a FIDO security key (sk-ssh-ed25519@openssh.com), "
            "which paramiko cannot sign with. Hardware keys that ssh-agent "
            "offers as RSA, ECDSA or Ed25519 keys (PIV smartcards, for "
            "example) work with --use-agent.",
        ),
        (
            "ssh-mldsa65",
            "id_sk is a ssh-mldsa65 key, which paramiko "
            f"{paramiko.__version__} cannot use; use an RSA, ECDSA or "
            "Ed25519 key.",
        ),
    ],
)
def test_unsupported_key_refusals_are_worded_exactly(
    kind: str, message: str
) -> None:
    """FIDO and unknown key types each say what to use instead."""
    with pytest.raises(ValueError) as error:
        identity._refuse_unsupported("id_sk", kind)
    assert str(error.value) == message


def test_encrypted_pem_sniffing_survives_binary_bytes(tmp_path: Path) -> None:
    """Undecodable bytes are replaced, so the marker is still found."""
    path = tmp_path / "key"
    path.write_bytes(b"\xff\xfe\x80\nProc-Type: 4,ENCRYPTED\n")
    assert identity._is_encrypted_pem(str(path)) is True


def test_encrypted_pem_sniffing_reads_only_the_head(tmp_path: Path) -> None:
    """Only the first 4096 characters are inspected."""
    marker = "Proc-Type: 4,ENCRYPTED"
    inside = tmp_path / "inside"
    inside.write_text("a" * (4096 - len(marker)) + marker, encoding="utf-8")
    assert identity._is_encrypted_pem(str(inside)) is True
    beyond = tmp_path / "beyond"
    beyond.write_text("a" * (4097 - len(marker)) + marker, encoding="utf-8")
    assert identity._is_encrypted_pem(str(beyond)) is False


def test_encrypted_pkcs8_is_recognised(tmp_path: Path) -> None:
    """A ``BEGIN ENCRYPTED PRIVATE KEY`` file is an encrypted PEM key."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    path = tmp_path / "pkcs8"
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(PASSPHRASE),
        )
    )
    assert identity._is_encrypted_pem(str(path)) is True


@pytest.mark.usefixtures("tokyo")
def test_certificate_times_are_utc_iso_8601() -> None:
    """Timestamps print in UTC whatever the local zone is."""
    assert identity._utc(0) == "1970-01-01T00:00:00Z"
    assert identity._utc(1_700_000_000) == "2023-11-14T22:13:20Z"


def _key_file(path: Path, key: ed25519.Ed25519PrivateKey) -> str:
    """Write ``key`` as an unencrypted OpenSSH private-key file."""
    path.write_text(_openssh_text(key), encoding="ascii")
    return str(path)


def _cert_file(
    path: Path, key: ed25519.Ed25519PrivateKey, after: int, before: int
) -> str:
    """Write a user certificate for ``key`` valid from after to before."""
    certificate = (
        serialization.SSHCertificateBuilder()
        .public_key(key.public_key())
        .serial(1)
        .type(serialization.SSHCertificateType.USER)
        .key_id(b"ops")
        .valid_principals([b"ops"])
        .valid_after(after)
        .valid_before(before)
        .sign(ed25519.Ed25519PrivateKey.generate())
    )
    path.write_bytes(certificate.public_bytes())
    return str(path)


def test_certificate_window_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Valid from ``valid_after`` itself; expired at ``valid_before``."""
    user = ed25519.Ed25519PrivateKey.generate()
    key = paramiko.Ed25519Key.from_private_key_file(
        _key_file(tmp_path / "id_ed25519", user)
    )
    cert = _cert_file(tmp_path / "id-cert.pub", user, 1_000, 2_000)
    monkeypatch.setattr(identity.time, "time", lambda: 1_000)
    identity.attach_certificate(key, cert, "id_ed25519")
    monkeypatch.setattr(identity.time, "time", lambda: 2_000)
    with pytest.raises(ValueError) as error:
        identity.attach_certificate(key, cert, "id_ed25519")
    assert str(error.value) == (
        "Certificate id-cert.pub expired at 1970-01-01T00:33:20Z."
    )


def test_certificate_refusals_name_both_files(tmp_path: Path) -> None:
    """A certificate for another key names the certificate and the key."""
    user = ed25519.Ed25519PrivateKey.generate()
    key_path = _key_file(tmp_path / "id_ed25519", user)
    other = _cert_file(
        tmp_path / "other-cert.pub",
        ed25519.Ed25519PrivateKey.generate(),
        0,
        2**40,
    )
    with pytest.raises(ValueError) as error:
        identity.load_identity(key_path, certificate=other)
    assert str(error.value) == (
        "Certificate other-cert.pub was issued for a different key than "
        "id_ed25519."
    )


def test_a_certificate_alone_is_refused_verbatim() -> None:
    """A certificate needs its private key; the message says which flag."""
    with pytest.raises(ValueError) as error:
        identity.load_identity(None, certificate="/keys/id-cert.pub")
    assert str(error.value) == (
        "A certificate needs the private key it was issued for "
        "(--identity-file)."
    )


def test_a_dsa_key_is_refused_by_its_filename(tmp_path: Path) -> None:
    """The refusal starts with the key file's own name."""
    path = tmp_path / "id_dsa"
    path.write_bytes(
        dsa.generate_private_key(1024).private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    with pytest.raises(ValueError) as error:
        identity.load_identity(str(path))
    assert str(error.value) == (
        "id_dsa is a DSA key. OpenSSH 10.0 removed DSA and paramiko "
        f"{paramiko.__version__} cannot use it; use an Ed25519 key."
    )


def test_an_encrypted_key_without_passphrase_names_the_file(
    tmp_path: Path,
) -> None:
    """The passphrase prompt names the key file, not its full path."""
    path = tmp_path / "id_work"
    path.write_bytes(
        ed25519.Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.BestAvailableEncryption(PASSPHRASE),
        )
    )
    with pytest.raises(ValueError) as error:
        identity.load_identity(str(path))
    assert str(error.value) == (
        "Private key id_work is encrypted; supply its passphrase."
    )


def test_a_valid_key_loads_with_its_certificate(tmp_path: Path) -> None:
    """A matching, current certificate is attached to the loaded key."""
    user = ed25519.Ed25519PrivateKey.generate()
    key_path = _key_file(tmp_path / "id_ed25519", user)
    now = int(time.time())
    cert = _cert_file(tmp_path / "id-cert.pub", user, now - 60, now + 60)
    key = identity.load_identity(key_path, certificate=cert)
    assert key is not None
    assert key.public_blob is not None
