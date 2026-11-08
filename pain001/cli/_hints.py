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

"""Small helpers the ``generate`` and ``validate`` commands share."""

import os

from rich.console import Console


def print_data_tip(console: Console, data_file_path: str) -> None:
    """Print a hint for a data file that failed to load, by its type.

    Args:
        console: The console the command writes to.
        data_file_path: Path to the payment data that failed.
    """
    # Provide helpful error messages based on file extension
    file_ext = os.path.splitext(data_file_path)[1].lower()
    if file_ext == ".parquet":
        console.print(
            "\n[yellow]Tip:[/yellow] Parquet files require pyarrow. "
            "Install with: [cyan]pip install pyarrow[/cyan]"
        )
    elif file_ext in [".json", ".jsonl"]:
        console.print(
            "\n[yellow]Tip:[/yellow] Ensure JSON is valid. "
            "Check for syntax errors or invalid structure."
        )


def read_text(path: str | None) -> str | None:
    """Return the UTF-8 text of ``path``, or ``None`` when none is given.

    Args:
        path: A PEM file path from a ``--xml-sign-*`` option, or ``None``.

    Returns:
        The file's text, or ``None``.
    """
    if not path:
        return None
    with open(path, encoding="utf-8") as handle:
        return handle.read()
