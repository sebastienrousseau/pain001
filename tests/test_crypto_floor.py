# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The cryptographic floor: no short RSA keys, no weak SSH algorithms.

XML-DSig refuses RSA keys under 2048 bits, the NIST minimum through
2030 (SP 800-131A), when signing and when verifying. The SFTP transport
never offers CBC or 3DES ciphers or SHA-1 and MD5 MACs, which paramiko
otherwise keeps as lower-preference fallbacks.
"""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from pain001.security import _dsig_algorithms as algorithms

paramiko = pytest.importorskip("paramiko")

from pain001.transport import sftp  # noqa: E402

WEAK_CIPHERS = {"aes128-cbc", "aes192-cbc", "aes256-cbc", "3des-cbc"}
WEAK_MACS = {"hmac-sha1", "hmac-md5", "hmac-sha1-96", "hmac-md5-96"}


@pytest.fixture(scope="module")
def short_rsa():
    """A 1024-bit RSA key, below the floor."""
    return rsa.generate_private_key(public_exponent=65537, key_size=1024)


@pytest.mark.parametrize("requested", [None, "rsa-sha256", "rsa-pss-sha256"])
def test_short_rsa_key_is_refused(short_rsa, requested):
    with pytest.raises(ValueError, match="2048 bits"):
        algorithms.algorithm_for_key(short_rsa, requested)


def test_short_rsa_key_is_refused_when_verifying(short_rsa):
    algorithm = algorithms.ALGORITHMS["rsa-sha256"]
    with pytest.raises(ValueError, match="2048 bits"):
        algorithms.verify_bytes(
            short_rsa.public_key(), algorithm, b"\x00" * 128, b"data"
        )


def test_2048_bit_rsa_key_is_accepted():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert algorithms.algorithm_for_key(key).name == "rsa-sha256"


def test_transport_offers_no_weak_algorithms():
    """A real paramiko Transport built with the floor offers none of them."""
    left, right = socket.socketpair()
    try:
        transport = paramiko.Transport(
            left, disabled_algorithms=sftp.DISABLED_ALGORITHMS
        )
        offered_ciphers = set(transport.preferred_ciphers)
        offered_macs = set(transport.preferred_macs)
        transport.close()
    finally:
        left.close()
        right.close()
    assert not offered_ciphers & WEAK_CIPHERS
    assert not offered_macs & WEAK_MACS
    assert "aes256-ctr" in offered_ciphers
    assert "hmac-sha2-256" in offered_macs


def test_connect_applies_the_floor():
    client = MagicMock()
    target = sftp.parse_target("sftp://ops@bank.example/inbox/")
    with patch.object(sftp, "load_identity", return_value=None):
        sftp._connect(client, target, sftp.Credentials(), 5)
    disabled = client.connect.call_args.kwargs["disabled_algorithms"]
    assert disabled is sftp.DISABLED_ALGORITHMS


def test_fingerprint_probe_applies_the_floor():
    transport = MagicMock()
    transport.__enter__.return_value = transport
    transport.get_remote_server_key.return_value = paramiko.ECDSAKey.generate()
    with (
        patch.object(
            sftp.socket, "create_connection", return_value=MagicMock()
        ),
        patch.object(paramiko, "Transport", return_value=transport) as build,
    ):
        sftp.print_host_fingerprint("sftp://ops@bank.example/inbox/", 3)
    assert build.call_args.kwargs["disabled_algorithms"] is (
        sftp.DISABLED_ALGORITHMS
    )
