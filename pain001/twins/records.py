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

"""The records twin: a pain.001 document as the library's flat input rows.

The CSV pipeline renders a bundled template from flat records whose
columns the input JSON Schema names (``debtor_name``,
``creditor_account_IBAN`` …). The records twin reads those columns back
out of a document, one row per transaction, so any corpus file can be
regenerated through the pipeline, and it says exactly which element
paths the pipeline cannot carry: the **gap**.

Which column lands on which element is not written anywhere; it is
derived once per edition by rendering the template with sentinel values
and reading where each sentinel ends up. That keeps the mapping true to
the template the pipeline actually uses.
"""

from __future__ import annotations

import json
import re

# The Element type only; parsing is defused.
import xml.etree.ElementTree as ET  # nosec B405
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from defusedxml import ElementTree as defused_et
from jinja2 import select_autoescape
from jinja2.sandbox import SandboxedEnvironment

from pain001.twins.iso_json import _check, to_iso_json
from pain001.xml.generate_xml import (
    _FIELD_ALIASES,
    _load_trusted_template_source,
    _normalize_financial_fields,
)
from pain001.xml.message_registry import prepare_xml_data

INPUT_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
_ROWS = 2


@dataclass(frozen=True)
class RecordsTwin:
    """The rows, what they cannot carry, and what the input schema wants.

    Attributes:
        rows: One flat record per transaction of the first payment block.
        gap: Element paths present in the document that no column carries,
            relative to ``Document`` and without occurrence indexes.
        missing_required: Columns the edition's preparer requires that the
            document gave no value for; with any of these the pipeline
            cannot regenerate the file.
    """

    rows: list[dict[str, str]]
    gap: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)


def input_columns(version: str) -> tuple[list[str], list[str]]:
    """The pipeline's columns and the input schema's required columns.

    The universe is the input schema's properties plus the header of the
    bundled ``template.csv``: the older preparers require address and
    reference columns the schema does not list, and the sample carries
    them.
    """
    from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

    schema = json.loads(
        (INPUT_SCHEMA_DIR / f"{version}.schema.json").read_text(
            encoding="utf-8"
        )
    )
    columns = list(schema["properties"])
    sample = DEFAULT_TEMPLATE_REGISTRY.get_template(
        version
    ).template_path.parent
    header = (
        (sample / "template.csv").read_text(encoding="utf-8").splitlines()[0]
    )
    for name in header.split(","):
        name = name.strip()
        if name and name not in columns:
            columns.append(name)
    return columns, list(schema.get("required", []))


@cache
def preparer_required(version: str) -> tuple[str, ...]:
    """The columns the edition's preparer refuses to render without.

    Learned by asking the preparer to render an empty row and reading
    the names it lists, so the records twin judges against the gate the
    pipeline really applies rather than the input schema's list. A
    group of alternatives (an IBAN or an account number) is one entry,
    its names joined by ``|``.
    """
    from pain001.exceptions import PaymentValidationError

    try:
        prepare_xml_data([{}], version)
    except PaymentValidationError as exc:
        text = str(exc).split(". Provide", 1)[0]
        names: list[str] = []
        for part in text.split(":", 1)[1].split(";"):
            part = part.split(":", 1)[-1]
            for item in re.split(r",(?![^(]*\))", part):
                item = item.strip()
                if not item:
                    continue
                match = re.fullmatch(r"(\w+) \(or ([^)]+)\)", item)
                if match:
                    name = "|".join(
                        [match.group(1)]
                        + [a.strip() for a in match.group(2).split(",")]
                    )
                else:
                    name = item.split(" ", 1)[0]
                if name not in names:
                    names.append(name)
        return tuple(names)
    return ()  # pragma: no cover - every bundled preparer has a gate


def _sentinel(column: str, index: int, row: int) -> str:
    """A value the template accepts that no other column produces."""
    if column in ("payment_amount", "ctrl_sum"):
        return f"{100 + row}.{10 + index:02d}"
    if column == "nb_of_txs":
        return str(_ROWS)
    if column == "date":
        return f"2001-01-0{row + 1}T0{index % 10}:{index % 60:02d}:00"
    if column.endswith("_datetime"):
        return f"2003-{index % 12 + 1:02d}-0{row + 1}T{index % 24:02d}:00:00"
    if column.endswith("_date"):
        return f"2002-{index % 12 + 1:02d}-0{row + 1}"
    if column == "batch_booking":
        return "true"
    if column == "currency":
        return f"C{index:02d}"
    return f"S{index:02d}R{row}"


