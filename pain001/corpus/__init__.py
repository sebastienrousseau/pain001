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

"""The example corpus engine (ADR-0003).

This package grows over the 0.0.67 to 0.0.69 releases. Today it holds
the schema inventory and coverage yardstick and, under ``rules``, the
vendored ISO external code sets; the scenario builder, the identifier
factories, the MDR rules and the shipped corpus data follow in their
own workstreams.
"""

from pain001.corpus.inventory import (
    ChoiceEntry,
    CoverageReport,
    ElementEntry,
    Inventory,
    build_inventory,
    coverage,
    inventory_for,
    present_paths,
)

__all__ = [
    "ChoiceEntry",
    "CoverageReport",
    "ElementEntry",
    "Inventory",
    "build_inventory",
    "coverage",
    "inventory_for",
    "present_paths",
]
