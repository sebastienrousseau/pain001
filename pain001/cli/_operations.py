# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Commands that move payment files to and from a bank, and read replies.

They are registered here rather than in ``cli.py``, which is already
over the file-length ceiling: ``upload`` and ``download`` (SFTP,
``pain001[upload]``, imported only when run) and ``status``.
"""

from __future__ import annotations

import click

from pain001.cli._status import status_cmd
from pain001.transport.cli import upload_cmd
from pain001.transport.download_cli import download_cmd


def add_operations(group: click.Group) -> None:
    """Register ``upload``, ``download`` and ``status`` on ``group``.

    Args:
        group: The ``pain001`` command group.
    """
    group.add_command(upload_cmd)
    group.add_command(download_cmd)
    group.add_command(status_cmd)
