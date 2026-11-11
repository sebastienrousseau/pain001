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


#: ``generate --help``: every example runs with only ``-t`` and ``-d``.
GENERATE_HELP = (
    "Generate ISO 20022 payment XML from CSV, SQLite, JSON, JSONL "
    "or Parquet data. The template and schema for the message type "
    "are bundled; -m and -s replace them.\n\n"
    "\b\nExamples:\n"
    "  # into the current directory\n"
    "  pain001 generate -t pain.001.001.09 -d payments.csv\n"
    "  # into a directory\n"
    "  pain001 generate -t pain.001.001.09 -d payments.csv -o out/\n"
    "  # validate only, write nothing\n"
    "  pain001 generate -t pain.001.001.09 -d payments.csv --dry-run\n"
    "  # JSON input, with log records on stderr\n"
    "  pain001 generate -t pain.001.001.09 -d payments.json -v\n"
    "  # your own template and schema\n"
    "  pain001 generate -t pain.001.001.09 -d payments.csv "
    "-m template.xml -s schema.xsd\n\n"
    "\b\nExit codes:\n"
    "  0  success\n"
    "  1  findings: invalid data or a failed check\n"
    "  2  usage, a missing input file or configuration"
)
