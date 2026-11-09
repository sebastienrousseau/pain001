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

"""The XML-DSig signature algorithms pain001 signs and verifies with.

Each algorithm is a W3C identifier plus how ``cryptography`` signs and
verifies with it. Verification accepts only the identifiers listed here
(``ALLOWED_SIGNATURE_METHODS``), so a document cannot pick a weak or
unexpected algorithm for its own check.

* ``rsa-sha256``: RSASSA-PKCS1-v1_5 with SHA-256 (RFC 6931).
* ``rsa-pss-sha256``: RSASSA-PSS with SHA-256, MGF1-SHA-256 and a
  32-byte salt (RFC 9231 ``sha256-rsa-MGF1``).
* ``ecdsa-sha256`` and ``ecdsa-sha384``: ECDSA on P-256 and P-384, the
  signature written as the raw ``r || s`` pair XML-DSig 1.1 (6.4.3)
  requires, not DER.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SIG_RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
SIG_RSA_PSS_SHA256 = "http://www.w3.org/2007/05/xmldsig-more#sha256-rsa-MGF1"
SIG_ECDSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#ecdsa-sha256"
SIG_ECDSA_SHA384 = "http://www.w3.org/2001/04/xmldsig-more#ecdsa-sha384"


@dataclass(frozen=True)
class SignatureAlgorithm:
    """One signature method: its short name, W3C URI and hash size."""

    name: str
    uri: str
    hash_name: str
    family: str  # "rsa", "rsa-pss" or "ecdsa"


ALGORITHMS: dict[str, SignatureAlgorithm] = {
    a.name: a
    for a in (
        SignatureAlgorithm("rsa-sha256", SIG_RSA_SHA256, "sha256", "rsa"),
        SignatureAlgorithm(
            "rsa-pss-sha256", SIG_RSA_PSS_SHA256, "sha256", "rsa-pss"
        ),
        SignatureAlgorithm(
            "ecdsa-sha256", SIG_ECDSA_SHA256, "sha256", "ecdsa"
        ),
        SignatureAlgorithm(
            "ecdsa-sha384", SIG_ECDSA_SHA384, "sha384", "ecdsa"
        ),
    )
}

#: Every SignatureMethod URI verification accepts.
ALLOWED_SIGNATURE_METHODS = {a.uri: a for a in ALGORITHMS.values()}

#: The ECDSA algorithm each supported curve signs with.
_CURVE_ALGORITHM = {"secp256r1": "ecdsa-sha256", "secp384r1": "ecdsa-sha384"}


def _crypto() -> tuple[Any, Any, Any, Any]:
    """``hashes``, ``padding``, ``ec`` and the DSS helpers, lazily."""
    from cryptography.hazmat.primitives import hashes  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric import (  # noqa: PLC0415
        ec,
        padding,
        utils,
    )

    return hashes, padding, ec, utils


def _is_rsa(key: Any) -> bool:
    """Whether ``key`` is an RSA private or public key."""
    from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: PLC0415

    return isinstance(key, (rsa.RSAPrivateKey, rsa.RSAPublicKey))


def algorithm_for_key(
    key: Any, requested: str | None = None
) -> SignatureAlgorithm:
    """The algorithm a private or public key signs with.

    Args:
        key: An RSA or EC key from ``cryptography``.
        requested: A name from ``ALGORITHMS``; None infers it from the
            key (RSA signs ``rsa-sha256``, P-256 and P-384 the matching
            ECDSA).

    Returns:
        The algorithm.

    Raises:
        ValueError: If the key type or curve is unsupported, or the
            requested algorithm does not fit the key.
    """
    _, _, ec, _ = _crypto()
    if isinstance(
        key, (ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey)
    ):
        inferred = _CURVE_ALGORITHM.get(key.curve.name)
        if inferred is None:
            raise ValueError(
                f"unsupported EC curve {key.curve.name}: use P-256 or P-384"
            )
        families = {"ecdsa"}
    elif _is_rsa(key):
        inferred, families = "rsa-sha256", {"rsa", "rsa-pss"}
    else:
        raise ValueError(f"unsupported key type {type(key).__name__}")
    if requested is None:
        return ALGORITHMS[inferred]
    algorithm = ALGORITHMS.get(requested)
    if algorithm is None or algorithm.family not in families:
        raise ValueError(
            f"algorithm {requested!r} does not fit a {sorted(families)[0]} key"
        )
    if algorithm.family == "ecdsa" and algorithm.name != inferred:
        raise ValueError(f"{requested} needs a different curve than this key")
    return algorithm


def _hash(algorithm: SignatureAlgorithm) -> Any:
    """The ``cryptography`` hash the algorithm signs with."""
    hashes, _, _, _ = _crypto()
    return (
        hashes.SHA384() if algorithm.hash_name == "sha384" else hashes.SHA256()
    )


def _pss(hashes: Any, padding: Any) -> Any:
    """RFC 9231: MGF1 with the same hash, salt as long as the digest."""
    return padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32)


def sign_bytes(key: Any, algorithm: SignatureAlgorithm, data: bytes) -> bytes:
    """The SignatureValue bytes for ``data`` (canonical SignedInfo).

    Args:
        key: The private key.
        algorithm: From ``algorithm_for_key``.
        data: The bytes to sign.

    Returns:
        PKCS#1 or PSS bytes for RSA, raw ``r || s`` for ECDSA.
    """
    hashes, padding, ec, utils = _crypto()
    digest = _hash(algorithm)
    if algorithm.family == "rsa":
        return bytes(key.sign(data, padding.PKCS1v15(), digest))
    if algorithm.family == "rsa-pss":
        return bytes(key.sign(data, _pss(hashes, padding), digest))
    der = key.sign(data, ec.ECDSA(digest))
    r, s = utils.decode_dss_signature(der)
    size: int = (key.curve.key_size + 7) // 8
    return int(r).to_bytes(size, "big") + int(s).to_bytes(size, "big")


def verify_bytes(
    key: Any, algorithm: SignatureAlgorithm, signature: bytes, data: bytes
) -> None:
    """Check ``signature`` over ``data``; raise if it does not verify.

    A signature that does not verify raises ``cryptography``'s
    ``InvalidSignature`` from the key's own ``verify``.

    Args:
        key: The public key.
        algorithm: The document's declared, allow-listed algorithm.
        signature: The decoded SignatureValue.
        data: Canonical SignedInfo.

    Raises:
        ValueError: If the key does not fit the algorithm or the raw
            ECDSA value has the wrong length.
    """
    hashes, padding, ec, utils = _crypto()
    algorithm_for_key(key, algorithm.name)
    digest = _hash(algorithm)
    if algorithm.family == "rsa":
        key.verify(signature, data, padding.PKCS1v15(), digest)
    elif algorithm.family == "rsa-pss":
        key.verify(signature, data, _pss(hashes, padding), digest)
    else:
        size = (key.curve.key_size + 7) // 8
        if len(signature) != 2 * size:
            raise ValueError(
                f"an {algorithm.name} SignatureValue is {2 * size} bytes "
                f"(raw r || s), not {len(signature)}"
            )
        r = int.from_bytes(signature[:size], "big")
        s = int.from_bytes(signature[size:], "big")
        der = utils.encode_dss_signature(r, s)
        key.verify(der, data, ec.ECDSA(digest))
