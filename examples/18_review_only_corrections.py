# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Suggest text corrections without applying them or editing financial fields."""

from copy import deepcopy

from pain001.validation.corrections import suggest_record_fix


def main() -> None:
    """Check the candidate, protected-field refusal and input immutability."""
    row = {"initiator_name": "Café", "payment_amount": "100.00"}
    original = deepcopy(row)
    finding = {"field": "initiator_name", "rule": "CHARSET"}
    result = suggest_record_fix(row, finding)
    assert result == suggest_record_fix(row, finding)
    patch = result["patches"][0]
    assert (patch["op"], patch["path"], patch["value"]) == (
        "replace",
        "/initiator_name",
        "Cafe",
    )
    refused = suggest_record_fix(
        row, {"field": "payment_amount", "rule": "CHARSET"}
    )
    assert refused == {
        "patches": [],
        "cannot_autofix": "protected_financial_field",
    }
    assert row == original
    print(
        "Deterministic, review-only suggestion and financial-field refusal: passed"
    )


if __name__ == "__main__":
    main()
