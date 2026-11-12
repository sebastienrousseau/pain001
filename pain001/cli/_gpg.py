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

"""Flags that are shorthand for environment variables.

``--decrypt-*`` configure the GPG loader and ``--workers`` streamed
generation, through the same variables the REST API and library
callers use; they apply for the lifetime of this process.
"""

from __future__ import annotations

import os

import click
from rich.console import Console

from pain001.cli._output import esc
from pain001.security.path_validator import sanitize_for_log

console = Console(stderr=True)


def _apply_gpg_options(
    decrypt_key: str | None, decrypt_passphrase_env: str | None
) -> None:
    """Hand the ``--decrypt-*`` flags to the GPG loader via its env vars.

    The loader (``pain001.plugins.builtins_gpg``) is configured through
    the environment so the same knobs work for the CLI, the REST API
    and library callers; the flags are sugar over those variables and
    only apply for the lifetime of this process.

    Args:
        decrypt_key: Path to a GPG private-key file to import before
            decrypting, or ``None`` to rely on the keyring.
        decrypt_passphrase_env: Name of the environment variable that
            holds the key's passphrase, or ``None`` when unprotected.
    """
    if decrypt_key:
        os.environ["PAIN001_GPG_KEYFILE"] = decrypt_key
        console.print(
            f"[cyan]ℹ GPG key file: {esc(sanitize_for_log(decrypt_key))}[/cyan]"
        )
    if decrypt_passphrase_env:
        os.environ["PAIN001_GPG_PASSPHRASE_ENV"] = decrypt_passphrase_env


def _workers_option(
    ctx: click.Context, param: click.Parameter, value: int | None
) -> int | None:
    """Hand ``--workers`` to streamed generation via ``PAIN001_WORKERS``.

    Args:
        ctx: The Click context (unused).
        param: The option (unused).
        value: The worker count, or ``None`` when the flag is absent.

    Returns:
        The value, unchanged.
    """
    if value is not None:
        os.environ["PAIN001_WORKERS"] = str(value)
    return value
