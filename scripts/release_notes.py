#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Compose a GitHub release body in the pain001 suite's release shape.

Vendored byte-identical in every pain001 suite repository, with
tests/test_release_notes.py; change both in pain001 and copy them out.

The shape, in order: ``## Highlights ⭐️`` (2 to 4 bullets, taken from
the ``## Highlights`` section of ``releases/v<version>.md``), ``## What's
Changed`` (the pull requests merged since the previous release, or its
commits when there are none), ``## Checksums`` (the SHA-256 GitHub
records for every asset attached to the release) and the ``**Full
Changelog**`` link. No em dash anywhere.

``publish`` runs as the last job of the tag workflow, after every asset
is attached, and sets the title (``<project> <version>``) and body with
``gh release edit``. ``check`` runs in the test suite: once the
CHANGELOG dates the current version, its release note must exist and
carry 2 to 4 highlights, so a missing note fails the pull request and
not the release.

Usage::

    release_notes.py check [--root DIR]
    release_notes.py publish --repo OWNER/REPO --tag vX.Y.Z \\
        --project NAME [--root DIR] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

Runner = Callable[[Sequence[str]], str]

EM_DASH = "—"
CHECKSUM_INTRO = "SHA-256 of every asset attached to this release:"
_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_MERGE = re.compile(r"^Merge pull request #(\d+) ")
_SQUASH = re.compile(r"\(#(\d+)\)$")


class ReleaseNotesError(Exception):
    """The release note or the release cannot produce a valid body."""


