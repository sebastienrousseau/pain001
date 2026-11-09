# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Registry metadata, OCI content and the deployed browser runtime."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import quote

from check_suite_consistency import core_floor

from .inventory import Member
from .releases import require
from .transport import Transport

OCI_ACCEPT = ", ".join(
    (
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    )
)


def pypi_metadata(
    client: Transport, name: str, version: str, latest: bool
) -> dict[str, Any]:
    """Fetch either the current distribution or a deliberately historical one."""
    suffix = "/json" if latest else f"/{version}/json"
    return client.json("https://pypi.org/pypi/" + name + suffix)


def pypi_evidence(
    client: Transport,
    member: Member,
    version: str,
    latest: bool,
    hashes: dict[str, str],
) -> dict[str, str]:
    """Match published wheel/source bytes and the core dependency floor."""
    metadata = pypi_metadata(client, member.name, version, latest)
    info = metadata["info"]
    require(
        info["version"] == version,
        f"PyPI is {info['version']}, expected {version}",
    )
    if member.name != "pain001":
        require(
            core_floor(info["requires_dist"]) == version,
            "PyPI core dependency floor differs from suite version",
        )
    files = [item for item in metadata["urls"] if not item["yanked"]]
    require(
        {"bdist_wheel", "sdist"} <= {item["packagetype"] for item in files},
        "PyPI wheel or source is missing/yanked",
    )
    require(
        all(
            hashes.get(item["filename"]) == item["digests"]["sha256"]
            for item in files
        ),
        "PyPI and GitHub artifact checksums disagree",
    )
    return {"pypi": version}


def content_json(
    client: Transport, base: str, digest: str, headers: dict[str, str]
) -> dict[str, Any]:
    """Verify an OCI content-addressed object before trusting its JSON."""
    require(
        bool(re.fullmatch(r"sha256:[0-9a-f]{64}", digest)),
        "invalid OCI content digest",
    )
    payload = client.get(base + digest, headers)
    require(
        hashlib.sha256(payload).hexdigest() == digest[7:],
        "OCI content digest mismatch",
    )
    return json.loads(payload)


def image_evidence(
    client: Transport, member: Member, version: str, commit: str
) -> dict[str, Any]:
    """Verify both Linux images identify the signed release's source commit."""
    token_url = f"https://ghcr.io/token?service=ghcr.io&scope=repository:{member.repository}:pull"
    token = client.json(token_url)["token"]
    headers = {"Authorization": "Bearer " + token, "Accept": OCI_ACCEPT}
    base = "https://ghcr.io/v2/" + member.repository + "/"
    index = client.json(base + "manifests/" + version, headers)
    targets = {
        item["platform"]["architecture"]: item
        for item in index["manifests"]
        if item["platform"]["os"] == "linux"
        and item["platform"]["architecture"] in {"amd64", "arm64"}
    }
    require(
        set(targets) == {"amd64", "arm64"},
        "OCI image platform missing: linux/amd64 or linux/arm64",
    )
    for item in targets.values():
        manifest = content_json(
            client, base + "manifests/", item["digest"], headers
        )
        config = content_json(
            client, base + "blobs/", manifest["config"]["digest"], headers
        )
        labels = config["config"]["Labels"]
        require(
            labels["org.opencontainers.image.version"] == version,
            "OCI image version differs from release",
        )
        require(
            labels["org.opencontainers.image.revision"] == commit,
            "OCI image source commit differs from signed tag",
        )
    return {"image_platforms": ["linux/amd64", "linux/arm64"]}


def website_evidence(
    client: Transport, member: Member, version: str, latest: bool
) -> dict[str, str]:
    """Check the live demo, not only its GitHub release archive."""
    runtime = client.json(member.runtime)
    require(
        runtime["pain001"] == version,
        "live website runtime differs from suite version",
    )
    wheels = [
        wheel
        for wheel in runtime["wheels"]
        if wheel["file"].startswith("pain001-")
    ]
    require(len(wheels) == 1, "website runtime needs exactly one core wheel")
    core = pypi_metadata(client, "pain001", version, latest)
    files = {
        item["filename"]: item for item in core["urls"] if not item["yanked"]
    }
    wheel = wheels[0]
    require(
        wheel["file"] in files, "website core wheel is not published on PyPI"
    )
    require(
        wheel["sha256"] == files[wheel["file"]]["digests"]["sha256"],
        "website core wheel checksum differs from PyPI",
    )
    return {"runtime": version}


def mcp_registry_evidence(
    client: Transport, member: Member, version: str, latest: bool
) -> dict[str, str]:
    """Verify the active server record and the package it tells clients to run."""
    name = quote(member.mcp_registry, safe="")
    record = client.json(
        f"https://registry.modelcontextprotocol.io/v0.1/servers/{name}/versions/{version}"
    )
    server = record["server"]
    require(
        server["name"] == member.mcp_registry,
        "MCP Registry server name differs from inventory",
    )
    require(
        server["version"] == version,
        "MCP Registry server version differs from suite",
    )
    require(
        server["repository"]["url"]
        == "https://github.com/" + member.repository,
        "MCP Registry repository mismatch",
    )
    meta = record["_meta"]["io.modelcontextprotocol.registry/official"]
    require(
        meta["status"] == "active", "MCP Registry publication is not active"
    )
    if latest:
        require(
            meta["isLatest"] is True,
            "MCP Registry latest version differs from suite",
        )
    packages = server["packages"]
    require(
        any(
            package["registryType"] == "pypi"
            and package["identifier"] == member.name
            and package["version"] == version
            for package in packages
        ),
        "MCP Registry package does not match the published PyPI distribution",
    )
    return {"mcp_registry": version}
