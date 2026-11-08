# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Load an SSH client identity: private key, passphrase and certificate.

Everything here runs before a connection opens, so a key that cannot be
used is reported by name instead of as an opaque authentication failure
from the server.
"""

from __future__ import annotations

import binascii
import time
from datetime import UTC, datetime
from pathlib import Path

import paramiko
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization

_KEY_TYPES = (paramiko.RSAKey, paramiko.ECDSAKey, paramiko.Ed25519Key)
_SUPPORTED_KEY_TYPES = frozenset(
    {
        "ssh-rsa",
        "ssh-ed25519",
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
    }
)
# How paramiko reports a wrong passphrase: PEM keys, then OpenSSH keys.
_WRONG_PASSPHRASE = ("Bad password", "checkints do not match")
_OPENSSH_MAGIC = b"openssh-key-v1\x00"


def _openssh_key_type(text: str) -> str | None:
    """Return the key type an OpenSSH-format private key declares.

    The public half of the key, including its type, is stored
    unencrypted, so this works without the passphrase.

    Args:
        text: The private-key file's contents.

    Returns:
        The key type (for example ``ssh-ed25519``), or None if the file
        is not a readable OpenSSH private key.
    """
    body = "".join(
        line for line in text.splitlines() if not line.startswith("-----")
    )
    try:
        blob = binascii.a2b_base64(body, strict_mode=True)
    except binascii.Error:
        return None
    if not blob.startswith(_OPENSSH_MAGIC):
        return None
    message = paramiko.Message(blob[len(_OPENSSH_MAGIC) :])
    for _ in range(3):  # cipher name, KDF name, KDF options
        message.get_binary()
    message.get_int()  # number of keys
    key_type = paramiko.Message(message.get_binary()).get_text()
    return key_type or None


def key_type(path: str) -> str | None:
    """Return the SSH key type of a private-key file, when it says one.

    Args:
        path: Private-key filename.

    Returns:
        ``ssh-dss`` for a PEM DSA key, the declared type of an
        OpenSSH-format key, or None when the file does not say.
    """
    text = Path(path).read_text(encoding="ascii", errors="replace")
    if "BEGIN DSA PRIVATE KEY" in text:
        return "ssh-dss"
    if "BEGIN OPENSSH PRIVATE KEY" in text:
        return _openssh_key_type(text)
    return None


def _refuse_unsupported(name: str, kind: str | None) -> None:
    """Refuse key types paramiko cannot sign with, saying why.

    Args:
        name: Key filename, for the message.
        kind: The key's declared type, or None when unknown.

    Raises:
        ValueError: For DSA, FIDO security keys and any other type
            paramiko cannot use.
    """
    if kind is None or kind in _SUPPORTED_KEY_TYPES:
        return
    if kind == "ssh-dss":
        raise ValueError(
            f"{name} is a DSA key. OpenSSH 10.0 removed DSA and paramiko "
            f"{paramiko.__version__} cannot use it; use an Ed25519 key."
        )
    if kind.startswith("sk-"):
        raise ValueError(
            f"{name} is a FIDO security key ({kind}), which paramiko cannot "
            "sign with. Hardware keys that ssh-agent offers as RSA, ECDSA "
            "or Ed25519 keys (PIV smartcards, for example) work with "
            "--use-agent."
        )
    raise ValueError(
        f"{name} is a {kind} key, which paramiko {paramiko.__version__} "
        "cannot use; use an RSA, ECDSA or Ed25519 key."
    )


def _load_private_key(
    path: str, passphrase: str | None, name: str
) -> paramiko.PKey:
    """Load a supported private key, naming a passphrase problem.

    Args:
        path: Private-key filename.
        passphrase: Passphrase for an encrypted key, never logged.
        name: Key filename, for messages.

    Returns:
        The loaded key.

    Raises:
        ValueError: If the key is encrypted and no passphrase was given,
            the passphrase is wrong, or the file holds no supported key.
    """
    for key_class in _KEY_TYPES:
        try:
            return key_class.from_private_key_file(path, password=passphrase)
        except paramiko.PasswordRequiredException as exc:
            raise ValueError(
                f"Private key {name} is encrypted; supply its passphrase."
            ) from exc
        except paramiko.SSHException as exc:
            if any(sign in str(exc) for sign in _WRONG_PASSPHRASE):
                raise ValueError(
                    f"Could not unlock private key {name}: wrong passphrase."
                ) from exc
    # About 1 in 256 wrong passwords pass the PEM padding check; the key
    # then fails to parse and paramiko names no password problem.
    if passphrase is not None and _is_encrypted_pem(path):
        raise ValueError(
            f"Could not unlock private key {name}: wrong passphrase."
        )
    raise ValueError(f"{name} is not an RSA, ECDSA or Ed25519 private key.")


def _is_encrypted_pem(path: str) -> bool:
    """Tell whether ``path`` holds a passphrase-encrypted PEM key."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        head = handle.read(4096)
    return (
        "Proc-Type: 4,ENCRYPTED" in head or "BEGIN ENCRYPTED PRIVATE" in head
    )


