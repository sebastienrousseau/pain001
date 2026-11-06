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

"""Indexed leaf paths of an ISO JSON twin, and a reader that records them.

A loss report is only honest if every occurrence of a repeated element
has its own path: ``PmtInf[0]/CdtTrfTxInf[1]/Amt/InstdAmt`` is a
different leaf from ``PmtInf[0]/CdtTrfTxInf[0]/Amt/InstdAmt``. Paths are
relative to ``Document`` and carry an index on every array item. An
amount object (``{"amt", "Ccy"}``) is one leaf plus its ``/@Ccy``.
"""

from __future__ import annotations

from typing import Any

AMOUNT_KEYS = frozenset({"amt", "Ccy"})


def is_amount(node: Any) -> bool:
    """True when ``node`` is a twin amount object ``{"amt", "Ccy"}``."""
    return isinstance(node, dict) and set(node) == AMOUNT_KEYS


def join(path: str, key: str) -> str:
    """Append ``key`` to ``path`` with a slash, or start a path."""
    return f"{path}/{key}" if path else key


def leaf_paths(twin: dict[str, Any]) -> set[str]:
    """Every leaf path in the twin's message, indexed per array item."""
    found: set[str] = set()

    def walk(node: Any, path: str) -> None:
        """Collect the leaves under ``node``."""
        if isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")
        elif is_amount(node):
            found.update((path, f"{path}/@Ccy"))
        elif isinstance(node, dict):
            for key, value in node.items():
                walk(value, join(path, key))
        else:
            found.add(path)

    walk(twin.get("Document", {}), "")
    return found


class Reader:
    """Read values from a twin and record each leaf path that was used."""

    def __init__(self) -> None:
        self.mapped: set[str] = set()

    def mark(self) -> frozenset[str]:
        """A snapshot of the recorded leaves, for :meth:`rollback`."""
        return frozenset(self.mapped)

    def rollback(self, mark: frozenset[str]) -> None:
        """Forget leaves recorded since ``mark``: their value was dropped."""
        self.mapped = set(mark)

    def text(self, node: Any, path: str, *keys: str) -> str | None:
        """The text leaf at ``keys`` below ``node``, recorded, or ``None``.

        Args:
            node: The twin node to start from.
            path: The indexed path of ``node``.
            *keys: Element tags to descend through; each must be a
                single (non-repeatable) element.

        Returns:
            The leaf's text, or ``None`` when any step is missing or the
            target is not a text leaf.
        """
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return None
            node, path = node[key], join(path, key)
        if not isinstance(node, str):
            return None
        self.mapped.add(path)
        return node

    def amount(self, node: Any, path: str) -> tuple[str, str] | None:
        """The ``(amount, currency)`` of an amount object, recorded."""
        if not is_amount(node):
            return None
        self.mapped.update((path, f"{path}/@Ccy"))
        return node["amt"], node["Ccy"]

    def texts(self, node: Any, path: str, key: str) -> list[str]:
        """Every text item of the repeatable element ``key``, recorded."""
        items = node.get(key) if isinstance(node, dict) else None
        if not isinstance(items, list):
            return []
        out = []
        for index, item in enumerate(items):
            if isinstance(item, str):
                self.mapped.add(f"{join(path, key)}[{index}]")
                out.append(item)
        return out
