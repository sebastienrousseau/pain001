# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Tests for scripts/release_notes.py, the release body composer.

Vendored byte-identical in every pain001 suite repository, with the
script it tests; change both in pain001 and copy them out. ``gh`` is
replaced by a fake that answers from a table and records its calls, so
nothing here touches the network.
"""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "release_notes", ROOT / "scripts" / "release_notes.py"
)
assert _SPEC is not None and _SPEC.loader is not None
rn: Any = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rn)

REPO = "owner/demo"
NOTE = """<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# demo v0.0.2

## Highlights ⭐️

* **One**: the first highlight,
  wrapped onto a second line.
* **Two**: the second highlight.

## Details

* Not a highlight.
"""
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


class FakeGh:
    """Answers ``gh`` calls from a table keyed by the joined arguments."""

    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers = answers
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> str:
        self.calls.append(list(args))
        key = " ".join(args)
        for prefix, answer in self.answers.items():
            if key.startswith(prefix):
                if isinstance(answer, str):
                    return answer
                return json.dumps(answer)
        raise AssertionError(f"unexpected gh call: {key}")


def _commit(
    sha: str,
    subject: str,
    login: str | None = "dev",
) -> dict[str, Any]:
    return {
        "sha": sha,
        "html_url": f"https://github.com/{REPO}/commit/{sha}",
        "commit": {"message": f"{subject}\n\nbody"},
        "author": {"login": login} if login else None,
    }


def _pr(number: int, title: str, merged: bool = True) -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "user": {"login": "dev"},
        "html_url": f"https://github.com/{REPO}/pull/{number}",
        "merged_at": "2026-11-07T00:00:00Z" if merged else None,
    }


def _fake(**overrides: Any) -> FakeGh:
    answers: dict[str, Any] = {
        f"release list -R {REPO}": [
            {"tagName": "v0.0.2", "isDraft": False},
            {"tagName": "v0.0.1", "isDraft": False},
            {"tagName": "v0.0.0", "isDraft": False},
        ],
        f"api repos/{REPO}/compare/v0.0.1...v0.0.2": {
            "commits": [
                _commit("c1", "feat: a change"),
                _commit("c2", "Merge pull request #7 from owner/feat"),
            ]
        },
        f"api repos/{REPO}/commits/c1/pulls": [_pr(7, "feat: the release")],
        f"api repos/{REPO}/commits/c2/pulls": [],
        f"release view v0.0.2 -R {REPO} --json assets": {
            "assets": [
                {"name": "b.tar.gz", "digest": f"sha256:{DIGEST_B}"},
                {"name": "a.whl", "digest": f"sha256:{DIGEST_A}"},
            ]
        },
        f"release edit v0.0.2 -R {REPO}": "",
    }
    answers.update(overrides)
    return FakeGh(answers)


def _tree(tmp_path: Path, heading: str, note: str | None = NOTE) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.0.2"\n', encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(
        f"# Changelog\n\n{heading}\n\n- A change.\n", encoding="utf-8"
    )
    if note is not None:
        (tmp_path / "releases").mkdir()
        path = tmp_path / "releases" / "v0.0.2.md"
        path.write_text(note, encoding="utf-8")
    return tmp_path


def test_highlights_join_wrapped_lines_and_stop_at_a_section() -> None:
    assert rn.highlights(NOTE) == [
        "* **One**: the first highlight, wrapped onto a second line.",
        "* **Two**: the second highlight.",
    ]


@pytest.mark.parametrize("count", [0, 1, 5])
def test_highlights_must_number_two_to_four(count: int) -> None:
    bullets = "".join(f"* **H{i}**: text.\n" for i in range(count))
    with pytest.raises(rn.ReleaseNotesError, match=f"found {count}"):
        rn.highlights(f"## Highlights ⭐️\n\n{bullets}")


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        (["v0.0.9", "v0.0.10", "v0.0.11", "v0.1.0"], "v0.0.10"),
        (["v0.0.11", "nightly", "v0.0.10-rc1"], None),
        ([], None),
    ],
)
def test_previous_tag_is_the_highest_release_below(
    tags: list[str], expected: str | None
) -> None:
    assert rn.previous_tag(tags, "v0.0.11") == expected


def test_compose_writes_the_family_shape() -> None:
    fake = _fake()
    body = rn.compose(REPO, "v0.0.2", NOTE, fake)
    assert body == (
        "## Highlights ⭐️\n\n"
        "* **One**: the first highlight, wrapped onto a second line.\n"
        "* **Two**: the second highlight.\n\n"
        "## What's Changed\n\n"
        f"* feat: the release by @dev in https://github.com/{REPO}/pull/7\n\n"
        "## Checksums\n\n"
        "SHA-256 of every asset attached to this release:\n\n"
        "```text\n"
        f"{DIGEST_A}  a.whl\n"
        f"{DIGEST_B}  b.tar.gz\n"
        "```\n\n"
        f"**Full Changelog**: https://github.com/{REPO}/compare/"
        "v0.0.1...v0.0.2\n"
    )


def test_a_merge_subject_names_a_pull_request_the_api_did_not() -> None:
    fake = _fake(
        **{
            f"api repos/{REPO}/commits/c1/pulls": [],
            f"api repos/{REPO}/pulls/7": _pr(7, "feat: from the subject"),
        }
    )
    rows = rn.changes(REPO, "v0.0.2", "v0.0.1", fake)
    assert rows == [
        f"* feat: from the subject by @dev in https://github.com/{REPO}/pull/7"
    ]


def test_squash_subjects_and_unmerged_pull_requests() -> None:
    fake = _fake(
        **{
            f"api repos/{REPO}/compare/v0.0.1...v0.0.2": {
                "commits": [_commit("c1", "fix: squashed (#9)")]
            },
            f"api repos/{REPO}/commits/c1/pulls": [_pr(3, "closed", False)],
            f"api repos/{REPO}/pulls/9": _pr(9, "fix: squashed"),
        }
    )
    rows = rn.changes(REPO, "v0.0.2", "v0.0.1", fake)
    url = f"https://github.com/{REPO}/pull/9"
    assert rows == [f"* fix: squashed by @dev in {url}"]


def test_without_pull_requests_the_commits_are_listed() -> None:
    fake = _fake(
        **{
            f"api repos/{REPO}/compare/v0.0.1...v0.0.2": {
                "commits": [_commit("c1", "chore: direct", None)]
            },
            f"api repos/{REPO}/commits/c1/pulls": [],
        }
    )
    rows = rn.changes(REPO, "v0.0.2", "v0.0.1", fake)
    assert rows == [
        f"* chore: direct by @unknown in https://github.com/{REPO}/commit/c1"
    ]


def test_a_first_release_lists_its_history() -> None:
    fake = _fake(
        **{
            f"release list -R {REPO}": [
                {"tagName": "v0.0.2", "isDraft": False},
            ],
            f"api repos/{REPO}/commits?sha=v0.0.2": [
                _commit("c1", "feat: first"),
            ],
            f"api repos/{REPO}/commits/c1/pulls": [],
        }
    )
    body = rn.compose(REPO, "v0.0.2", NOTE, fake)
    url = f"https://github.com/{REPO}/commit/c1"
    assert f"* feat: first by @dev in {url}" in body
    assert body.endswith(
        f"**Full Changelog**: https://github.com/{REPO}/commits/v0.0.2\n"
    )


def test_drafts_are_not_previous_releases() -> None:
    fake = _fake(
        **{
            f"release list -R {REPO}": [
                {"tagName": "v0.0.2", "isDraft": False},
                {"tagName": "v0.0.1", "isDraft": True},
                {"tagName": "v0.0.0", "isDraft": False},
            ],
            f"api repos/{REPO}/compare/v0.0.0...v0.0.2": {"commits": []},
        }
    )
    body = rn.compose(REPO, "v0.0.2", NOTE, fake)
    assert "compare/v0.0.0...v0.0.2" in body


@pytest.mark.parametrize(
    ("assets", "reason"),
    [
        ([], "has no assets"),
        ([{"name": "a.whl", "digest": None}], "a.whl has no sha256 digest"),
    ],
)
def test_checksums_need_a_digest_for_every_asset(
    assets: list[dict[str, Any]], reason: str
) -> None:
    with pytest.raises(rn.ReleaseNotesError, match=reason):
        rn.checksums(assets)


def test_an_em_dash_is_refused() -> None:
    note = NOTE.replace("the second highlight", "a dash — here")
    with pytest.raises(rn.ReleaseNotesError, match="em dash"):
        rn.compose(REPO, "v0.0.2", note, _fake())


def test_publish_sets_the_title_and_body(tmp_path: Path) -> None:
    root = _tree(tmp_path, "## [0.0.2] - 2026-11-07")
    fake = _fake()
    assert rn.publish(REPO, "v0.0.2", "demo", root, fake) == (
        f"{REPO} v0.0.2: 'demo 0.0.2' published"
    )
    edit = fake.calls[-1]
    assert edit[:6] == ["release", "edit", "v0.0.2", "-R", REPO, "--title"]
    assert edit[6:8] == ["demo 0.0.2", "--notes-file"]


def test_publish_dry_run_prints_without_editing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _tree(tmp_path, "## [0.0.2] - 2026-11-07")
    fake = _fake()
    rn.publish(REPO, "v0.0.2", "demo", root, fake, dry_run=True)
    assert "## Highlights ⭐️" in capsys.readouterr().out
    assert not any(call[:2] == ["release", "edit"] for call in fake.calls)


def test_publish_needs_the_release_note(tmp_path: Path) -> None:
    root = _tree(tmp_path, "## [0.0.2] - 2026-11-07", note=None)
    with pytest.raises(rn.ReleaseNotesError, match="releases/v0.0.2.md"):
        rn.publish(REPO, "v0.0.2", "demo", root, _fake())


def test_check_skips_an_undated_version(tmp_path: Path) -> None:
    root = _tree(tmp_path, "## [0.0.2] - Unreleased", note=None)
    assert rn.check(root) == "0.0.2 is not dated yet; no release note needed"


def test_check_needs_a_note_for_a_dated_version(tmp_path: Path) -> None:
    root = _tree(tmp_path, "## [0.0.2] - 2026-11-07", note=None)
    with pytest.raises(rn.ReleaseNotesError, match="releases/v0.0.2.md"):
        rn.check(root)
    root = _tree(tmp_path, "## [0.0.2] - 2026-11-07", note="## Highlights\n")
    with pytest.raises(rn.ReleaseNotesError, match="found 0"):
        rn.check(root)


def test_check_accepts_a_poetry_version(tmp_path: Path) -> None:
    root = _tree(tmp_path, "## [0.0.2] - 2026-11-07")
    (root / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "demo"\nversion = "0.0.2"\n', encoding="utf-8"
    )
    assert rn.check(root) == "releases/v0.0.2.md: 2 highlights"


def test_main_check_and_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _tree(tmp_path, "## [0.0.2] - 2026-11-07")
    assert rn.main(["check", "--root", str(root)]) == 0
    assert capsys.readouterr().out == "releases/v0.0.2.md: 2 highlights\n"
    (root / "releases" / "v0.0.2.md").unlink()
    assert rn.main(["check", "--root", str(root)]) == 1
    assert "releases/v0.0.2.md" in capsys.readouterr().err


def test_main_publish(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _tree(tmp_path, "## [0.0.2] - 2026-11-07")
    argv = ["publish", "--repo", REPO, "--tag", "v0.0.2", "--project", "demo"]
    assert rn.main([*argv, "--root", str(root)], run=_fake()) == 0
    published = f"{REPO} v0.0.2: 'demo 0.0.2' published\n"
    assert capsys.readouterr().out == published


def test_gh_runs_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Any] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> Any:
        seen.append((cmd, kwargs))
        return type("Done", (), {"stdout": "out"})()

    monkeypatch.setattr(rn.subprocess, "run", fake_run)
    assert rn.gh(["release", "list"]) == "out"
    assert seen == [
        (
            ["gh", "release", "list"],
            {"check": True, "capture_output": True, "text": True},
        )
    ]


def test_the_committed_tree_passes() -> None:
    """A dated version in this repository has a usable release note."""
    rn.check(ROOT)
