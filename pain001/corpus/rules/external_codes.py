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


"""The ISO 20022 external code sets, vendored.

ISO publishes the external code sets quarterly at iso20022.org, no
login needed, as XLSX, XSD and a JSON Schema document whose
``definitions`` hold one ``enum`` per code set. That JSON is vendored
verbatim under ``pain001/corpus/data/external_codes/<edition>.json``;
the edition is the file's stem. Codes are version-independent: the
same list serves pain.001.001.03 and .13 alike.

``scripts/refresh_external_codes.py`` swaps in a newer edition and
refuses when a code the bundled data uses has been withdrawn.

A few sets (the bank transaction domain, family and sub-family codes,
card transaction categories) are declared without an ``enum`` because
ISO publishes their codes in a separate structured list; they are
listed by :func:`sets_without_codes` and :func:`codes` raises for them.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "external_codes"

_DESCRIPTION_LINE = re.compile(r"^\*`([A-Z0-9]+)`-(.*)$", re.MULTILINE)


def edition_file(data_dir: Path = DATA_DIR) -> Path:
    """The vendored edition, the one ``*.json`` in ``data_dir``.

    Args:
        data_dir: Directory holding the vendored JSON.

    Returns:
        The path of the edition file.

    Raises:
        FileNotFoundError: If there is not exactly one edition file.
    """
    files = sorted(data_dir.glob("*.json"))
    if len(files) != 1:
        raise FileNotFoundError(
            f"expected exactly one external code set edition in "
            f"{data_dir}, found {[f.name for f in files]}"
        )
    return files[0]


def edition() -> str:
    """The vendored edition's name, e.g. ``2Q2026_v3``."""
    return edition_file().stem


@cache
def _definitions() -> dict[str, dict[str, Any]]:
    """The ``definitions`` block of the vendored document."""
    with open(edition_file(), encoding="utf-8") as handle:
        document = json.load(handle)
    definitions: dict[str, dict[str, Any]] = document["definitions"]
    return definitions


def load_definitions(path: Path) -> dict[str, dict[str, Any]]:
    """The ``definitions`` block of any edition file.

    Args:
        path: An external code set JSON Schema document.

    Returns:
        Its ``definitions``.
    """
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    definitions: dict[str, dict[str, Any]] = document["definitions"]
    return definitions


def code_sets() -> tuple[str, ...]:
    """Every set name the edition declares, sorted."""
    return tuple(sorted(_definitions()))


def sets_without_codes() -> tuple[str, ...]:
    """Sets declared without an ``enum``, sorted."""
    return tuple(
        sorted(
            name
            for name, spec in _definitions().items()
            if not spec.get("enum")
        )
    )


def codes(set_name: str) -> tuple[str, ...]:
    """The codes of one set, in publication order.

    Args:
        set_name: An ISO set name such as ``ExternalPurpose1Code``.

    Returns:
        The codes.

    Raises:
        KeyError: If the set is unknown or carries no codes.
    """
    spec = _definitions().get(set_name)
    if spec is None or not spec.get("enum"):
        raise KeyError(
            f"{set_name!r} is not an external code set with codes in "
            f"edition {edition()}"
        )
    return tuple(spec["enum"])


def is_valid(set_name: str, code: str) -> bool:
    """True when ``code`` is in ``set_name``.

    Args:
        set_name: An ISO set name.
        code: The candidate code, exact case.

    Returns:
        Whether the code is published in that set.
    """
    return code in codes(set_name)


@cache
def _descriptions(set_name: str) -> dict[str, str]:
    """Parse the ``*`CODE`-text`` lines of a set's description."""
    text = _definitions()[set_name].get("description", "")
    return {
        code: desc.strip() for code, desc in _DESCRIPTION_LINE.findall(text)
    }


def describe(set_name: str, code: str) -> str | None:
    """The published one-line meaning of a code, if the edition has one.

    Args:
        set_name: An ISO set name.
        code: A code in that set.

    Returns:
        The description text, or ``None`` when the edition gives none.
    """
    codes(set_name)  # validates the set
    return _descriptions(set_name).get(code)


__all__ = [
    "DATA_DIR",
    "code_sets",
    "codes",
    "describe",
    "edition",
    "edition_file",
    "is_valid",
    "load_definitions",
    "sets_without_codes",
]
