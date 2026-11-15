# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Element paths through arrays, in errors and in boolean decoding.

The ISO JSON twin carries repeated blocks as arrays. A path computed
for an item of an array must still be the element's path, because it
decides which values are booleans and it is what an error names.
"""

from __future__ import annotations

import copy

import pytest

from pain001.corpus import get_file
from pain001.corpus.rules import external_codes
from pain001.twins import TwinError, from_iso_json, iso_json, to_iso_json

CHAPS = ("gb.chaps.property-purchase", "pain.001.001.09")


def _twin() -> dict[str, object]:
    """The CHAPS twin, with its one payment block in an array."""
    return to_iso_json(get_file(*CHAPS), CHAPS[1])


def _block(twin: dict[str, object]) -> dict[str, object]:
    """The first payment block of a twin."""
    document = twin["Document"]
    assert isinstance(document, dict)
    blocks = document["CstmrCdtTrfInitn"]["PmtInf"]
    assert isinstance(blocks, list)
    block: dict[str, object] = blocks[0]
    return block


def test_xsi_and_namespace_hints_carry_no_data() -> None:
    """``@xsi:`` and ``@xmlns`` keys are dropped from simple content."""
    for hint in ("@xsi:type", "@xmlns", "@xmlns:x"):
        node = {"$": "x", hint: "y"}
        assert iso_json._encode_node(node, "E", frozenset()) == "x"


def test_attribute_error_names_the_element_inside_an_array() -> None:
    """A refused attribute on an array item is reported at its path."""
    with pytest.raises(TwinError) as caught:
        iso_json._encode_node([{"$": "x", "@Other": "y"}], "A/B", frozenset())
    assert str(caught.value) == "A/B: attributes ['@Other'] have no twin form"


def test_boolean_forms_in_a_block_array_are_decoded() -> None:
    """``1`` under PmtInf[0] is a boolean and comes back as ``true``."""
    twin = _twin()
    _block(twin)["BtchBookg"] = "1"
    xml = from_iso_json(twin, CHAPS[1])
    assert "<BtchBookg>true</BtchBookg>" in xml


def test_bad_boolean_in_a_block_array_names_its_path() -> None:
    """The error gives the element path, not the array's position."""
    twin = _twin()
    _block(twin)["BtchBookg"] = "yes"
    with pytest.raises(TwinError) as caught:
        from_iso_json(twin, CHAPS[1])
    assert str(caught.value) == (
        "CstmrCdtTrfInitn/PmtInf/BtchBookg: 'yes' is not a boolean"
    )


def test_two_blocks_keep_their_transactions_as_arrays() -> None:
    """Each block of a two-block document still has an array of transfers."""
    twin = _twin()
    second = copy.deepcopy(_block(twin))
    second["PmtInfId"] = "SECOND"
    document = twin["Document"]
    assert isinstance(document, dict)
    document["CstmrCdtTrfInitn"]["PmtInf"].append(second)
    back = to_iso_json(from_iso_json(twin, CHAPS[1]), CHAPS[1])
    blocks = back["Document"]["CstmrCdtTrfInitn"]["PmtInf"]
    assert [b["PmtInfId"] for b in blocks] == ["CHAPS-20260912-001", "SECOND"]
    assert all(isinstance(b["CdtTrfTxInf"], list) for b in blocks)
    assert all(isinstance(b["CdtTrfTxInf"][0]["Cdtr"], dict) for b in blocks)


def test_a_twin_needs_exactly_the_document_key() -> None:
    """Any other root is refused with the same plain message."""
    docs: list[dict[str, object]] = [
        {},
        {"document": {}},
        {"Document": {}, "x": 1},
    ]
    for doc in docs:
        with pytest.raises(TwinError) as caught:
            from_iso_json(doc, CHAPS[1])
        assert str(caught.value) == (
            "a twin is an object with the single key 'Document'"
        )


def test_sets_without_codes_are_only_the_empty_ones() -> None:
    """Twenty-three sets publish no codes; the service levels do."""
    empty = external_codes.sets_without_codes()
    assert len(empty) == 23
    assert empty[0] == "ExternalBankTransactionDomain1Code"
    assert "ExternalServiceLevel1Code" not in empty
    assert "ExternalPurpose1Code" not in empty
