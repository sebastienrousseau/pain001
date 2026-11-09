# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Publication failures must never look like a complete suite release."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import ecosystem_audit
import pytest

VERSION = "0.0.82"
COMMIT = "a" * 40
API = "https://api.github.com/repos/sebastienrousseau/"
NAMES = (
    "pain001",
    "pain001-mcp",
    "pain001-lsp",
    "pain001-loader-mt101",
    "pain001-loader-xlsx",
    "pain001-mockbank",
    "pain001-plugin-template",
    "pain001-fast",
    "pain001.github.io",
)


class Published:
    """A complete synthetic release served through the transport boundary."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {}
        self.data[
            "https://api.github.com/search/repositories?q=user:sebastienrousseau+pain001+in:name&per_page=100"
        ] = {
            "total_count": 9,
            "items": [{"name": name, "archived": False} for name in NAMES],
        }
        for name in NAMES:
            self.release(name)
        for name in (
            "pain001",
            "pain001-mcp",
            "pain001-lsp",
            "pain001-mockbank",
        ):
            self.image(name)
        self.data[
            "https://registry.modelcontextprotocol.io/v0.1/servers/io.github.sebastienrousseau%2Fpain001-mcp/versions/"
            + VERSION
        ] = {
            "server": {
                "name": "io.github.sebastienrousseau/pain001-mcp",
                "version": VERSION,
                "repository": {
                    "url": "https://github.com/sebastienrousseau/pain001-mcp"
                },
                "packages": [
                    {
                        "registryType": "pypi",
                        "identifier": "pain001-mcp",
                        "version": VERSION,
                    }
                ],
            },
            "_meta": {
                "io.modelcontextprotocol.registry/official": {
                    "status": "active",
                    "isLatest": True,
                }
            },
        }
        self.data["https://pain001.com/pyodide/pain001-runtime.json"] = {
            "pain001": VERSION,
            "wheels": [
                {"file": "pain001-0.0.82-py3-none-any.whl", "sha256": "b" * 64}
            ],
        }

    def release(self, name: str) -> None:
        """Publish source metadata, a signed tag and optional PyPI files."""
        project = "pain001.com" if name == "pain001.github.io" else name
        prefix = name.replace("-", "_")
        if name == "pain001-plugin-template":
            prefix = name
        if name == "pain001.github.io":
            prefix = "pain001-site-v"
        source = (
            f"{prefix}-{VERSION}.tar.gz"
            if name != "pain001.github.io"
            else f"pain001-site-v{VERSION}.tar.gz"
        )
        files = [source, "SHA256SUMS"]
        if name in NAMES[:5]:
            files.append(f"{prefix}-{VERSION}-py3-none-any.whl")
        files.extend(extra_assets(name))
        assets = [{"name": f, "digest": "sha256:" + "b" * 64} for f in files]
        sums = "\n".join("b" * 64 + "  " + f for f in files)
        body = (
            "## Highlights ⭐️\n\n* **One**: First change.\n* **Two**: Second change.\n\n"
            "## What's Changed\n\n* Update by @example in https://example.test/pr/1\n\n"
            "## Checksums\n\nSHA-256 of every asset attached to this release:\n\n"
            f"```text\n{sums}\n```\n\n**Full Changelog**: "
            f"https://github.com/sebastienrousseau/{name}/compare/v0.0.81...v{VERSION}\n"
        )
        release = {
            "tag_name": "v" + VERSION,
            "name": project + " " + VERSION,
            "draft": False,
            "prerelease": False,
            "assets": assets,
            "body": body,
        }
        self.data[API + name + "/releases/latest"] = release
        self.data[API + name + "/releases/tags/v" + VERSION] = release
        self.data[API + name + "/git/ref/tags/v" + VERSION] = {
            "object": {"type": "tag", "sha": "c" * 40}
        }
        self.data[API + name + "/git/tags/" + "c" * 40] = {
            "object": {"type": "commit", "sha": COMMIT},
            "message": project + " v" + VERSION + "\n",
            "verification": {"verified": True},
        }
        if name in NAMES[:5]:
            self.pypi(name, files)

    def pypi(self, name: str, files: list[str]) -> None:
        """Publish only Python distributions in the synthetic registry."""
        requires = [] if name == "pain001" else [f"pain001<1,>={VERSION}"]
        metadata = {
            "info": {"version": VERSION, "requires_dist": requires},
            "urls": [
                {
                    "filename": filename,
                    "packagetype": "sdist"
                    if filename.endswith(".tar.gz")
                    else "bdist_wheel",
                    "yanked": False,
                    "digests": {"sha256": "b" * 64},
                }
                for filename in files
                if filename.endswith((".whl", ".tar.gz"))
            ],
        }
        self.data[f"https://pypi.org/pypi/{name}/json"] = metadata
        self.data[f"https://pypi.org/pypi/{name}/{VERSION}/json"] = metadata

    def blob(self, base: str, value: dict[str, Any]) -> str:
        """Return an OCI content digest tied to the actual serialized bytes."""
        payload = json.dumps(value).encode()
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        self.data[base + digest] = payload
        return digest

    def image(
        self, name: str, version: str = VERSION, commit: str = COMMIT
    ) -> None:
        """Publish two runnable platforms and a provenance placeholder."""
        base = f"https://ghcr.io/v2/sebastienrousseau/{name}/"
        token_url = f"https://ghcr.io/token?service=ghcr.io&scope=repository:sebastienrousseau/{name}:pull"
        self.data[token_url] = {"token": "synthetic-public-pull-token"}
        config = {
            "config": {
                "Labels": {
                    "org.opencontainers.image.version": version,
                    "org.opencontainers.image.revision": commit,
                }
            }
        }
        config_digest = self.blob(base + "blobs/", config)
        manifest = {"config": {"digest": config_digest}}
        digest = self.blob(base + "manifests/", manifest)
        self.data[base + "manifests/" + VERSION] = {
            "manifests": [
                {
                    "platform": {"os": "linux", "architecture": arch},
                    "digest": digest,
                }
                for arch in ("amd64", "arm64", "unknown")
            ],
        }

    def get(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        """Read fixture bytes; absent endpoints are explicit failures."""
        if url not in self.data:
            raise ValueError("HTTP 404: " + url)
        value = self.data[url]
        return (
            value if isinstance(value, bytes) else json.dumps(value).encode()
        )

    def json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        """Decode exactly the bytes that a real client would receive."""
        return json.loads(self.get(url, headers))


def test_inventory_includes_every_repository_and_publication_channel() -> None:
    """The scaffold, native wheel and website cannot disappear behind PyPI."""
    inventory = {member.name: member for member in ecosystem_audit.inventory()}
    assert set(inventory) == {
        "pain001",
        "pain001-mcp",
        "pain001-lsp",
        "pain001-loader-mt101",
        "pain001-loader-xlsx",
        "pain001-mockbank",
        "pain001-plugin-template",
        "pain001-fast",
        "pain001.github.io",
    }
    assert sum(member.pypi for member in inventory.values()) == 5
    assert {m.name for m in inventory.values() if m.image} == {
        "pain001",
        "pain001-mcp",
        "pain001-lsp",
        "pain001-mockbank",
    }
    assert inventory["pain001.github.io"].project == "pain001.com"
    assert inventory["pain001.github.io"].runtime == (
        "https://pain001.com/pyodide/pain001-runtime.json"
    )


def extra_assets(name: str) -> list[str]:
    """Required non-PyPI artifacts, independent of the implementation inventory."""
    if name == "pain001-fast":
        return [
            f"pain001_fast-{VERSION}-cp311-abi3-{platform}.whl"
            for platform in (
                "linux_x86_64",
                "linux_aarch64",
                "macosx_11_0_arm64",
                "macosx_11_0_x86_64",
                "win_amd64",
            )
        ]
    return {
        "pain001-lsp": [f"pain001-lsp-json-{VERSION}.vsix"],
        "pain001-mockbank": ["image.txt"],
        "pain001.github.io": [f"pain001-site-v{VERSION}.cdx.json"],
    }.get(name, [])


def test_complete_family_checks_every_channel() -> None:
    """A successful report names all nine repositories and their evidence."""
    report = ecosystem_audit.audit(Published())
    assert report["complete"] is True
    assert report["version"] == VERSION
    assert report["problems"] == []
    assert set(report["members"]) == set(NAMES)
    assert report["members"]["pain001-mockbank"]["image_platforms"] == [
        "linux/amd64",
        "linux/arm64",
    ]
    assert report["members"]["pain001.github.io"]["runtime"] == VERSION


@pytest.mark.parametrize("name", NAMES)
def test_any_missing_release_fails_the_family(name: str) -> None:
    """A missing non-PyPI member is as fatal as a missing core release."""
    published = Published()
    del published.data[API + name + "/releases/latest"]
    report = ecosystem_audit.audit(published)
    assert report["complete"] is False
    assert any(name in problem for problem in report["problems"])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "v0.0.82"),
        ("tag_name", "v0.0.81"),
        ("draft", True),
        ("prerelease", True),
        ("assets", []),
        ("body", "Incomplete notes"),
        ("body", None),
    ],
)
def test_invalid_release_metadata_is_not_a_publication(
    field: str, value: Any
) -> None:
    """A page existing on GitHub does not establish release completeness."""
    published = Published()
    published.data[API + "pain001-fast/releases/latest"][field] = value
    report = ecosystem_audit.audit(published)
    assert report["complete"] is False
    assert any("pain001-fast" in problem for problem in report["problems"])


def test_additional_asset_requires_a_checksum_in_the_notes() -> None:
    """Catch the facts file attached after the original MCP note audit."""
    published = Published()
    published.data[API + "pain001-mcp/releases/latest"]["assets"].append(
        {"name": "extra.facts.json", "digest": "sha256:" + "d" * 64}
    )
    report = ecosystem_audit.audit(published)
    assert report["complete"] is False
    assert any(
        "checksum" in p.lower() and "pain001-mcp" in p
        for p in report["problems"]
    )


def test_unsigned_tag_fails() -> None:
    """Tag annotations require GitHub's signature verification too."""
    published = Published()
    published.data[API + "pain001-fast/git/tags/" + "c" * 40]["verification"][
        "verified"
    ] = False
    report = ecosystem_audit.audit(published)
    assert report["complete"] is False


