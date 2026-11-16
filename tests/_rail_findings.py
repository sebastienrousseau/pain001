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

"""Shared rows and a findings helper for the rail-findings tests.

Each row is validated twice by a freshly constructed profile, so the
row index and the rail constructor are checked along with the findings.
"""

from __future__ import annotations

from typing import Any

from pain001.validation import rails

Finding = tuple[str, str | None, str, str]

GB = {
    "payment_currency": "GBP",
    "payment_amount": "100.00",
    "service_level_code": "URGP",
    "creditor_agent_clearing_system": "GBDSC",
    "creditor_agent_member_id": "309634",
    "creditor_account_id": "12345678",
    "end_to_end_id": "REF-1",
}
SWISS = {
    "payment_currency": "CHF",
    "creditor_account_IBAN": "CH4431999123000889012",
    "creditor_reference": "210000000003139471430009017",
    "creditor_reference_type": "QRR",
}
SWISS_PLAIN_IBAN = "CH9300762011623852957"
BACS_DD = {
    "payment_method": "DD",
    "payment_currency": "GBP",
    "debtor_agent_clearing_system": "GBDSC",
    "debtor_agent_member_id": "040004",
    "debtor_account_id": "12345678",
    "mandate_id": "DDI-000123",
    "sequence_type": "RCUR",
    "creditor_id": "123456",
}


def findings(
    name: str, row: dict[str, Any], **overrides: Any
) -> list[Finding]:
    """Validate ``row`` (with overrides; ``None`` drops a key) at two indexes.

    The row is validated as rows 0 and 1 by a freshly constructed
    profile; the findings of both rows must agree and each must carry its
    own index. Returns the findings of one row.
    """
    merged = {**row, **overrides}
    for key, value in overrides.items():
        if value is None:
            merged.pop(key)
    result = rails.RailProfile(rails.rail(name)).validate([merged, merged])
    assert result.profile == name
    by_index: dict[int, list[Finding]] = {0: [], 1: []}
    for v in result.violations:
        by_index[v.index].append((v.rule, v.field, v.severity, v.message))
    assert by_index[0] == by_index[1]
    return by_index[1]
