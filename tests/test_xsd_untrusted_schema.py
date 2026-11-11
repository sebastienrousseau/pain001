# SPDX-License-Identifier: Apache-2.0 OR MIT
"""A user-supplied ``--schema`` is local data, not a network client.

xmlschema fetched a remote ``xs:import`` and lxml expanded entities in
the XSD by default. Both loaders now refuse the network and DTDs.
"""

from __future__ import annotations

import threading
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from pain001.xml import validate_via_xsd as module

DOC = "<root><element>TOPSECRET</element></root>"


@pytest.fixture
def listener() -> Iterator[tuple[str, list[str]]]:
    """A loopback HTTP server that records every request it receives."""
    hits: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server's name
            hits.append(self.path)
            self.send_response(404)
            self.end_headers()

        def log_message(self, *args: object) -> None:
            return None

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", hits
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """xmlschema opens local files with urlopen too; only file: may pass."""
    real = urllib.request.urlopen

    def local_only(url: object, *args: object, **kwargs: object) -> object:
        target = getattr(url, "full_url", url)
        if not str(target).startswith("file:"):
            pytest.fail(f"network fetch attempted: {target!r}")
        return real(url, *args, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", local_only)


def _schema(tmp_path: Path, body: str, prolog: str = "") -> str:
    path = tmp_path / "user.xsd"
    path.write_text(
        prolog
        + '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        + body
        + '<xs:element name="root"><xs:complexType><xs:sequence>'
        '<xs:element name="element" type="Value"/>'
        "</xs:sequence></xs:complexType></xs:element></xs:schema>",
        encoding="utf-8",
    )
    return str(path)


def test_a_remote_import_is_never_fetched(tmp_path, listener):
    base, hits = listener
    xsd = _schema(
        tmp_path,
        f'<xs:import namespace="urn:example:remote" '
        f'schemaLocation="{base}/remote.xsd"/>'
        '<xs:simpleType name="Value"><xs:restriction base="xs:string"/>'
        "</xs:simpleType>",
    )
    xml = tmp_path / "doc.xml"
    xml.write_text(DOC, encoding="utf-8")
    with pytest.warns(Warning, match="block access to remote resource"):
        assert module.validate_xml_string_via_xsd(DOC, xsd)
        assert module.validate_via_xsd(str(xml), xsd)
        assert module.collect_xsd_validation_errors(DOC, xsd) == []
    assert hits == []


def test_entities_in_a_schema_are_not_expanded(tmp_path):
    """lxml 5 still expands internal entities (billion laughs) by default."""
    xsd = _schema(
        tmp_path,
        '<xs:simpleType name="Value"><xs:restriction base="xs:string">'
        '<xs:enumeration value="&secret;"/></xs:restriction></xs:simpleType>',
        prolog='<!DOCTYPE xs:schema [<!ENTITY secret "TOPSECRET">]>',
    )
    assert not module.validate_xml_string_via_xsd(DOC, xsd)
    assert module.collect_xsd_validation_errors(DOC, xsd)


def test_bundled_schemas_still_validate():
    schema = next(
        Path(module.__file__)
        .parents[1]
        .glob("templates/pain.001.001.09/*.xsd")
    )
    loaded = module._get_cached_schema(str(schema))
    assert loaded.target_namespace.endswith("pain.001.001.09")
    assert module._get_cached_lxml_schema(str(schema)) is not None
