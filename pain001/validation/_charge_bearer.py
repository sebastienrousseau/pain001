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

"""The SEPA charge-bearer rule shared by the four SEPA profiles.

The EPC Customer-to-PSP Implementation Guidelines, 2025 Version 1.0
(issued 28 November 2024, effective 5 October 2025), give Charge Bearer
the SEPA usage rule 'Only "SLEV" is allowed.' in every SEPA scheme:
EPC132-08 (SCT) and EPC121-16 (SCT Inst), pain.001.001.09 indexes 2.75
and 2.98; EPC130-08 (SDD Core) and EPC131-08 (SDD B2B),
pain.008.001.08 indexes 2.68 and 2.99. The element is optional (0..1),
so an absent or empty value passes.
"""

from typing import Any

from pain001.validation._scheme_types import (
    SchemeValidationResult,
    SchemeViolation,
)


def check_charge_bearer(
    row: dict[str, Any], index: int, result: SchemeValidationResult
) -> None:
    """Require the charge bearer, when given, to be ``SLEV``.

    Args:
        row: The payment row.
        index: Zero-based row index.
        result: The result accumulator to append violations to.
    """
    raw = row.get("charge_bearer")
    value = "" if raw is None else str(raw).strip()
    if value and value.upper() != "SLEV":
        result.violations.append(
            SchemeViolation(
                rule="SEPA-CHRGBR",
                message=f"SEPA allows only charge_bearer SLEV (got {value})",
                index=index,
                field="charge_bearer",
            )
        )
