# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The bundled rulebooks judge every pain.001 version, not only .03.

They bind ``pain:`` to the pain.001.001.03 namespace. Until 0.0.82 a
.04 to .13 document matched no rule context at all, so every rulebook
evaluated nothing and reported it valid: a .09 file paying in USD
passed ``--schematron sepa``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pain001.constants import TEMPLATES_DIR
from pain001.schematron import validate_schematron

PAIN001 = [f"pain.001.001.{n:02d}" for n in range(3, 14)]


def _sample(message_type: str) -> str:
    return (TEMPLATES_DIR / message_type / f"{message_type}.xml").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("message_type", PAIN001)
def test_the_sepa_rulebook_evaluates_every_pain001_version(
    message_type: str,
) -> None:
    result = validate_schematron(_sample(message_type), "sepa")
    assert result.rules_evaluated > 0


@pytest.mark.parametrize(
    "message_type", ["pain.001.001.03", "pain.001.001.09"]
)
def test_a_non_euro_payment_fails_sepa_in_any_version(
    message_type: str,
) -> None:
    xml = _sample(message_type).replace('Ccy="EUR"', 'Ccy="USD"')
    result = validate_schematron(xml, "sepa")
    assert not result.is_valid
    assert "EPC-SCT-001" in {v.rule_id for v in result.violations}


def test_another_message_family_is_not_rebound() -> None:
    xml = _sample("pain.008.001.08")
    result = validate_schematron(xml, "sepa")
    assert result.rules_evaluated == 0


def test_a_document_without_a_namespace_keeps_the_rulebook_binding(
    tmp_path: Path,
) -> None:
    result = validate_schematron("<Document/>", "sepa")
    assert result.rules_evaluated == 0
