# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The SSH algorithms the SFTP transport never offers.

paramiko keeps CBC and 3DES ciphers and SHA-1 and MD5 MACs as
lower-preference fallbacks; with these disabled, a server that offers
nothing better is refused at key exchange. Key exchange and host-key
algorithms are SHA-2 or better already.
"""

from __future__ import annotations

#: The ``disabled_algorithms`` argument for ``paramiko``.
DISABLED_ALGORITHMS: dict[str, list[str]] = {
    "ciphers": ["aes128-cbc", "aes192-cbc", "aes256-cbc", "3des-cbc"],
    "macs": ["hmac-sha1", "hmac-md5", "hmac-sha1-96", "hmac-md5-96"],
}
