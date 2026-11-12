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


def test_the_tag_message_is_the_lowercase_project_name() -> None:
    """The family's tags read ``pain001 v<version>``, not ``Pain001``.

    The preflight creates the tag with ``--tag`` and inspect_release
    verifies it against ``--project``; both must spell the project the
    way the release invariants do, or the check would pass a tag the
    release page then contradicts.
    """
    source = Path(preflight_release.__file__).read_text(encoding="utf-8")
    assert 'msg = f"pain001 v{version}"' in source
    assert '"Pain001"' not in source


def test_the_release_workflow_titles_the_release_by_project() -> None:
    """A GitHub release is titled ``pain001 <version>``, not ``v<version>``.

    softprops/action-gh-release titles a release after its tag unless
    ``name`` is set, which produced exactly the title the family's
    release invariants forbid.
    """
    workflow = (
        Path(__file__).resolve().parent.parent / ".github/workflows/ci.yml"
    ).read_text(encoding="utf-8")
    assert "name: pain001 ${{ needs.build.outputs.version }}" in workflow
    assert "version: ${{ steps.release_notes.outputs.version }}" in workflow
    assert '"version=$TAG_VERSION" >> "$GITHUB_OUTPUT"' in workflow
    assert "--project Pain001" not in workflow


def test_the_readme_names_the_version_being_released() -> None:
    """Both README release statements follow the version sources."""
    from pain001.constants import VERSION

    assert preflight_release.readme_release_problems(VERSION) == []


def test_a_stale_readme_blocks_the_release() -> None:
    """The 0.0.81 README, still announcing 0.0.80, fails both checks."""
    stale = (
        "> **Latest release: v0.0.80**: ISO 20022 files\n"
        "... The current release\nis 0.0.80; publication requires ..."
    )
    assert preflight_release.readme_release_problems("0.0.81", stale) == [
        "README.md lacks 'Latest release: v0.0.81'",
        "README.md lacks 'The current release is 0.0.81;'",
    ]
    fixed = stale.replace("0.0.80", "0.0.81")
    assert preflight_release.readme_release_problems("0.0.81", fixed) == []


def test_the_action_examples_pin_the_version_being_released() -> None:
    """action.yml and docs/usage.rst show ``pain001@v<version>``."""
    from pain001.constants import VERSION

    assert preflight_release.action_pin_problems(VERSION) == []


def test_a_stale_action_pin_blocks_the_release() -> None:
    """The 0.0.83 manual, still pinning @v0.0.82, fails the check."""
    texts = {
        "docs/usage.rst": "- uses: sebastienrousseau/pain001@v0.0.82\n",
        "action.yml": "#   - uses: sebastienrousseau/pain001@v0.0.83\n",
    }
    assert preflight_release.action_pin_problems("0.0.83", texts) == [
        "docs/usage.rst pins sebastienrousseau/pain001@v0.0.82, not @v0.0.83"
    ]
    assert preflight_release.action_pin_problems(
        "0.0.83", {"action.yml": "no example here\n"}
    ) == ["action.yml has no sebastienrousseau/pain001@v... example"]


_ANNOUNCED = """## [0.0.83] - Unreleased

### Changed

- Something.

## [0.0.82] - 2026-11-09

### Announced

- 0.0.83 writes `<X>` instead of `<Y>`.

## [0.0.81] - 2026-11-08
"""


def test_unchanged_golden_files_need_no_notice() -> None:
    """Output that did not change needs no announcement."""
    bare = _ANNOUNCED.replace("### Announced", "### Fixed")
    assert (
        preflight_release.breaking_notice_problems("0.0.83", bare, False) == []
    )


def test_a_golden_change_announced_a_release_ahead_passes() -> None:
    """The previous release's ``### Announced`` section is the notice."""
    assert (
        preflight_release.breaking_notice_problems("0.0.83", _ANNOUNCED, True)
        == []
    )


def test_an_unannounced_golden_change_blocks_the_release() -> None:
    """0.0.82 changed .04 to .08 output with no notice in 0.0.81."""
    bare = _ANNOUNCED.replace("### Announced", "### Fixed")
    (problem,) = preflight_release.breaking_notice_problems(
        "0.0.83", bare, True
    )
    assert "0.0.82" in problem and "### Announced" in problem


def test_a_recorded_exception_passes() -> None:
    """An exception names itself and the ADR that records why."""
    bare = _ANNOUNCED.replace("### Announced", "### Fixed")
    owned = bare.replace(
        "- Something.",
        "- Something. This was not announced a\n  release ahead as the "
        "policy asks; [ADR-0012](docs/adr/0012-x.md) records why.",
    )
    assert (
        preflight_release.breaking_notice_problems("0.0.83", owned, True) == []
    )
    unlinked = bare.replace(
        "- Something.", "- Something. Not announced a release ahead."
    )
    assert preflight_release.breaking_notice_problems("0.0.83", unlinked, True)


def test_the_first_release_has_nothing_to_announce_from() -> None:
    """With no earlier section there is no previous release to check."""
    only = "## [0.0.1] - 2023-01-01\n\n- First.\n"
    assert (
        preflight_release.breaking_notice_problems("0.0.1", only, True) == []
    )


def test_0_0_82_records_its_exception() -> None:
    """The real CHANGELOG: 0.0.82 regenerated golden files unannounced."""
    changelog = (
        Path(__file__).resolve().parent.parent / "CHANGELOG.md"
    ).read_text(encoding="utf-8")
    assert (
        preflight_release.breaking_notice_problems("0.0.82", changelog, True)
        == []
    )
