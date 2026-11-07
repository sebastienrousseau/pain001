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

"""ISO 2018 compatibility face: full element names in snake_case (ADR-0005).

Each XML tag becomes its ISO 20022 message element name, read from
``iso_names.json``, a table derived from the Registration Authority's
Message Definition Reports (Part 2) with the reports and the read date
recorded (see ``scripts/build_iso_name_table.py``), then written in
snake_case: ``GrpHdr`` -> ``group_header``. The message content is
projected without the ``Document`` root, repeatable elements stay
arrays, and an amount becomes ``{"amount", "currency"}``. A tag the
table lists as unresolved has no name to give, so that element and
everything under it stay out of the payload and appear in the loss
report.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from typing import Any

from pain001.faces.common import MESSAGE
from pain001.faces.models import FaceError
from pain001.faces.paths import is_amount, join

FACE = "iso_2018"
BINDINGS: tuple[str, ...] = ()

_ACRONYM_BOUNDARY = re.compile(r"([A-Z]+)([A-Z][a-z])")
_WORD_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")


@lru_cache(maxsize=1)
def name_table() -> dict[str, Any]:
    """The shipped tag-to-name table with its provenance."""
    text = (
        resources.files("pain001.faces")
        .joinpath("iso_names.json")
        .read_text(encoding="utf-8")
    )
    table: dict[str, Any] = json.loads(text)
    return table


def snake_case(name: str) -> str:
    """``CreditTransferTransactionInformation`` -> ``credit_transfer_...``.

    Runs of capitals stay one word: ``BICFI`` -> ``bicfi``, ``AnyBIC`` ->
    ``any_bic``, ``UETR`` -> ``uetr``.
    """
    return _WORD_BOUNDARY.sub(
        r"\1_\2", _ACRONYM_BOUNDARY.sub(r"\1_\2", name)
    ).lower()


def _project(
    node: Any, path: str, names: dict[str, str], mapped: set[str]
) -> Any:
    """Rename one twin node, recording each leaf that is carried."""
    if isinstance(node, list):
        return [
            _project(item, f"{path}[{index}]", names, mapped)
            for index, item in enumerate(node)
        ]
    if is_amount(node):
        mapped.update((path, f"{path}/@Ccy"))
        return {"amount": node["amt"], "currency": node["Ccy"]}
    if isinstance(node, dict):
        return {
            snake_case(names[key]): _project(
                value, join(path, key), names, mapped
            )
            for key, value in node.items()
            if key in names
        }
    mapped.add(path)
    return node


def project_iso_2018(
    twin: dict[str, Any],
    bindings: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], set[str]]:
    """Project a pain.001 twin into ISO element names in snake_case.

    Args:
        twin: The ISO JSON twin of the document.
        bindings: Unused: this face takes no side inputs (the engine
            refuses any).

    Returns:
        The projected message content and the set of source leaf paths
        it carries.

    Raises:
        FaceError: When the twin holds no pain.001 message.
    """
    message = twin.get("Document", {}).get(MESSAGE)
    if not isinstance(message, dict):
        raise FaceError(f"{FACE}: the twin holds no {MESSAGE} message")
    mapped: set[str] = set()
    payload = _project(message, MESSAGE, name_table()["names"], mapped)
    return payload, mapped
