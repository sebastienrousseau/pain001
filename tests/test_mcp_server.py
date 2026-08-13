# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""Tests for the Pain001 MCP server tools, resources, and prompt."""

import pytest

pytest.importorskip("mcp")

from pain001.constants import TEMPLATES_DIR  # noqa: E402
from pain001.csv.load_csv_data import load_csv_data  # noqa: E402
from pain001.mcp import server  # noqa: E402

_ROWS = load_csv_data(str(TEMPLATES_DIR / "pain.001.001.03" / "template.csv"))


class TestMcpTools:
    """The MCP tool adapters wrap the core functions."""

    def test_list_supported_versions(self) -> None:
        """Lists all bundled message types."""
        versions = server.list_supported_versions()
        assert "pain.001.001.03" in versions
        assert "pain.008.001.02" in versions

    def test_inspect_template(self) -> None:
        """Returns the expected columns for a message type."""
        info = server.inspect_template("pain.001.001.03")
        assert info["message_type"] == "pain.001.001.03"
        assert "id" in info["columns"]

    def test_inspect_template_unknown(self) -> None:
        """An unknown message type is rejected."""
        with pytest.raises(ValueError):
            server.inspect_template("pain.999.999.99")

    def test_generate_payment_file(self) -> None:
        """Generates validated XML from inline rows."""
        xml = server.generate_payment_file("pain.001.001.03", _ROWS)
        assert xml.startswith("<?xml")
        assert "pain.001.001.03" in xml

    def test_generate_payment_file_empty(self) -> None:
        """Empty rows are rejected."""
        with pytest.raises(ValueError):
            server.generate_payment_file("pain.001.001.03", [])

    def test_generate_payment_file_unknown_type(self) -> None:
        """An unknown message type is rejected."""
        with pytest.raises(ValueError):
            server.generate_payment_file("pain.999.999.99", _ROWS)

    def test_validate_payment_data(self) -> None:
        """Reports a schema-validation summary for the rows."""
        result = server.validate_payment_data("pain.001.001.03", _ROWS)
        assert result["total_rows"] == len(_ROWS)
        assert "errors" in result

    def test_validate_payment_data_unknown_type(self) -> None:
        """An unknown message type is rejected."""
        with pytest.raises(ValueError):
            server.validate_payment_data("pain.999.999.99", _ROWS)

    def test_validate_payment_scheme(self) -> None:
        """Runs scheme validation and returns structured violations."""
        result = server.validate_payment_scheme(_ROWS, profile="sepa-sct")
        assert result["profile"] == "sepa-sct"
        assert "violations" in result

    def test_schema_resource(self) -> None:
        """Returns the XSD text for a message type."""
        xsd = server.schema_resource("pain.001.001.03")
        assert "xs:schema" in xsd or "schema" in xsd

    def test_schema_resource_unknown(self) -> None:
        """An unknown message type is rejected."""
        with pytest.raises(ValueError):
            server.schema_resource("pain.999.999.99")

    def test_build_payment_batch_prompt(self) -> None:
        """The guided prompt mentions the workflow tools."""
        prompt = server.build_payment_batch("pain.001.001.03")
        assert "inspect_template" in prompt
        assert "generate_payment_file" in prompt

    def test_server_registered(self) -> None:
        """The MCPServer instance exists and is runnable."""
        assert server.mcp.name == "pain001"
        assert hasattr(server.mcp, "run")
