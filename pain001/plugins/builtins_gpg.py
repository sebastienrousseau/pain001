# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Built-in GPG-decrypting loader (requires the ``pain001[gpg]`` extra).

A composition plugin: it does not understand the inner payload
format itself; instead it decrypts ``foo.csv.gpg`` (or ``.asc``) in
memory, writes the plaintext to a brief, ``0o600``-permissioned
temp file in ``/dev/shm`` (Linux RAM-backed tmpfs) or the platform
default otherwise, dispatches to the loader registered for the
inner extension (``.csv``, ``.json``, …), and unlinks the temp file
before returning.

Plaintext therefore touches the filesystem for the duration of the
inner loader's read - on Linux that is a RAM-backed file, on other
platforms an unlinked temp file with restrictive permissions. This
trade-off is documented in ``docs/plugins.md``; a future loader
contract version may add a bytes-native API to eliminate the temp
file entirely.

Configuration is environment-driven (the same surface ops teams use
for the REST API and Redis backends):

* ``PAIN001_GPG_HOMEDIR`` - GPG homedir (default: ``~/.gnupg``).
* ``PAIN001_GPG_PASSPHRASE_ENV`` - name of the env var that holds
  the private-key passphrase, if the key is passphrase-protected.
* ``PAIN001_GPG_KEY_ID`` - optional specific key id to decrypt with;
  when unset, any matching key in the keyring is tried.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pain001.exceptions import DataSourceError
from pain001.plugins._version import PAIN001_API_VERSION
from pain001.plugins.contracts import LoaderResult, PluginMeta

if TYPE_CHECKING:
    from pain001.plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)


class GpgDecryptError(DataSourceError):
    """Raised when GPG decryption fails for any reason.

    Wraps the underlying ``gnupg`` error so callers see a single
    pain001-typed exception, with no key material or stack trace
    leaking into the message.
    """


def _gpg_module() -> Any:
    """Import ``gnupg`` lazily so the dep is truly optional.

    Returns:
        The imported ``gnupg`` module.

    Raises:
        DataSourceError: When the ``python-gnupg`` package (and the
            underlying ``gpg`` binary) are not available.
    """
    try:
        import gnupg  # noqa: PLC0415 - lazy
    except ImportError as exc:
        raise DataSourceError(
            "The pain001[gpg] extra is required to read .gpg / .asc "
            "files; install with `pip install pain001[gpg]` and ensure "
            "the `gpg` binary is on PATH."
        ) from exc
    return gnupg


def _secure_tempfile_dir() -> str:
    """Return the best available secure tempfile directory for this host.

    Prefers Linux ``/dev/shm`` (RAM-backed tmpfs, no spinning-disk
    persistence) when available and writable. Falls back to the
    platform default, which is fine on macOS (``/var/folders/...``)
    and Windows (``%TEMP%``) where the temp files at least carry our
    ``0o600`` permissions and are unlinked promptly.

    Returns:
        Filesystem path to use for the temp directory.
    """
    if sys.platform.startswith("linux"):
        shm = "/dev/shm"  # nosec B108 - vetted RAM-tmpfs, checked writable, 0o600
        if os.path.isdir(shm) and os.access(shm, os.W_OK):
            return shm
    return tempfile.gettempdir()


def _inner_extension(path: str) -> str:
    """Strip ``.gpg`` / ``.asc`` from ``path`` and return the inner ext.

    Args:
        path: The encrypted-file path (``"batch.csv.gpg"`` etc.).

    Returns:
        The inner extension *with* leading dot, lowercased
        (``".csv"``). Empty string when there is no inner extension
        (e.g. ``"sealed.gpg"`` alone, which is then treated by the
        registry as an unsupported format).
    """
    suffixes = Path(path).suffixes  # [".csv", ".gpg"]
    if len(suffixes) >= 2 and suffixes[-1].lower() in {".gpg", ".asc"}:
        return suffixes[-2].lower()
    return ""


def _decrypt_to_bytes(ciphertext: bytes) -> bytes:
    """Decrypt ``ciphertext`` to plaintext bytes via ``python-gnupg``.

    Args:
        ciphertext: Raw bytes read from the encrypted file (binary
            or ASCII-armoured).

    Returns:
        Plaintext bytes.

    Raises:
        GpgDecryptError: When decryption fails for any reason - no
            secret key in the keyring, wrong passphrase, bad
            signature, etc.
    """
    gnupg = _gpg_module()
    homedir = os.environ.get("PAIN001_GPG_HOMEDIR") or None
    gpg = gnupg.GPG(gnupghome=homedir) if homedir else gnupg.GPG()
    passphrase_env = os.environ.get("PAIN001_GPG_PASSPHRASE_ENV")
    passphrase = os.environ.get(passphrase_env) if passphrase_env else None
    result = gpg.decrypt(ciphertext, passphrase=passphrase)
    if not bool(result):
        # Don't echo ``str(result)`` directly - it can include the
        # tried-key fingerprint. The status / stderr surface a fixed
        # short status string we can safely propagate.
        status = getattr(result, "status", "decryption failed")
        raise GpgDecryptError(
            f"GPG decryption failed: {status}. Check "
            "PAIN001_GPG_HOMEDIR, PAIN001_GPG_PASSPHRASE_ENV, and that "
            "the matching secret key is available in the keyring."
        )
    return bytes(result.data)