def test_stale_pypi_floor_is_reported() -> None:
    """Matching version labels do not establish a tested dependency pairing."""
    published = Published()
    published.data["https://pypi.org/pypi/pain001-mcp/json"]["info"][
        "requires_dist"
    ] = ["pain001>=0.0.81"]
    report = ecosystem_audit.audit(published)
    assert report["complete"] is False
    assert any("floor" in p for p in report["problems"])


def test_stale_website_is_reported() -> None:
    """A website release alone does not prove the browser demo deployed."""
    published = Published()
    published.data["https://pain001.com/pyodide/pain001-runtime.json"][
        "pain001"
    ] = "0.0.78"
    report = ecosystem_audit.audit(published)
    assert report["complete"] is False
    assert any("runtime" in p for p in report["problems"])


def test_missing_image_platform_fails() -> None:
    """Check the published image rather than a package-page version label."""
    published = Published()
    url = (
        "https://ghcr.io/v2/sebastienrousseau/pain001-mockbank/manifests/"
        + VERSION
    )
    published.data[url]["manifests"] = published.data[url]["manifests"][:1]
    report = ecosystem_audit.audit(published)
    assert report["complete"] is False
    assert any("platform" in p for p in report["problems"])


def test_unknown_repository_cannot_be_silently_omitted() -> None:
    """The committed table must keep up when the ecosystem grows."""
    published = Published()
    discovery = next(
        value
        for value in published.data.values()
        if isinstance(value, dict) and "items" in value
    )
    discovery["items"].append({"name": "pain001-new", "archived": False})
    discovery["total_count"] = 10
    report = ecosystem_audit.audit(published)
    assert report["complete"] is False
    assert any("inventory" in p for p in report["problems"])


