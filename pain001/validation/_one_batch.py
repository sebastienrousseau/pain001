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

"""Refuse, at validation time, the batches generation refuses.

Generation renders one PmtInf per file and refuses rows that disagree
on a column it renders there
(:func:`pain001.xml.batch_consistency.require_single_payment_information`).
Validation runs the same check on the rows as generation will see them,
so a file never passes ``validate`` and then fails ``generate``.
"""

from __future__ import annotations

from typing import Any

from pain001.data.loader import load_payment_data
from pain001.xml.batch_consistency import require_one_batch


def load_batch(
    data_file_path: str | list[dict[str, Any]] | dict[str, Any],
    message_type: str,
    identifier_checks: bool = True,
) -> list[dict[str, Any]]:
    """Load payment rows and refuse them unless they form one batch.

    Args:
        data_file_path: Path to the payment data, a list of rows or
            one row.
        message_type: The target message type.
        identifier_checks: If False, skip the IBAN, BIC and LEI checks.

    Returns:
        The loaded rows.

    A ``PaymentValidationError`` from the loader (an invalid identifier)
    or from :func:`pain001.xml.batch_consistency.require_one_batch`
    propagates unchanged.
    """
    data = load_payment_data(data_file_path, identifier_checks)
    require_one_batch(data, message_type)
    return data
