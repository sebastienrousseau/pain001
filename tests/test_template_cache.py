# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""A template is compiled once per source text, not once per call.

Compiling the sandboxed template cost about 8.6 ms of a 8.9 ms
``generate_xml_string`` call on a five-row batch (0.0.81). The cache is
keyed on the template's text, read through the trusted-path check on
every call, so an edited template compiles again.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from pain001.constants import TEMPLATES_DIR
from pain001.xml import generate_xml as gx

MESSAGE_TYPE = "pain.001.001.09"
BUNDLE = TEMPLATES_DIR / MESSAGE_TYPE


def _rows() -> list[dict[str, str]]:
    with (BUNDLE / "template.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    gx._compile_template.cache_clear()


def test_the_same_source_compiles_once() -> None:
    first = gx._compile_template("<a>{{ x }}</a>")
    assert gx._compile_template("<a>{{ x }}</a>") is first
    assert gx._compile_template.cache_info().misses == 1


def test_repeated_generation_reuses_the_compiled_template() -> None:
    args = (
        _rows(),
        MESSAGE_TYPE,
        str(BUNDLE / "template.xml"),
        str(BUNDLE / f"{MESSAGE_TYPE}.xsd"),
    )
    first = gx.generate_xml_string(*args)
    second = gx.generate_xml_string(*args)
    assert first == second
    info = gx._compile_template.cache_info()
    assert (info.misses, info.hits) == (1, 1)


def test_an_edited_template_compiles_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    template = tmp_path / "template.xml"
    shutil.copy(BUNDLE / "template.xml", template)
    xsd = str(BUNDLE / f"{MESSAGE_TYPE}.xsd")
    before = gx.generate_xml_string(_rows(), MESSAGE_TYPE, str(template), xsd)
    template.write_text(
        template.read_text(encoding="utf-8").replace(
            "<CstmrCdtTrfInitn>", "<CstmrCdtTrfInitn>\n<!-- edited -->", 1
        ),
        encoding="utf-8",
    )
    after = gx.generate_xml_string(_rows(), MESSAGE_TYPE, str(template), xsd)
    assert "<!-- edited -->" in after
    assert "<!-- edited -->" not in before
    assert gx._compile_template.cache_info().misses == 2


def test_autoescape_still_applies_to_cached_templates() -> None:
    template = gx._compile_template("<a>{{ x }}</a>")
    assert template.render(x="<b>&") == "<a>&lt;b&gt;&amp;</a>"