def test_historical_audit_uses_the_requested_version() -> None:
    """An explicit version audits that release, independently of latest."""
    published = Published()
    for name in NAMES:
        published.data[API + name + "/releases/latest"] = {
            "tag_name": "v0.0.83"
        }
    report = ecosystem_audit.audit(published, version=VERSION)
    assert report["complete"] is True


@pytest.mark.parametrize("tag", [None, 82, "v0.0.82rc1", "v00.0.82"])
def test_invalid_core_version_is_a_structured_failure(tag: Any) -> None:
    """Unavailable or malformed core metadata cannot produce a traceback."""
    published = Published()
    published.data[API + "pain001/releases/latest"]["tag_name"] = tag
    report = ecosystem_audit.audit(published)
    assert report["complete"] is False
    assert report["problems"]


@pytest.mark.parametrize(
    ("version", "commit"), [("0.0.81", COMMIT), (VERSION, "d" * 40)]
)
def test_image_must_match_both_release_version_and_source(
    version: str, commit: str
) -> None:
    """An existing image at the right tag can still contain stale software."""
    published = Published()
    published.image("pain001-mockbank", version, commit)
    report = ecosystem_audit.audit(published)
    assert report["complete"] is False
    assert any("OCI image" in p for p in report["problems"])


def test_mcp_registry_is_a_required_publication() -> None:
    """PyPI success does not establish an active MCP Registry publication."""
    published = Published()
    endpoint = (
        "https://registry.modelcontextprotocol.io/v0.1/servers/io.github.sebastienrousseau%2Fpain001-mcp/versions/"
        + VERSION
    )
    del published.data[endpoint]
    report = ecosystem_audit.audit(published)
    assert report["complete"] is False
    assert any("pain001-mcp" in problem for problem in report["problems"])


