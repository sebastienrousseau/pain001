# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The release preflight refuses a suite whose floors left the release.

The core releases first and every member follows at the same version,
each requiring ``pain001>=<that version>``. A floor recorded in
``pain001/suite.py`` that resolves to anything else must stop the core
before its tag exists, not surface in the nightly after a member ships.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import preflight_release  # noqa: E402

from pain001.suite import LOCKSTEP, SUITE, SuiteMember  # noqa: E402


def test_the_suite_floors_are_the_release() -> None:
    """Every member of the real suite is lockstep with this release."""
    assert preflight_release.suite_floor_problems("0.0.74") == []


def test_a_floor_below_the_release_blocks_it() -> None:
    """A recorded floor of 0.0.56 is not a 0.0.74 release."""
    members = [
        SUITE["pain001"],
        SUITE["pain001-mcp"],
        SuiteMember("pain001-loader-xlsx", "o/r", "Loader.", "0.0.56"),
    ]
    (problem,) = preflight_release.suite_floor_problems("0.0.74", members)
    assert problem == (
        "pain001-loader-xlsx floor is >=0.0.56, not the release 0.0.74"
    )


def test_an_explicit_floor_equal_to_the_release_passes() -> None:
    """The rule is the release version, however it is written down."""
    members = [SuiteMember("pain001-lsp", "o/r", "Server.", "0.0.74")]
    assert preflight_release.suite_floor_problems("0.0.74", members) == []


def test_the_core_has_no_floor_to_check() -> None:
    """The core does not depend on itself."""
    assert SUITE["pain001"].floor is None
    assert SUITE["pain001-mcp"].floor == LOCKSTEP
    assert (
        preflight_release.suite_floor_problems("0.0.74", [SUITE["pain001"]])
        == []
    )
