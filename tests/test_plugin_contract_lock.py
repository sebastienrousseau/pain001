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

"""The plugin contract cannot be locked at 1.0 without external review.

Issue #179 required that an independent contributor build a plugin
against the documented Protocols before the contract is locked. That is
a condition on locking v1.0, so it is held here: ``docs/plugins.md``
records the review, and a contract major of 1 or more with no review
recorded fails the suite.
"""

from __future__ import annotations

import re
from pathlib import Path

from pain001.plugins._version import PAIN001_API_VERSION

PLUGINS_DOC = Path(__file__).resolve().parent.parent / "docs" / "plugins.md"
_RECORD = re.compile(r"^External review: (?P<value>.+)$", re.MULTILINE)


def _recorded_review(text: str) -> str | None:
    """Return the recorded external review, or None when none is recorded."""
    match = _RECORD.search(text)
    if match is None:
        return None
    value = match.group("value").strip()
    return None if value.lower().startswith("none") else value


def test_the_plugin_doc_records_the_external_review_state() -> None:
    """The record line exists, so the gate below has something to read."""
    assert _RECORD.search(PLUGINS_DOC.read_text(encoding="utf-8")), (
        "docs/plugins.md has no 'External review:' line"
    )


def test_a_v1_contract_needs_a_recorded_external_review() -> None:
    """Locking the contract at major 1 requires the review on record."""
    if PAIN001_API_VERSION[0] >= 1:
        assert _recorded_review(PLUGINS_DOC.read_text(encoding="utf-8")), (
            "the plugin contract is at major "
            f"{PAIN001_API_VERSION[0]} but docs/plugins.md records no "
            "independent external review (issue #179)"
        )


def test_the_record_parser() -> None:
    """``none`` in any form means no review; anything else is a record."""
    assert _recorded_review("External review: none yet\n") is None
    assert _recorded_review("no record line\n") is None
    assert _recorded_review("External review: @someone, 2027-01-01\n") == (
        "@someone, 2027-01-01"
    )
