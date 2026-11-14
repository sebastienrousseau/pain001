# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Package registries of the SDKs: Go, Maven Central, crates.io and NuGet."""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from .inventory import Member
from .releases import require
from .transport import Transport

Check = Callable[[Transport, str, str, dict[str, str]], None]


def go_evidence(
    client: Transport, module: str, version: str, hashes: dict[str, str]
) -> None:
    """Require the Go module proxy to serve the tagged module version.

    The proxy escapes upper-case letters in module paths (``!x``). The
    inventory's module paths are all lower case, so the path is used as
    it stands; an upper-case path would fail here rather than pass.
    """
    del hashes
    info = client.json(f"https://proxy.golang.org/{module}/@v/v{version}.info")
    require(
        info["Version"] == "v" + version,
        "Go module proxy does not serve the release version",
    )


def maven_evidence(
    client: Transport, coordinates: str, version: str, hashes: dict[str, str]
) -> None:
    """Require the jar on Maven Central to be the release's jar, byte for byte."""
    group, artifact = coordinates.split(":")
    jar = f"{artifact}-{version}.jar"
    payload = client.get(
        "https://repo1.maven.org/maven2/"
        + f"{group.replace('.', '/')}/{artifact}/{version}/{jar}"
    )
    require(
        hashlib.sha256(payload).hexdigest() == hashes.get(jar),
        "Maven Central jar differs from the release asset",
    )


def crates_evidence(
    client: Transport, crate: str, version: str, hashes: dict[str, str]
) -> None:
    """Require crates.io to list the version and not to have yanked it."""
    del hashes
    record = client.json(f"https://crates.io/api/v1/crates/{crate}/{version}")
    require(
        record["version"]["num"] == version,
        "crates.io version differs from release",
    )
    require(
        record["version"]["yanked"] is False, "crates.io version is yanked"
    )


def nuget_evidence(
    client: Transport, package: str, version: str, hashes: dict[str, str]
) -> None:
    """Require nuget.org to list the version.

    nuget.org adds its repository signature to every package, so the
    served ``.nupkg`` never matches the release asset's bytes.
    """
    del hashes
    index = client.json(
        f"https://api.nuget.org/v3-flatcontainer/{package.lower()}/index.json"
    )
    require(version in index["versions"], "NuGet does not list the version")


REGISTRIES: dict[str, tuple[str, Check]] = {
    "go": ("Go module proxy", go_evidence),
    "maven": ("Maven Central", maven_evidence),
    "crates": ("crates.io", crates_evidence),
    "nuget": ("NuGet", nuget_evidence),
}


def registry_evidence(
    client: Transport, member: Member, version: str, hashes: dict[str, str]
) -> dict[str, str]:
    """Check the one package registry an SDK publishes to."""
    require(
        member.registry in REGISTRIES,
        "unknown package registry: " + member.registry,
    )
    REGISTRIES[member.registry][1](client, member.package, version, hashes)
    return {member.registry: version}
