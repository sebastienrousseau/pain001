# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The suite policy, and the checker that enforces it.

Every test here uses stubbed metadata. A checker that needs the network
to be tested is a checker nobody runs, and a scheduled job that fails
on a PyPI blip teaches people to ignore it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from pain001.suite import CORE, SUITE, lockstep_members, plugin_members

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_suite_consistency import (  # noqa: E402
    _as_tuple,
    audit,
    core_floor,
    main,
)


class TestPolicy:
    """What the suite declares about itself."""

    def test_core_is_a_lockstep_member(self) -> None:
        """The core sets the number the others match."""
        assert SUITE[CORE].lockstep is True

    def test_every_member_is_split_into_exactly_one_group(self) -> None:
        """A member is lockstep or a plugin, never both or neither."""
        assert len(lockstep_members()) + len(plugin_members()) == len(SUITE)

    def test_wrappers_are_lockstep_and_loaders_are_not(self) -> None:
        """The distinction is the whole point of the module."""
        lockstep = {m.distribution for m in lockstep_members()}
        plugins = {m.distribution for m in plugin_members()}
        assert {"pain001-mcp", "pain001-lsp"} <= lockstep
        assert {"pain001-loader-xlsx", "pain001-loader-mt101"} <= plugins

    def test_membership_table_is_read_only(self) -> None:
        """Reference data a check trusts must not be reshapable."""
        with pytest.raises(TypeError):
            SUITE["pain001-rogue"] = SUITE[CORE]  # type: ignore[index]

    def test_every_member_carries_a_repository_and_summary(self) -> None:
        """The table feeds the README, so blanks would ship."""
        for member in SUITE.values():
            assert member.repository.startswith("sebastienrousseau/")
            assert member.summary.endswith(".")


class TestCoreFloor:
    """Parsing the declared dependency on the core."""

    @pytest.mark.parametrize(
        ("requires", "expected"),
        [
            # The shape the plugins actually publish: upper bound first.
            (["pain001<1,>=0.0.56"], "0.0.56"),
            (["pain001>=0.0.55"], "0.0.55"),
            (["pain001==0.0.60"], "0.0.60"),
            (["pain001~=0.0.55"], "0.0.55"),
            (["pain001[api]>=0.0.55"], "0.0.55"),
            # No lower bound is not a floor of zero.
            (["pain001<1"], None),
            (["openpyxl>=3.1"], None),
            ([], None),
            (None, None),
        ],
    )
    def test_floor_is_read_from_real_metadata_shapes(
        self, requires: list[str] | None, expected: str | None
    ) -> None:
        """An earlier hand-rolled scan silently returned None here.

        `pain001<1,>=0.0.56` puts the upper bound first, so scanning for
        the first `>=` found nothing and the check it feeds quietly did
        not run.
        """
        assert core_floor(requires) == expected

    def test_unparseable_metadata_is_skipped_not_fatal(self) -> None:
        """A scheduled job must not die on one malformed entry."""
        assert core_floor(["!!! not a requirement", "pain001>=0.0.55"]) == (
            "0.0.55"
        )


class TestVersionOrdering:
    """Comparison used by the reachability check."""

    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("0.0.60", (0, 0, 60)),
            ("1.2.3", (1, 2, 3)),
            ("0.0.60rc1", (0, 0, 60)),
            ("0.0", (0, 0)),
        ],
    )
    def test_versions_compare_numerically(
        self, version: str, expected: tuple[int, ...]
    ) -> None:
        """String comparison would put 0.0.9 above 0.0.60."""
        assert _as_tuple(version) == expected

    def test_ordering_is_numeric_not_lexical(self) -> None:
        """The bug this exists to avoid."""
        assert _as_tuple("0.0.60") > _as_tuple("0.0.9")


def _stub(monkeypatch: pytest.MonkeyPatch, table: dict[str, Any]) -> None:
    """Point the checker at fixed metadata instead of PyPI."""
    import check_suite_consistency as mod

    monkeypatch.setattr(mod, "fetch_metadata", lambda name: table.get(name))


def _member(version: str, floor: str | None = None) -> dict[str, Any]:
    """Build one stubbed PyPI ``info`` block."""
    requires = [f"pain001<1,>={floor}"] if floor else []
    return {"version": version, "requires_dist": requires}


class TestAudit:
    """The checks themselves."""

    def test_a_consistent_suite_reports_no_problems(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lockstep matched, floors reachable."""
        _stub(
            monkeypatch,
            {
                "pain001": _member("0.0.60"),
                "pain001-mcp": _member("0.0.60", "0.0.55"),
                "pain001-lsp": _member("0.0.60", "0.0.55"),
                "pain001-loader-xlsx": _member("0.1.0", "0.0.56"),
                "pain001-loader-mt101": _member("0.0.2", "0.0.55"),
            },
        )

        problems, report = audit()

        assert problems == []
        assert report["core"] == "0.0.60"

    def test_a_lockstep_member_left_behind_is_reported(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The drift that actually happened: lsp stuck at 0.0.54."""
        _stub(
            monkeypatch,
            {
                "pain001": _member("0.0.60"),
                "pain001-mcp": _member("0.0.60"),
                "pain001-lsp": _member("0.0.54"),
            },
        )

        problems, _ = audit()

        assert any("pain001-lsp is 0.0.54" in p for p in problems)

    def test_an_independently_versioned_plugin_is_not_drift(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """mt101 at 0.0.2 needing pain001>=0.0.55 is correct.

        An earlier version of this check compared a plugin's own version
        against the core floor and flagged this. It was measuring the
        wrong thing.
        """
        _stub(
            monkeypatch,
            {
                "pain001": _member("0.0.60"),
                "pain001-loader-mt101": _member("0.0.2", "0.0.55"),
            },
        )

        problems, _ = audit()

        assert problems == []

    def test_an_unreachable_floor_is_reported(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Requiring a core that was never published is uninstallable."""
        _stub(
            monkeypatch,
            {
                "pain001": _member("0.0.60"),
                "pain001-loader-xlsx": _member("0.1.0", "0.9.9"),
            },
        )

        problems, _ = audit()

        assert any("Nobody can install" in p for p in problems)

    def test_an_unpublished_member_is_recorded_not_flagged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A member that has never shipped is not drift."""
        _stub(
            monkeypatch,
            {"pain001": _member("0.0.60"), "pain001-mcp": None},
        )

        problems, report = audit()

        assert problems == []
        assert report["members"]["pain001-mcp"] == {"published": None}


class TestExitCode:
    """The schedule only works if failure is loud."""

    def test_consistent_suite_exits_zero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """A clean run says so and exits 0."""
        _stub(monkeypatch, {"pain001": _member("0.0.60")})

        assert main([]) == 0
        assert "Suite is consistent." in capsys.readouterr().out

    def test_inconsistent_suite_exits_non_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Otherwise the scheduled job is a report nobody opens."""
        _stub(
            monkeypatch,
            {
                "pain001": _member("0.0.60"),
                "pain001-lsp": _member("0.0.54"),
            },
        )

        assert main([]) == 1

    def test_json_output_is_machine_readable(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """`--json` feeds an issue body or a dashboard."""
        import json as _json

        _stub(monkeypatch, {"pain001": _member("0.0.60")})

        main(["--json"])

        assert _json.loads(capsys.readouterr().out)["core"] == "0.0.60"
