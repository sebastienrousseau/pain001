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

"""The validation ladder for one built corpus file (ADR-0003, L0 to L3).

* **L0** the edition's XSD (the builder already refuses a failure);
* **L1** the MDR cross-element rules;
* **L2** the scheme and rail profiles the scenario lists, run on the
  file's row projection;
* **L3** the overlays that apply to the scenario or its family.

:func:`run_ladder` returns a JSON-ready record the build writes into the
file's provenance sidecar and the gate re-checks; :func:`ladder_passes`
says whether any rung produced an error-severity finding.
"""

from __future__ import annotations

from typing import Any

from pain001.corpus.registry import Scenario
from pain001.corpus.rules.mdr import evaluate_mdr
from pain001.corpus.rules.overlays import Overlay, evaluate, load_overlays
from pain001.corpus.rules.projection import rows_from_xml
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.validation.schemes import validate_scheme
from pain001.xml.validate_via_xsd import collect_xsd_validation_errors


def run_ladder(
    scenario: Scenario,
    version: str,
    xml: str,
    overlays: list[Overlay] | None = None,
) -> dict[str, Any]:
    """Run L0 to L3 on one built file.

    Args:
        scenario: The scenario the file was built from.
        version: The edition.
        xml: The built document.
        overlays: The overlay pool; defaults to ``scenarios/overlays``.

    Returns:
        ``{"xsd": ..., "mdr": ..., "profiles": {...}, "overlays": {...}}``
        with error and warning counts and the first messages of each.
    """
    xsd = str(DEFAULT_TEMPLATE_REGISTRY.get_template(version).xsd_path)
    xsd_errors = collect_xsd_validation_errors(xml, xsd, max_errors=5)
    mdr = evaluate_mdr(xml)
    rows = rows_from_xml(xml)
    profiles: dict[str, Any] = {}
    for name in scenario.profiles:
        result = validate_scheme(rows, name)
        errors = [v for v in result.violations if v.severity == "error"]
        warnings = [v for v in result.violations if v.severity != "error"]
        profiles[name] = {
            "errors": len(errors),
            "warnings": len(warnings),
            "findings": [
                f"{v.rule}: {v.message}" for v in result.violations[:5]
            ],
        }
    pool = load_overlays() if overlays is None else overlays
    wanted = scenario.overlays
    applied: dict[str, Any] = {}
    for overlay in pool:
        if wanted is None:
            if not overlay.applies(scenario.id, scenario.family):
                continue
        elif overlay.overlay_id not in wanted:
            continue
        findings = evaluate(overlay, xml)
        applied[overlay.overlay_id] = {
            "errors": sum(f.severity == "error" for f in findings),
            "warnings": sum(f.severity != "error" for f in findings),
            "findings": [f"{f.code}: {f.message}" for f in findings[:5]],
        }
    return {
        "xsd": {"errors": len(xsd_errors), "findings": xsd_errors},
        "mdr": {
            "errors": len(mdr),
            "findings": [f"{f.rule_id} at {f.path}" for f in mdr[:5]],
        },
        "profiles": profiles,
        "overlays": applied,
    }


def ladder_passes(record: dict[str, Any]) -> bool:
    """True when no rung of a :func:`run_ladder` record has an error."""
    if record["xsd"]["errors"] or record["mdr"]["errors"]:
        return False
    for rung in ("profiles", "overlays"):
        if any(entry["errors"] for entry in record[rung].values()):
            return False
    return True


__all__ = ["ladder_passes", "run_ladder"]
