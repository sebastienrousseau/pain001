# SPDX-License-Identifier: Apache-2.0 OR MIT
"""GitHub release identity, signed annotations and complete checksum notes."""

from __future__ import annotations

import re
from typing import Any

from .inventory import Member
from .transport import Transport

API = "https://api.github.com/repos/"


def require(condition: bool, message: str) -> None:
    """Reject incomplete evidence with a user-facing diagnostic."""
    if not condition:
        raise ValueError(message)


def notes_checksums(body: str, repository: str, tag: str) -> dict[str, str]:
    """Check the global note format and return its complete asset hashes."""
    if not isinstance(body, str):
        raise ValueError("release notes must be text")
    body = body.replace("\r\n", "\n")
    require("—" not in body, "release notes contain an em dash")
    headings = [
        "## Highlights ⭐️",
        "## What's Changed",
        "## Checksums",
        "**Full Changelog**:",
    ]
    require(
        body.startswith(headings[0]),
        "release notes do not start with Highlights",
    )
    positions = [body.index(heading) for heading in headings]
    require(
        positions == sorted(positions),
        "release note sections are out of order",
    )
    count = len(re.findall(r"^\* \*\*", body[: positions[1]], re.M))
    require(2 <= count <= 4, "release notes need two to four Highlights")
    require(
        "SHA-256 of every asset attached to this release:" in body,
        "checksum introduction is missing",
    )
    block = (
        body[positions[2] : positions[3]]
        .split("```text\n", 1)[1]
        .split("```", 1)[0]
    )
    lines = block.splitlines()
    pairs = [re.fullmatch(r"([0-9a-f]{64})  (.+)", line) for line in lines]
    require(bool(pairs) and all(pairs), "invalid checksum block")
    hashes = {match[2]: match[1] for match in pairs if match is not None}
    require(len(hashes) == len(lines), "duplicate checksum filename")
    link = body[positions[3] :].strip()
    require(
        link.startswith(
            f"**Full Changelog**: https://github.com/{repository}/"
        ),
        "incorrect changelog repository",
    )
    require(link.endswith(tag), "incorrect changelog version")
    return hashes


def release_evidence(
    client: Transport, member: Member, version: str, latest: bool
) -> dict[str, Any]:
    """Verify the live page, every API asset digest and signed tag target."""
    base = API + member.repository
    tag = "v" + version
    endpoint = "/releases/latest" if latest else "/releases/tags/" + tag
    release = client.json(base + endpoint)
    require(
        release["tag_name"] == tag,
        f"latest GitHub release is {release['tag_name']}, expected {tag}",
    )
    require(
        release["name"] == member.project + " " + version,
        "incorrect release title",
    )
    require(
        release["draft"] is False and release["prerelease"] is False,
        "release is draft or prerelease",
    )
    assets = release["assets"]
    require(bool(assets), "release has no assets")
    hashes = notes_checksums(release["body"], member.repository, tag)
    missing = {
        name.format(version=version) for name in member.required_assets
    } - set(hashes)
    require(
        not missing,
        "required release assets missing: " + ", ".join(sorted(missing)),
    )
    require(
        len({asset["name"] for asset in assets}) == len(assets),
        "duplicate release asset",
    )
    require(
        set(hashes) == {asset["name"] for asset in assets},
        "checksum filenames do not match release assets",
    )
    require(
        all(
            asset["digest"] == "sha256:" + hashes[asset["name"]]
            for asset in assets
        ),
        "checksum digest differs from GitHub",
    )
    return {
        "commit": signed_target(client, member, tag),
        "asset_hashes": hashes,
        "release": f"https://github.com/{member.repository}/releases/tag/{tag}",
    }


def signed_target(client: Transport, member: Member, tag: str) -> str:
    """Read the source commit only from a verified annotated release tag."""
    base = API + member.repository
    ref = client.json(base + "/git/ref/tags/" + tag)["object"]
    require(ref["type"] == "tag", "release tag is not annotated")
    annotation = client.json(base + "/git/tags/" + ref["sha"])
    require(
        annotation["message"].splitlines()[0] == member.project + " " + tag,
        "incorrect tag annotation",
    )
    require(
        annotation["verification"]["verified"] is True,
        "tag signature is not verified",
    )
    target = annotation["object"]
    require(
        target["type"] == "commit"
        and bool(re.fullmatch(r"[0-9a-f]{40}", target["sha"])),
        "tag target is not a commit",
    )
    return str(target["sha"])