def gh(args: Sequence[str]) -> str:
    """Run the GitHub CLI and return its standard output."""
    done = subprocess.run(
        ["gh", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return str(done.stdout)


def _json(run: Runner, *args: str) -> Any:
    return json.loads(run(list(args)))


def highlights(note: str) -> list[str]:
    """The bullets of the note's Highlights section, wrapped lines joined."""
    bullets: list[str] = []
    inside = False
    for line in note.splitlines():
        if line.startswith("## "):
            inside = line.startswith("## Highlights")
        elif inside and line.startswith("* "):
            bullets.append(line.rstrip())
        elif inside and bullets and line.startswith("  "):
            bullets[-1] += " " + line.strip()
    if not 2 <= len(bullets) <= 4:
        raise ReleaseNotesError(
            f"expected 2 to 4 highlight bullets, found {len(bullets)}"
        )
    return bullets


def _version_key(tag: str) -> tuple[int, ...] | None:
    match = _TAG.match(tag)
    return tuple(int(part) for part in match.groups()) if match else None


def previous_tag(tags: Iterable[str], tag: str) -> str | None:
    """The highest ``vX.Y.Z`` tag below ``tag``, or None for a first one."""
    current = _version_key(tag) or ()
    below = [t for t in tags if (_version_key(t) or current) < current]
    return max(below, key=lambda t: _version_key(t) or (), default=None)


def _row(pr: dict[str, Any]) -> str:
    return f"* {pr['title']} by @{pr['user']['login']} in {pr['html_url']}"


def _named_pr(subject: str) -> int | None:
    match = _MERGE.match(subject) or _SQUASH.search(subject)
    return int(match.group(1)) if match else None


def _commit_prs(
    repo: str, commit: dict[str, Any], known: set[int], run: Runner
) -> list[Any]:
    """Merged pull requests of a commit, plus one its subject names.

    A merge commit of a reused branch name loses its pull request link
    in the API, so ``Merge pull request #N`` (or a squash ``(#N)``) is
    read from the subject; one already listed is not fetched again.
    """
    sha = commit["sha"]
    prs: list[Any] = _json(run, "api", f"repos/{repo}/commits/{sha}/pulls")
    named = _named_pr(commit["commit"]["message"].splitlines()[0])
    seen = known | {pr["number"] for pr in prs}
    if named is not None and named not in seen:
        prs.append(_json(run, "api", f"repos/{repo}/pulls/{named}"))
    return [pr for pr in prs if pr.get("merged_at")]


def _commits(repo: str, tag: str, prev: str | None, run: Runner) -> list[Any]:
    if prev is None:
        url = f"repos/{repo}/commits?sha={tag}"
        history: list[Any] = _json(run, "api", url)
        return history
    compare = _json(run, "api", f"repos/{repo}/compare/{prev}...{tag}")
    return list(compare["commits"])


def changes(repo: str, tag: str, prev: str | None, run: Runner) -> list[str]:
    """What's Changed rows: merged pull requests, else the commits."""
    commits = _commits(repo, tag, prev, run)
    rows: dict[int, str] = {}
    for commit in commits:
        for pr in _commit_prs(repo, commit, set(rows), run):
            rows.setdefault(pr["number"], _row(pr))
    if rows:
        return list(rows.values())
    return [
        f"* {c['commit']['message'].splitlines()[0]} by "
        f"@{(c.get('author') or {}).get('login', 'unknown')} "
        f"in {c['html_url']}"
        for c in commits
    ]


def checksums(assets: list[dict[str, Any]]) -> list[str]:
    """``<sha256>  <name>`` for every asset, sorted by name."""
    if not assets:
        raise ReleaseNotesError("the release has no assets")
    rows = []
    for asset in sorted(assets, key=lambda a: a["name"]):
        digest = asset.get("digest") or ""
        if not digest.startswith("sha256:"):
            raise ReleaseNotesError(f"{asset['name']} has no sha256 digest")
        rows.append(f"{digest.removeprefix('sha256:')}  {asset['name']}")
    return rows


def compose(repo: str, tag: str, note: str, run: Runner) -> str:
    """The full release body for ``tag``, validated."""
    releases = _json(
        run,
        "release",
        "list",
        "-R",
        repo,
        "--limit",
        "1000",
        "--json",
        "tagName,isDraft",
    )
    published = [r["tagName"] for r in releases if not r["isDraft"]]
    prev = previous_tag(published, tag)
    view = _json(run, "release", "view", tag, "-R", repo, "--json", "assets")
    link = f"compare/{prev}...{tag}" if prev else f"commits/{tag}"
    body = "\n".join(
        [
            "## Highlights ⭐️",
            "",
            *highlights(note),
            "",
            "## What's Changed",
            "",
            *changes(repo, tag, prev, run),
            "",
            "## Checksums",
            "",
            CHECKSUM_INTRO,
            "",
            "```text",
            *checksums(view["assets"]),
            "```",
            "",
            f"**Full Changelog**: https://github.com/{repo}/{link}",
            "",
        ]
    )
    if EM_DASH in body:
        raise ReleaseNotesError("the body contains an em dash")
    return body


def _note(root: Path, version: str) -> str:
    path = root / "releases" / f"v{version}.md"
    if not path.is_file():
        raise ReleaseNotesError(f"missing releases/v{version}.md")
    return path.read_text(encoding="utf-8")


def _version(root: Path) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = data.get("project", {}).get("version")
    return str(version or data["tool"]["poetry"]["version"])


def check(root: Path) -> str:
    """Fail when the dated current version has no usable release note."""
    version = _version(root)
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    dated = rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}\s*$"
    if not re.search(dated, changelog, re.MULTILINE):
        return f"{version} is not dated yet; no release note needed"
    count = len(highlights(_note(root, version)))
    return f"releases/v{version}.md: {count} highlights"


def publish(
    repo: str,
    tag: str,
    project: str,
    root: Path,
    run: Runner,
    dry_run: bool = False,
) -> str:
    """Compose the body for ``tag`` and set it, with the title, on GitHub."""
    version = tag.removeprefix("v")
    title = f"{project} {version}"
    body = compose(repo, tag, _note(root, version), run)
    if dry_run:
        print(f"# {title}\n\n{body}")
        return f"{repo} {tag}: dry run"
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", encoding="utf-8", delete=False
    ) as handle:
        handle.write(body)
    run(
        [
            "release",
            "edit",
            tag,
            "-R",
            repo,
            "--title",
            title,
            "--notes-file",
            handle.name,
        ]
    )
    Path(handle.name).unlink()
    return f"{repo} {tag}: {title!r} published"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "publish"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--root", type=Path, default=Path.cwd())
    pub = sub.choices["publish"]
    for flag in ("--repo", "--tag", "--project"):
        pub.add_argument(flag, required=True)
    pub.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None, run: Runner = gh) -> int:
    """Entry point; prints the outcome, or the reason on standard error."""
    args = _parser().parse_args(argv)
    try:
        if args.command == "check":
            print(check(args.root))
        else:
            print(
                publish(
                    args.repo,
                    args.tag,
                    args.project,
                    args.root,
                    run,
                    args.dry_run,
                )
            )
    except ReleaseNotesError as error:
        print(f"release_notes: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - the CLI entry point
    sys.exit(main())
