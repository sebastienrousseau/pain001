# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""SSH identities: key types, refusals and OpenSSH certificates."""

from __future__ import annotations

import base64
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

paramiko = pytest.importorskip("paramiko")

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import (  # noqa: E402
    dsa,
    ed25519,
    rsa,
)

from pain001.transport import identity  # noqa: E402
from pain001.transport import sftp as upload  # noqa: E402

PASSPHRASE = b"test-passphrase"


def _write_openssh_key(path: Path, private_key: object) -> str:
    """Write ``private_key`` in OpenSSH format, passphrase-protected."""
    path.write_bytes(
        private_key.private_bytes(  # type: ignore[attr-defined]
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.BestAvailableEncryption(PASSPHRASE),
        )
    )
    return str(path)


def _write_declared_type(path: Path, key_type: str) -> str:
    """Write an OpenSSH private-key file declaring ``key_type``.

    Enough of the format for the type to be read, as a FIDO or
    post-quantum key would be; no real key material is needed.
    """
    public = paramiko.Message()
    public.add_string(key_type)
    public.add_string(b"\x00" * 32)
    body = paramiko.Message()
    for field in (b"none", b"none", b""):
        body.add_string(field)
    body.add_int(1)
    body.add_string(public.asbytes())
    body.add_string(b"")
    blob = identity._OPENSSH_MAGIC + body.asbytes()
    text = base64.b64encode(blob).decode()
    lines = [text[i : i + 70] for i in range(0, len(text), 70)]
    path.write_text(
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        + "\n".join(lines)
        + "\n-----END OPENSSH PRIVATE KEY-----\n",
        encoding="ascii",
    )
    return str(path)


def _certificate(
    path: Path,
    user_key: ed25519.Ed25519PrivateKey,
    *,
    after: int = -60,
    before: int = 3600,
) -> str:
    """Write a user certificate for ``user_key``, valid relative to now."""
    authority = ed25519.Ed25519PrivateKey.generate()
    now = int(time.time())
    certificate = (
        serialization.SSHCertificateBuilder()
        .public_key(user_key.public_key())
        .serial(1)
        .type(serialization.SSHCertificateType.USER)
        .key_id(b"ops")
        .valid_principals([b"ops"])
        .valid_after(now + after)
        .valid_before(now + before)
        .sign(authority)
    )
    path.write_bytes(certificate.public_bytes())
    return str(path)


