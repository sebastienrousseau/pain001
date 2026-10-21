# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""CITATION.cff states the package's real licence, in CFF's own form.

CFF 1.2.0 takes ``license`` as one SPDX identifier or a list of them;
an SPDX *expression* such as ``Apache-2.0 OR MIT`` is not valid there,
and citation tooling rejects the file. A dual licence is the list.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

if sys.version_info >= (3, 11):  # pragma: no cover - version dependent
    import tomllib
else:  # pragma: no cover - version dependent
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent


def _citation() -> dict:
    return yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))


def test_the_licence_is_a_list_of_spdx_identifiers() -> None:
    """No expression: each entry is a bare identifier."""
    licence = _citation()["license"]
    assert isinstance(licence, list), (
        f"CITATION.cff license is {licence!r}; CFF 1.2.0 needs an SPDX "
        f"identifier or a list of them, not an expression"
    )
    assert all(" " not in entry for entry in licence), licence


def test_the_licence_matches_the_package() -> None:
    """The same grant as the wheel's License-Expression."""
    with (ROOT / "pyproject.toml").open("rb") as handle:
        expression = tomllib.load(handle)["project"]["license"]
    assert " OR ".join(_citation()["license"]) == expression


def test_every_listed_licence_ships_its_text() -> None:
    """A licence named in the citation has its text in the tree."""
    names = {"Apache-2.0": "LICENSE-APACHE", "MIT": "LICENSE-MIT"}
    for entry in _citation()["license"]:
        assert (ROOT / names[entry]).is_file(), entry