def _render(version: str, rows: list[dict[str, str]]) -> str:
    """Render the edition's template from rows, without validation."""
    from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

    template_path = DEFAULT_TEMPLATE_REGISTRY.get_template(
        version
    ).template_path
    data, count, total = _normalize_financial_fields([dict(r) for r in rows])
    context = prepare_xml_data(data, version)
    context["nb_of_txs"] = count
    if "payment_nb_of_txs" in context:
        context["payment_nb_of_txs"] = count
    if "ctrl_sum" in context:
        context["ctrl_sum"] = total
    env = SandboxedEnvironment(
        autoescape=select_autoescape(
            enabled_extensions=("xml",), default_for_string=True
        )
    )
    source = _load_trusted_template_source(str(template_path))
    return str(env.from_string(source).render(**context))


def _texts(xml: str) -> dict[str, list[str]]:
    """Every text and attribute value in the document, by path."""
    root = defused_et.fromstring(xml.encode("utf-8"))
    found: dict[str, list[str]] = {}

    def walk(element: ET.Element, path: str) -> None:
        """Collect the element's attribute and text values, then recurse."""
        tag = element.tag.split("}", 1)[-1]
        here = f"{path}/{tag}" if path else tag
        for name, value in element.attrib.items():
            if "}" not in name:
                found.setdefault(value, []).append(f"{here}/@{name}")
        text = (element.text or "").strip()
        if text:
            found.setdefault(text, []).append(here)
        for child in element:
            walk(child, here)

    walk(root, "")
    return found


#: Columns a template renders only when the preferred column is absent.
_ALTERNATES: dict[str, str] = {
    "debtor_account_number": "debtor_account_IBAN",
    "debtor_account_scheme": "debtor_account_IBAN",
    "debtor_account_scheme_proprietary": "debtor_account_scheme",
    "creditor_account_number": "creditor_account_IBAN",
    "creditor_account_scheme": "creditor_account_IBAN",
    "creditor_account_scheme_proprietary": "creditor_account_scheme",
    "initiator_id_scheme_proprietary": "initiator_id_scheme",
    "debtor_id_scheme_proprietary": "debtor_id_scheme",
    "local_instrument_proprietary": "local_instrument_code",
    "requested_execution_date": "requested_execution_datetime",
}
#: Values that make a template take its other branch for one column.
_EXTRA_RENDERS: dict[str, str] = {"creditor_reference_type": "SCOR"}


@cache
def column_paths(version: str) -> dict[str, tuple[str, ...]]:
    """Which element paths each input column renders to, per edition.

    Derived by rendering the template with a sentinel per column and
    reading the sentinels back. Columns the template never renders map
    to nothing, and that is the input side of the gap.

    Args:
        version: A bundled pain.001 edition.

    Returns:
        Column to paths (relative to ``Document``, no indexes). A
        column can land on more than one element.
    """
    _check(version)
    columns, _ = input_columns(version)
    rows = [
        {c: _sentinel(c, i, r) for i, c in enumerate(columns)}
        for r in range(_ROWS)
    ]
    texts = _texts(_render(version, rows))
    # a second rendering without the preferred columns reveals where the
    # alternates land (an account number instead of an IBAN)
    for alternate in _ALTERNATES:
        if alternate not in columns:
            continue
        # drop the whole chain of preferred columns above this alternate
        removed: set[str] = set()
        current = alternate
        while current in _ALTERNATES:
            current = _ALTERNATES[current]
            removed.add(current)
        sparse = [
            {c: v for c, v in r.items() if c not in removed} for r in rows
        ]
        for value, paths in _texts(_render(version, sparse)).items():
            texts.setdefault(value, []).extend(paths)
    mapping: dict[str, set[str]] = {c: set() for c in columns}
    for column, other in _EXTRA_RENDERS.items():
        if column not in columns:
            continue
        variant = [dict(r, **{column: other}) for r in rows]
        for value, paths in _texts(_render(version, variant)).items():
            if value.startswith(other):
                mapping[column].update(paths)
    for value, paths in texts.items():
        for index, column in enumerate(columns):
            if value == _sentinel(column, index, 0) or (
                column == "payment_amount"
                and value.endswith(f".{10 + index:02d}")
            ):
                mapping[column].update(
                    p for p in paths if not p.endswith("NbOfTxs")
                )
    # the pipeline computes the totals itself: they land on every
    # NbOfTxs and CtrlSum the template renders
    for paths in texts.values():
        for path in paths:
            if path.endswith("/NbOfTxs") and "nb_of_txs" in mapping:
                mapping["nb_of_txs"].add(path)
            if path.endswith("/CtrlSum") and "ctrl_sum" in mapping:
                mapping["ctrl_sum"].add(path)
    # the boolean cannot be unique: find the element whose text flips
    if "batch_booking" in columns:
        flipped = [dict(r, batch_booking="false") for r in rows]
        before = _texts(_render(version, rows)).get("true", [])
        after = _texts(_render(version, flipped)).get("false", [])
        mapping["batch_booking"] = set(before) & set(after)
    # an alias the pipeline folds into its canonical column lands there
    for column in columns:
        alias = _FIELD_ALIASES.get(column)
        if not mapping.get(column) and alias in mapping:
            mapping[column] = set(mapping[alias])
    return {c: tuple(sorted(mapping.get(c, ()))) for c in columns}