class _GpgDecryptingLoader:
    """Decrypt ``.gpg`` / ``.asc`` files and dispatch to the inner loader.

    Registered as a built-in plugin (kind=``loader``, name=``gpg``)
    when the ``pain001[gpg]`` extra is installed. Composes with any
    other registered loader by inner extension: ``batch.csv.gpg``
    flows through this loader then through the ``csv`` loader.
    """

    meta = PluginMeta(
        name="gpg",
        version="0.0.57",  # synced with the pain001 build that ships it
        description=(
            "Decrypt .gpg / .asc files in memory then dispatch to the "
            "inner-extension loader (pain001[gpg])."
        ),
        api_version=PAIN001_API_VERSION,
        source="built-in",
    )
    extensions: tuple[str, ...] = (".gpg", ".asc")

    def load(self, path: str) -> LoaderResult:
        """Decrypt ``path`` and delegate to the inner loader.

        Args:
            path: Path to an encrypted file whose name carries the
                inner extension first (e.g. ``"payments.csv.gpg"``).

        Returns:
            The inner loader's :class:`LoaderResult`, with
            ``source_hint`` rewritten to the original encrypted path
            so downstream findings point at the file the user named.

        Raises:
            DataSourceError: When the inner extension is unknown,
                when no loader is registered for it, or when
                decryption fails.
        """
        inner_ext = _inner_extension(path)
        if not inner_ext:
            raise DataSourceError(
                f"Cannot infer inner format for {path}: filename must "
                "be of the form `<name>.<inner-ext>.gpg` (e.g. "
                "`batch.csv.gpg`)."
            )
        with open(path, "rb") as fh:
            ciphertext = fh.read()
        plaintext = _decrypt_to_bytes(ciphertext)
        return self._dispatch(plaintext, inner_ext, path)

    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]:
        """Decrypt once, then yield from the inner loader's streaming variant.

        Args:
            path: Encrypted-file path.
            chunk_size: Forwarded verbatim to the inner loader.

        Yields:
            LoaderResult: chunks from the inner loader.

        Raises:
            DataSourceError: When the inner extension is unknown,
                when no loader is registered for it, or when
                decryption fails.
        """
        inner_ext = _inner_extension(path)
        if not inner_ext:
            raise DataSourceError(
                f"Cannot infer inner format for {path}: filename must "
                "be of the form `<name>.<inner-ext>.gpg`."
            )
        with open(path, "rb") as fh:
            ciphertext = fh.read()
        plaintext = _decrypt_to_bytes(ciphertext)
        yield from self._dispatch_streaming(
            plaintext, inner_ext, path, chunk_size
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _dispatch(
        self, plaintext: bytes, inner_ext: str, source_hint: str
    ) -> LoaderResult:
        """Hand decrypted bytes to the inner loader via a secure temp file."""
        # Lazy import to avoid a circular dep with the registry.
        from pain001.plugins.registry import (  # noqa: PLC0415
            registry as plugin_registry,
        )

        inner = plugin_registry.get_loader_for_extension(inner_ext)
        if inner is None:
            raise DataSourceError(
                f"GPG loader: no inner loader registered for "
                f"{inner_ext!r} (got {source_hint}). Install a plugin "
                "that handles that extension, or use a supported "
                "inner format."
            )
        with _secure_tempfile(plaintext, inner_ext) as tmp_path:
            result = inner.load(tmp_path)
        # Rewrite the source hint so downstream findings cite the
        # *encrypted* file the user passed, not the ephemeral temp.
        return LoaderResult(rows=result.rows, source_hint=source_hint)

    def _dispatch_streaming(
        self,
        plaintext: bytes,
        inner_ext: str,
        source_hint: str,
        chunk_size: int,
    ) -> Iterable[LoaderResult]:
        """Streaming dispatch variant of :meth:`_dispatch`."""
        from pain001.plugins.registry import (  # noqa: PLC0415
            registry as plugin_registry,
        )

        inner = plugin_registry.get_loader_for_extension(inner_ext)
        if inner is None:
            raise DataSourceError(
                f"GPG loader: no inner loader registered for "
                f"{inner_ext!r} (got {source_hint})."
            )
        with _secure_tempfile(plaintext, inner_ext) as tmp_path:
            for chunk in inner.load_streaming(tmp_path, chunk_size):
                yield LoaderResult(rows=chunk.rows, source_hint=source_hint)


class _secure_tempfile:
    """Context manager yielding a ``0o600`` plaintext temp file.

    Writes ``data`` to a temp file under :func:`_secure_tempfile_dir`
    with the requested ``suffix``. On exit, the file is *unlinked*
    even if the inner block raised. The bytes only live on disk for
    the duration of the inner loader's read.

    Args:
        data: The plaintext bytes to materialise.
        suffix: File extension to give the temp file (with leading
            dot) so the inner loader's extension dispatch still
            works.
    """

    def __init__(self, data: bytes, suffix: str) -> None:
        self._data = data
        self._suffix = suffix
        self._path: str | None = None

    def __enter__(self) -> str:
        """Materialise the temp file and return its path."""
        fd, path = tempfile.mkstemp(
            suffix=self._suffix,
            prefix="pain001-gpg-",
            dir=_secure_tempfile_dir(),
        )
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, self._data)
        finally:
            os.close(fd)
        self._path = path
        return path

    def __exit__(self, *exc_info: Any) -> None:
        """Unlink the temp file (best-effort)."""
        if self._path is not None:
            try:
                os.unlink(self._path)
            except FileNotFoundError:  # pragma: no cover - already gone
                pass


def maybe_register(reg: PluginRegistry) -> None:
    """Register the GPG loader iff the ``python-gnupg`` extra is installed.

    Called by ``pain001.plugins._builtins.register_all`` so the GPG
    loader is opt-in via the extra rather than always-on.

    Args:
        reg: The process-level :class:`PluginRegistry` to populate.
    """
    try:
        import gnupg  # noqa: PLC0415, F401 - probe only
    except ImportError:
        logger.debug(
            "pain001[gpg] extra not installed; .gpg / .asc loader unavailable"
        )
        return
    reg.register_loader(_GpgDecryptingLoader())