@pytest.mark.parametrize(
    "name",
    [
        "pain001-lsp",
        "pain001-mockbank",
        "pain001-fast",
        "pain001-plugin-template",
        "pain001.github.io",
    ],
)
def test_required_artifacts_cannot_disappear_with_their_checksum_lines(
    name: str,
) -> None:
    """A consistent checksum list is insufficient if the payload is missing."""
    published = Published()
    release = published.data[API + name + "/releases/latest"]
    asset = (
        next(
            asset
            for asset in release["assets"]
            if asset["name"].endswith(".vsix")
        )
        if name == "pain001-lsp"
        else release["assets"][0]
    )
    release["assets"].remove(asset)
    release["body"] = release["body"].replace(
        "b" * 64 + "  " + asset["name"] + "\n", ""
    )
    report = ecosystem_audit.audit(published)
    assert report["complete"] is False
    assert any(
        name in problem and "required" in problem
        for problem in report["problems"]
    )


@pytest.mark.parametrize(
    "platform",
    [
        "linux_x86_64",
        "linux_aarch64",
        "macosx_11_0_arm64",
        "macosx_11_0_x86_64",
        "win_amd64",
    ],
)
def test_every_native_wheel_platform_is_required(platform: str) -> None:
    """The native release needs its full advertised wheel matrix."""
    published = Published()
    release = published.data[API + "pain001-fast/releases/latest"]
    filename = f"pain001_fast-{VERSION}-cp311-abi3-{platform}.whl"
    release["assets"] = [
        asset for asset in release["assets"] if asset["name"] != filename
    ]
    release["body"] = release["body"].replace(
        "b" * 64 + "  " + filename + "\n", ""
    )
    report = ecosystem_audit.audit(published)
    assert report["complete"] is False
    assert any(filename in problem for problem in report["problems"])
