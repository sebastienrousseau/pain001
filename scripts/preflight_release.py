#!/usr/bin/env python3
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
    print(f"  {OK if ok else FAIL} {label}" + (f" — {detail}" if detail else ""))
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
        "pain001/__init__.py": grab("pain001/__init__.py", r'^__version__ = "([^"]+)"'),
        "pain001/constants.py": grab("pain001/constants.py", r'^VERSION = "([^"]+)"'),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("version", nargs="?", help="expected version, e.g. 0.0.58")
    ap.add_argument("--tag", action="store_true",
                    help="create the signed tag if every check passes")
    ap.add_argument("--full", action="store_true",
                    help="also run the test suite, build and pip-audit (slow)")
    args = ap.parse_args()

    print("Pre-flight checks (RELEASING.md):\n")

    # 6. version identical in the three files
    vs = versions()
    unique = set(vs.values())
    check("version is identical in all three files (item 6)",
          len(unique) == 1 and None not in unique,
          ", ".join(f"{k}={v}" for k, v in vs.items()) if len(unique) != 1 else str(next(iter(unique))))
    version = args.version or (next(iter(unique)) if len(unique) == 1 else None)
    if not version:
        print("\nCannot determine the version; fix the mismatch first.")
        return 1
    if args.version and len(unique) == 1 and args.version != next(iter(unique)):
        check(f"version matches the requested {args.version}", False,
              f"files say {next(iter(unique))}")
    print(f"\n  release candidate: v{version}\n")

    # 7. releases/vX.Y.Z.md exists and is non-trivial — the gate that
    #    actually broke the v0.0.57 tag build.
    note = ROOT / "releases" / f"v{version}.md"
    body = note.read_text(encoding="utf-8") if note.exists() else ""
    check(f"releases/v{version}.md exists (item 7)", note.exists())
    if note.exists():
        check("release note is substantive", len(body.split()) >= 80,
              f"{len(body.split())} words")
        check("release note names the right tag", f"v{version}" in body)

    # 5. CHANGELOG has a dated section for this version
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"^## \[%s\] - (\d{4}-\d{2}-\d{2})" % re.escape(version),
                  changelog, re.M)
    check(f"CHANGELOG.md has a dated [{version}] section (item 5)", bool(m),
          m.group(1) if m else "missing or undated")

    # clean tree and correct branch — cutting from a dirty tree is how
    # unreviewed changes end up inside a signed tag
    dirty = run("git", "status", "--porcelain").stdout.strip()
    check("working tree is clean", not dirty,
          f"{len(dirty.splitlines())} modified path(s)" if dirty else "")
    branch = run("git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    check("on main", branch == "main", branch)
    local = run("git", "rev-parse", "HEAD").stdout.strip()
    remote = run("git", "rev-parse", "origin/main").stdout.strip()
    check("HEAD matches origin/main", local == remote and bool(local))

    # tag must not already exist (locally or remotely)
    existing = run("git", "tag", "-l", f"v{version}").stdout.strip()
    check(f"tag v{version} does not exist locally", not existing)
    remote_tag = run("git", "ls-remote", "--tags", "origin",
                     f"refs/tags/v{version}").stdout.strip()
    check(f"tag v{version} does not exist on origin", not remote_tag)

    # signing configured — the workflow expects signed tags
    signing = run("git", "config", "--get", "user.signingkey").stdout.strip()
    check("tag signing key configured", bool(signing), signing or "unset")

    if args.full:
        print("\n  running slow checks…")
        r = run("poetry", "run", "pytest", "-q")
        check("test suite passes", r.returncode == 0,
              (r.stdout.strip().splitlines() or ["no output"])[-1])
        r = run("poetry", "build")
        check("package builds", r.returncode == 0)
        r = run("poetry", "run", "pip-audit", "-r", "requirements.txt",
                "--no-deps")
        check("pip-audit clean", r.returncode == 0,
              (r.stdout.strip().splitlines() or [""])[-1])
    else:
        skip("test suite / build / pip-audit (items 1-4)", "pass --full to run")

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
        print(f"{OK} created signed tag v{version}")
        print(f"    push it with:  git push origin v{version}")
    else:
        print(f"Next:  python3 scripts/preflight_release.py {version} --tag")
    return 0


if __name__ == "__main__":
    sys.exit(main())
