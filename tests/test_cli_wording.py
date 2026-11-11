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

"""What ``generate --help`` and the banner say, and the base error.

The help examples passed ``-m`` and ``-s`` on every line, so the
optional template and schema looked required; the banner said the input
was "CSV or SQLite Data files" (JSON, JSONL and Parquet are read too)
in a sales voice; and the base exception was not importable from the
package root.
"""

from __future__ import annotations

import re

from click.testing import CliRunner

import pain001
from pain001.cli.cli import cli
from pain001.constants import APP_DESCRIPTION
from pain001.exceptions import Pain001Error


def test_generate_help_examples_need_no_template_or_schema() -> None:
    """Every example is runnable with only -t and -d."""
    result = CliRunner().invoke(cli, ["generate", "--help"])
    assert result.exit_code == 0
    examples = re.findall(r"^\s+(pain001 generate .*)$", result.output, re.M)
    assert examples, result.output
    assert "pain001 generate -t pain.001.001.09 -d payments.csv" in examples
    assert all(" -t " in line and " -d " in line for line in examples)
    assert not any(
        " -m " in line or " -s " in line for line in examples[:-1]
    ), examples


def test_banner_names_every_input_format_plainly() -> None:
    """The banner lists the real inputs and makes no claim."""
    for name in ("CSV", "SQLite", "JSON", "JSONL", "Parquet"):
        assert name in APP_DESCRIPTION
    assert "powerful" not in APP_DESCRIPTION.lower()
    assert "Data files" not in APP_DESCRIPTION


def test_base_error_is_exported() -> None:
    """``from pain001 import Pain001Error`` works and is public."""
    assert pain001.Pain001Error is Pain001Error
    assert "Pain001Error" in pain001.__all__
