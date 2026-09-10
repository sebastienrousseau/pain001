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
the schema inventory and coverage yardstick, the scenario loader and
the version-aware builder with its identifier factories, the shipped
market files under ``data/market`` and, under ``rules``, the vendored
ISO external code sets; the MDR rules, overlays and the coverage sets
follow in their own workstreams.
"""

from pain001.corpus.builder import (
    BuildError,
    BuildReport,
    BuildResult,
    build,
    build_all,
)
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
from pain001.corpus.registry import (
    Scenario,
    ScenarioError,
    load_scenario,
    load_scenarios,
    scenario_from,
)

__all__ = [
    "BuildError",
    "BuildReport",
    "BuildResult",
    "ChoiceEntry",
    "CoverageReport",
    "ElementEntry",
    "Inventory",
    "Scenario",
    "ScenarioError",
    "build",
    "build_all",
    "build_inventory",
    "coverage",
    "inventory_for",
    "load_scenario",
    "load_scenarios",
    "present_paths",
    "scenario_from",
]