def test_key_type_reads_openssh_and_pem_dsa(tmp_path):
    """The declared type is read without the passphrase."""
    ed = _write_openssh_key(
        tmp_path / "ed", ed25519.Ed25519PrivateKey.generate()
    )
    assert identity.key_type(ed) == "ssh-ed25519"
    pem_dsa = tmp_path / "dsa"
    pem_dsa.write_bytes(
        dsa.generate_private_key(1024).private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    assert identity.key_type(str(pem_dsa)) == "ssh-dss"


@pytest.mark.parametrize(
    "content",
    [
        "-----BEGIN RSA PRIVATE KEY-----\nAAAA\n-----END RSA PRIVATE KEY-----\n",
        "-----BEGIN OPENSSH PRIVATE KEY-----\n!!!\n-----END OPENSSH PRIVATE KEY-----\n",
        "-----BEGIN OPENSSH PRIVATE KEY-----\nAAAA\n-----END OPENSSH PRIVATE KEY-----\n",
    ],
    ids=["pem-rsa", "bad-base64", "no-magic"],
)
def test_key_type_unknown(tmp_path, content):
    """Files that do not declare a type report None."""
    path = tmp_path / "key"
    path.write_text(content, encoding="ascii")
    assert identity.key_type(str(path)) is None


@pytest.mark.parametrize(
    ("key_type", "message"),
    [
        ("ssh-dss", "is a DSA key. OpenSSH 10.0 removed DSA"),
        ("sk-ssh-ed25519@openssh.com", "FIDO security key"),
        ("sk-ecdsa-sha2-nistp256@openssh.com", "FIDO security key"),
        ("ssh-mldsa44-ed25519@openssh.com", "which paramiko"),
    ],
)
def test_unsupported_key_types_are_refused_by_name(
    tmp_path, key_type, message
):
    """DSA, FIDO and unknown types are named, not misreported."""
    path = _write_declared_type(tmp_path / "key", key_type)
    with pytest.raises(ValueError, match=message):
        identity.load_identity(path, "anything")


def test_unknown_type_message_names_the_type(tmp_path):
    """The generic refusal says which type it saw."""
    kind = "ssh-mldsa44-ed25519@openssh.com"
    path = _write_declared_type(tmp_path / "key", kind)
    with pytest.raises(ValueError, match=kind):
        identity.load_identity(path, None)


def test_pem_dsa_key_is_refused(tmp_path):
    """A traditional PEM DSA key is refused before loading."""
    path = tmp_path / "id_dsa"
    path.write_bytes(
        dsa.generate_private_key(1024).private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    with pytest.raises(ValueError, match="DSA key"):
        identity.load_identity(str(path))


def test_certificate_is_attached(tmp_path):
    """A matching, current certificate is presented with the key."""
    user = ed25519.Ed25519PrivateKey.generate()
    key_file = _write_openssh_key(tmp_path / "id_ed25519", user)
    cert = _certificate(tmp_path / "id_ed25519-cert.pub", user)
    key = identity.load_identity(key_file, PASSPHRASE.decode(), cert)
    assert key is not None
    assert key.public_blob.key_type == "ssh-ed25519-cert-v01@openssh.com"


def test_certificate_for_another_key_is_refused(tmp_path):
    """paramiko accepts it (same type); the check catches it first."""
    key_file = _write_openssh_key(
        tmp_path / "id_ed25519", ed25519.Ed25519PrivateKey.generate()
    )
    other = ed25519.Ed25519PrivateKey.generate()
    cert = _certificate(tmp_path / "other-cert.pub", other)
    with pytest.raises(ValueError, match="issued for a different key"):
        identity.load_identity(key_file, PASSPHRASE.decode(), cert)


@pytest.mark.parametrize(
    ("after", "before", "message"),
    [(-7200, -3600, "expired at"), (3600, 7200, "is not valid until")],
)
def test_certificate_validity_window(tmp_path, after, before, message):
    """Short-lived certificates outside their window are named."""
    user = ed25519.Ed25519PrivateKey.generate()
    key_file = _write_openssh_key(tmp_path / "id_ed25519", user)
    cert = _certificate(tmp_path / "c", user, after=after, before=before)
    with pytest.raises(ValueError, match=message):
        identity.load_identity(key_file, PASSPHRASE.decode(), cert)


def test_public_key_is_not_a_certificate(tmp_path):
    """A plain .pub file is refused as a certificate."""
    user = ed25519.Ed25519PrivateKey.generate()
    key_file = _write_openssh_key(tmp_path / "id_ed25519", user)
    public = tmp_path / "id_ed25519.pub"
    public.write_bytes(
        user.public_key().public_bytes(
            serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
        )
    )
    with pytest.raises(ValueError, match="is a public key"):
        identity.load_identity(key_file, PASSPHRASE.decode(), str(public))


def test_garbage_is_not_a_certificate(tmp_path):
    """An unreadable certificate file is refused."""
    user = ed25519.Ed25519PrivateKey.generate()
    key_file = _write_openssh_key(tmp_path / "id_ed25519", user)
    junk = tmp_path / "junk-cert.pub"
    junk.write_text("not a certificate\n", encoding="ascii")
    with pytest.raises(ValueError, match="not an OpenSSH certificate"):
        identity.load_identity(key_file, PASSPHRASE.decode(), str(junk))


def test_certificate_without_key_is_refused(tmp_path):
    """A certificate alone cannot authenticate."""
    with pytest.raises(ValueError, match="needs the private key"):
        identity.load_identity(None, None, str(tmp_path / "c"))


def test_no_identity_loads_nothing():
    """Without an identity file the agent and default keys are used."""
    assert identity.load_identity(None) is None


def test_rsa_key_still_loads(tmp_path):
    """A traditional PEM RSA key (no declared type) loads as before."""
    path = tmp_path / "id_rsa"
    path.write_bytes(
        rsa.generate_private_key(65537, 2048).private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.BestAvailableEncryption(PASSPHRASE),
        )
    )
    key = identity.load_identity(str(path), PASSPHRASE.decode())
    assert key is not None and key.get_name() == "ssh-rsa"


@pytest.fixture
def client(tmp_path):
    """An SSH client whose connection is observed, not made."""
    local = tmp_path / "payments.xml"
    local.write_bytes(b"<Document/>")
    ssh, sftp = MagicMock(), MagicMock()
    ssh.__enter__.return_value = ssh
    ssh.open_sftp.return_value = sftp
    sftp.__enter__.return_value = sftp
    sftp.lstat.side_effect = FileNotFoundError(2, "absent")
    with (
        patch.object(paramiko, "SSHClient", return_value=ssh),
        patch.object(
            upload, "_load_known_hosts", return_value=paramiko.HostKeys()
        ),
    ):
        yield local, ssh


@pytest.mark.parametrize(
    ("use_agent", "with_key", "expected"),
    [
        (False, True, False),
        (True, True, True),
        (False, False, True),
    ],
    ids=["key-only", "key-and-agent", "unattended"],
)
def test_use_agent_keeps_the_agent_with_explicit_credentials(
    client, tmp_path, use_agent, with_key, expected
):
    """--use-agent offers agent keys even with a key file or password."""
    local, ssh = client
    key_file = (
        _write_openssh_key(
            tmp_path / "id", ed25519.Ed25519PrivateKey.generate()
        )
        if with_key
        else None
    )
    upload.upload_sftp(
        str(local),
        "sftp://ops@bank.example/inbox/",
        identity_file=key_file,
        passphrase=PASSPHRASE.decode() if with_key else None,
        use_agent=use_agent,
    )
    assert ssh.connect.call_args.kwargs["allow_agent"] is expected
    assert ssh.connect.call_args.kwargs["look_for_keys"] is (not with_key)


def test_certificate_reaches_connect(client, tmp_path):
    """The key passed to connect carries the certificate."""
    local, ssh = client
    user = ed25519.Ed25519PrivateKey.generate()
    key_file = _write_openssh_key(tmp_path / "id_ed25519", user)
    cert = _certificate(tmp_path / "id_ed25519-cert.pub", user)
    upload.upload_sftp(
        str(local),
        "sftp://ops@bank.example/inbox/",
        identity_file=key_file,
        passphrase=PASSPHRASE.decode(),
        certificate=cert,
    )
    pkey = ssh.connect.call_args.kwargs["pkey"]
    assert pkey.public_blob.key_type.endswith("-cert-v01@openssh.com")
