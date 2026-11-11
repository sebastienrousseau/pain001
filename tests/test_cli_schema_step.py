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

"""The CLI never reports a schema check it did not make.

Until 0.0.86 ``generate`` ran ``validate_via_xsd`` on the Jinja template
file, which is not an instance of the schema: the check returned False,
the result was ignored, and the CLI printed "Schema validation passed"
anyway, spending a pure-Python schema compile on every run. The
generated document is what the XSD checks, and generation does that.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from pain001.cli.cli import cli
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.xml import validate_via_xsd as xsd_mod

MTYPE = "pain.001.001.09"
SAMPLE = (
    Path(DEFAULT_TEMPLATE_REGISTRY.get_template(MTYPE).template_path).parent
    / "template.csv"
)


@pytest.fixture
def workdir(monkeypatch, tmp_path: Path) -> Path:
    """An empty working directory holding one valid input file."""
    monkeypatch.chdir(tmp_path)
    shutil.copyfile(SAMPLE, tmp_path / "payments.csv")
    return tmp_path


def _refuse(*_args, **_kwargs):
    raise AssertionError("pure-Python schema compiled")


@pytest.mark.parametrize("extra", [[], ["--dry-run"]])
def test_no_template_schema_check(workdir: Path, extra: list[str]) -> None:
    """A valid run never compiles the schema with xmlschema."""
    xsd_mod._get_cached_schema.cache_clear()
    with patch.object(xsd_mod.xmlschema, "XMLSchema", side_effect=_refuse):
        result = CliRunner().invoke(
            cli,
            ["generate", "-t", MTYPE, "-d", "payments.csv", *extra],
        )
    xsd_mod._get_cached_schema.cache_clear()
    assert result.exit_code == 0, result.output
    assert "Schema validation passed" not in result.output
    assert "Validating XML template" not in result.output