def _read(twin: dict[str, Any], path: str, tx_index: int) -> str | None:
    """The value at ``path`` for transaction ``tx_index`` of the first block."""
    node: Any = twin["Document"]
    for step in path.split("/"):
        if step.startswith("@"):
            return node.get("Ccy") if isinstance(node, dict) else None
        if not isinstance(node, dict) or step not in node:
            return None
        node = node[step]
        if step == "CdtTrfTxInf" and isinstance(node, list):
            node = node[tx_index] if tx_index < len(node) else None
        elif isinstance(node, list):
            node = node[0]
        if node is None:
            return None
    if isinstance(node, dict):
        return node.get("amt")
    return str(node) if node is not None else None


def _leaf_paths(twin: dict[str, Any]) -> set[str]:
    """Leaf paths present in a twin, relative to Document, no indexes."""
    found: set[str] = set()

    def walk(node: Any, path: str) -> None:
        """Collect leaf paths, treating an amount object as one leaf."""
        if isinstance(node, list):
            for item in node:
                walk(item, path)
        elif isinstance(node, dict):
            if set(node) == {"amt", "Ccy"}:
                found.add(path)
                found.add(f"{path}/@Ccy")
                return
            for key, value in node.items():
                walk(value, f"{path}/{key}" if path else key)
        else:
            found.add(path)

    walk(twin["Document"], "")
    return found


def to_records(xml: str, version: str) -> RecordsTwin:
    """The records twin of a pain.001 document.

    Args:
        xml: The document.
        version: Its edition.

    Returns:
        The :class:`RecordsTwin`: rows, gap and missing required columns.
    """
    twin = to_iso_json(xml, version)
    paths = column_paths(version)
    columns, _ = input_columns(version)
    message = twin["Document"]["CstmrCdtTrfInitn"]
    blocks = message["PmtInf"]
    transactions = blocks[0]["CdtTrfTxInf"]
    rows: list[dict[str, str]] = []
    collapsed: set[str] = set()
    for tx_index in range(len(transactions)):
        row: dict[str, str] = {}
        for column in columns:
            chosen: str | None = None
            for path in paths[column]:
                value = _read(twin, path.split("/", 1)[1], tx_index)
                if value is None:
                    continue
                if chosen is None:
                    row[column] = value
                    chosen = value
                elif value != chosen:
                    # one column feeds two elements; the pipeline cannot
                    # give them different values
                    collapsed.add(
                        f"{path.split('/', 1)[1]} (collapsed into {column})"
                    )
        rows.append(row)
    carried = {p.split("/", 1)[1] for ps in paths.values() for p in ps}
    gap = sorted((_leaf_paths(twin) - carried) | collapsed)
    if len(blocks) > 1:
        gap.append(f"CstmrCdtTrfInitn/PmtInf (occurrences 2 to {len(blocks)})")
    present = set().union(*(set(r) for r in rows)) if rows else set()
    missing = [
        group
        for group in preparer_required(version)
        if not any(
            c in present or _FIELD_ALIASES.get(c) in present
            for c in group.split("|")
        )
    ]
    return RecordsTwin(rows, gap, missing)


__all__ = [
    "INPUT_SCHEMA_DIR",
    "RecordsTwin",
    "column_paths",
    "input_columns",
    "preparer_required",
    "to_records",
]
