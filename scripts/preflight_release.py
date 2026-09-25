#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Executable form of the RELEASING.md pre-flight checklist.

Prose checklists get skipped; this one fails loudly. Run before tagging:

    python3 scripts/preflight_release.py            # infer version
    python3 scripts/preflight_release.py 0.0.58     # assert a version
    python3 scripts/preflight_release.py --tag      # also create the tag

Every check maps to a numbered item in RELEASING.md. Checks that need the
network or a full test run are skipped unless --full is passed, so the
common case stays fast enough to actually get used.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAIL = "\033[31m✗\033[0m"
OK = "\033[32m✓\033[0m"
SKIP = "\033[33m–\033[0m"

problems: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(
        f"  {OK if ok else FAIL} {label}" + (f" — {detail}" if detail else "")
    )
    if not ok:
        problems.append(label)
    return ok


def skip(label: str, why: str) -> None:
    print(f"  {SKIP} {label} — {why}")


def run(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def versions() -> dict[str, str | None]:
    def grab(path: str, pattern: str) -> str | None:
        text = (ROOT / path).read_text(encoding="utf-8")
        m = re.search(pattern, text, re.M)
        return m.group(1) if m else None

    return {
        "pyproject.toml": grab("pyproject.toml", r'^version = "([^"]+)"'),
        "pain001/__init__.py": grab(
            "pain001/__init__.py", r'^__version__ = "([^"]+)"'
        ),
        "pain001/constants.py": grab(
            "pain001/constants.py", r'^VERSION = "([^"]+)"'
        ),
        "CITATION.cff": grab("CITATION.cff", r'^version: "?([^"\n]+)"?'),
        "SECURITY.md": grab("SECURITY.md", r"^\| `([0-9.]+)` \(latest\)"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("version", nargs="?", help="expected version, e.g. 0.0.58")
    ap.add_argument(
        "--tag",
        action="store_true",
        help="create the signed tag if every check passes",
    )
    ap.add_argument(
        "--full",
        action="store_true",
        help="also run the test suite, build and pip-audit (slow)",
    )
    args = ap.parse_args()
    if args.tag and not args.full:
        ap.error(
            "--tag requires --full; publishing without full preflight is forbidden"
        )

    print("Pre-flight checks (RELEASING.md):\n")

    exceptions = run(sys.executable, "scripts/check_security_exceptions.py")
    check(
        "security exceptions are current (item 4)",
        exceptions.returncode == 0,
        exceptions.stdout.strip() or exceptions.stderr.strip(),
    )

    # 6. version identical in the three files
    vs = versions()
    unique = set(vs.values())
    check(
        "version is identical in all three files (item 6)",
        len(unique) == 1 and None not in unique,
        ", ".join(f"{k}={v}" for k, v in vs.items())
        if len(unique) != 1
        else str(next(iter(unique))),
    )
    version = args.version or (
        next(iter(unique)) if len(unique) == 1 else None
    )
    if not version:
        print("\nCannot determine the version; fix the mismatch first.")
        return 1
    if (
        args.version
        and len(unique) == 1
        and args.version != next(iter(unique))
    ):
        check(
            f"version matches the requested {args.version}",
            False,
            f"files say {next(iter(unique))}",
        )
    print(f"\n  release candidate: v{version}\n")

    # 7. releases/vX.Y.Z.md exists and is non-trivial — the gate that
    #    actually broke the v0.0.57 tag build.
    note = ROOT / "releases" / f"v{version}.md"
    body = note.read_text(encoding="utf-8") if note.exists() else ""
    check(f"releases/v{version}.md exists (item 7)", note.exists())
    if note.exists():
        check(
            "release note is substantive",
            len(body.split()) >= 80,
            f"{len(body.split())} words",
        )
        check("release note names the right tag", f"v{version}" in body)

    # 5. CHANGELOG has a dated section for this version
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(
        rf"^## \[{re.escape(version)}\] - (\d{{4}}-\d{{2}}-\d{{2}})",
        changelog,
        re.M,
    )
    check(
        f"CHANGELOG.md has a dated [{version}] section (item 5)",
        bool(m),
        m.group(1) if m else "missing or undated",
    )

    # poetry.lock must match pyproject.toml. The publish job installs
    # with poetry, so a stale lock fails the release — but only after the
    # tag is pushed and public. Editing pyproject and re-locking are one
    # action; this is the check that says so before it matters.
    lock_ok = run("poetry", "check", "--lock").returncode == 0
    check(
        "poetry.lock matches pyproject.toml",
        lock_ok,
        "" if lock_ok else "run `poetry lock` and commit the result",
    )

    # clean tree and correct branch — cutting from a dirty tree is how
    # unreviewed changes end up inside a signed tag
    dirty = run("git", "status", "--porcelain").stdout.strip()
    check(
        "working tree is clean",
        not dirty,
        f"{len(dirty.splitlines())} modified path(s)" if dirty else "",
    )
    branch = run("git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    check("on main", branch == "main", branch)
    local = run("git", "rev-parse", "HEAD").stdout.strip()
    remote = run("git", "rev-parse", "origin/main").stdout.strip()
    ahead = run(
        "git", "rev-list", "--count", "origin/main..HEAD"
    ).stdout.strip()
    check(
        "HEAD matches origin/main",
        local == remote and bool(local),
        # Naming the fix matters: RELEASING.md has you merge to main
        # before pre-flight, but running the checks on an unpushed
        # release commit is an easy order to fall into, and a bare
        # failure here reads like something is wrong with the release.
        f"{ahead} unpushed commit(s) — push them before tagging"
        if ahead and ahead != "0"
        else "",
    )

    # tag must not already exist (locally or remotely)
    existing = run("git", "tag", "-l", f"v{version}").stdout.strip()
    check(f"tag v{version} does not exist locally", not existing)
    remote_tags = run(
        "git", "ls-remote", "--tags", "origin", f"refs/tags/v{version}"
    )
    check(
        "remote tag inventory is reachable",
        remote_tags.returncode == 0,
        remote_tags.stderr.strip() if remote_tags.returncode else "",
    )
    check(
        f"tag v{version} does not exist on origin",
        not remote_tags.stdout.strip(),
    )

    # signing configured — the workflow expects signed tags
    signing = run("git", "config", "--get", "user.signingkey").stdout.strip()
    check("tag signing key configured", bool(signing), signing or "unset")

    if args.full:
        print("\n  running slow checks…")
        r = run("poetry", "run", "pytest", "-q")
        check(
            "test suite passes",
            r.returncode == 0,
            (r.stdout.strip().splitlines() or ["no output"])[-1],
        )
        r = run("poetry", "build")
        check("package builds", r.returncode == 0)
        r = run(
            sys.executable,
            "scripts/inspect_release.py",
            "--name",
            "pain001",
            "--project",
            "Pain001",
            "--version",
            version,
            "--dist",
            "dist",
            "--output",
            ".release",
        )
        check(
            "built artifacts and checksum-bearing notes are current",
            r.returncode == 0,
            r.stdout.strip() or r.stderr.strip(),
        )
        r = run(
            "poetry", "run", "pip-audit", "-r", "requirements.txt", "--no-deps"
        )
        check(
            "pip-audit clean",
            r.returncode == 0,
            (r.stdout.strip().splitlines() or [""])[-1],
        )
    else:
        skip(
            "test suite / build / pip-audit (items 1-4)", "pass --full to run"
        )

    print()
    if problems:
        print(f"{len(problems)} problem(s): " + "; ".join(problems))
        print("Fix these before tagging — the publish job fails on them too,")
        print("but only after you have already pushed a tag.")
        return 1

    print("All pre-flight checks passed.")
    if args.tag:
        msg = f"Pain001 v{version}"
        r = run("git", "tag", "-s", f"v{version}", "-m", msg)
        if r.returncode != 0:
            print(f"{FAIL} tag creation failed: {r.stderr.strip()}")
            return 1
        r = run(
            sys.executable,
            "scripts/inspect_release.py",
            "--name",
            "pain001",
            "--project",
            "Pain001",
            "--version",
            version,
            "--dist",
            "dist",
            "--output",
            ".release",
            "--tag",
            f"v{version}",
        )
        if r.returncode != 0:
            print(f"{FAIL} signed-tag preflight failed: {r.stderr.strip()}")
            print("The local tag was retained for inspection. Do not push it.")
            return 1
        print(f"{OK} created signed tag v{version}")
        print(f"    push it with:  git push origin v{version}")
    else:
        print(
            f"Next:  python3 scripts/preflight_release.py {version} --full --tag"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