def _utc(seconds: int) -> str:
    """Format a certificate timestamp as an ISO 8601 UTC time."""
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def attach_certificate(key: paramiko.PKey, path: str, key_name: str) -> None:
    """Attach an OpenSSH certificate after checking it fits ``key``.

    paramiko only compares the certificate's key type, so a certificate
    issued for another key of the same type would fail late, at the
    server. This checks the certified key and the validity window first.

    Args:
        key: The loaded private key.
        path: Certificate filename (``*-cert.pub``).
        key_name: Private-key filename, for messages.

    Raises:
        ValueError: If the file is not an OpenSSH certificate, was issued
            for a different key, has expired or is not yet valid.
    """
    name = Path(path).name
    try:
        certificate = serialization.load_ssh_public_identity(
            Path(path).read_bytes()
        )
    except (ValueError, UnsupportedAlgorithm) as exc:
        raise ValueError(f"{name} is not an OpenSSH certificate.") from exc
    if not isinstance(certificate, serialization.SSHCertificate):
        raise ValueError(
            f"{name} is a public key, not an OpenSSH certificate."
        )
    certified = certificate.public_key().public_bytes(
        serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
    )
    if certified.split()[1].decode() != key.get_base64():
        raise ValueError(
            f"Certificate {name} was issued for a different key than {key_name}."
        )
    now = time.time()
    if now >= certificate.valid_before:
        raise ValueError(
            f"Certificate {name} expired at {_utc(certificate.valid_before)}."
        )
    if now < certificate.valid_after:
        raise ValueError(
            f"Certificate {name} is not valid until "
            f"{_utc(certificate.valid_after)}."
        )
    key.load_certificate(path)


def load_identity(
    identity_file: str | None,
    passphrase: str | None = None,
    certificate: str | None = None,
) -> paramiko.PKey | None:
    """Load the client identity before any connection, or refuse it.

    Args:
        identity_file: Private-key filename, or None for agent/defaults.
        passphrase: Passphrase for an encrypted key, never logged.
        certificate: Optional OpenSSH certificate for the key.

    Returns:
        The loaded key (with its certificate attached), or None when no
        identity file was given.

    Raises:
        ValueError: If the key type is unsupported, the key cannot be
            unlocked, or the certificate does not fit.
    """
    if identity_file is None:
        if certificate is not None:
            raise ValueError(
                "A certificate needs the private key it was issued for "
                "(--identity-file)."
            )
        return None
    name = Path(identity_file).name
    _refuse_unsupported(name, key_type(identity_file))
    key = _load_private_key(identity_file, passphrase, name)
    if certificate is not None:
        attach_certificate(key, certificate, name)
    return key
