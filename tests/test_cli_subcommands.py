# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.

"""Tests for the Pain001 CLI subcommand suite and backwards-compat routing."""

import json
from unittest.mock import patch

from click.testing import CliRunner

from pain001.cli.cli import cli

DATA = "examples/data/payments.csv"
MTYPE = "pain.001.001.03"


class TestGroupAndRouting:
    """The top-level group, versioning, and default-command routing."""

    def setup_method(self) -> None:
        """Provide a fresh Click runner per test."""
        self.runner = CliRunner()

    def test_group_help_lists_subcommands(self) -> None:
        """`--help` lists every subcommand in the suite."""
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for name in ("generate", "validate", "versions", "inspect", "init"):
            assert name in result.output

    def test_version_option(self) -> None:
        """`--version` prints the package version and exits 0."""
        result = self.runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "pain001" in result.output

    def test_bare_flags_route_to_generate(self) -> None:
        """Legacy `pain001 -t ... -d ... --dry-run` still works."""
        result = self.runner.invoke(
            cli, ["-t", MTYPE, "-d", DATA, "--dry-run"]
        )
        assert result.exit_code == 0
        assert "validations passed" in result.output.lower()

    def test_explicit_generate_subcommand(self) -> None:
        """`generate` is reachable explicitly as well as by default."""
        result = self.runner.invoke(
            cli, ["generate", "-t", MTYPE, "-d", DATA, "--dry-run"]
        )
        assert result.exit_code == 0


class TestValidateCommand:
    """The `validate` subcommand (a named `generate --dry-run`)."""

    def setup_method(self) -> None:
        """Provide a fresh Click runner per test."""
        self.runner = CliRunner()

    def test_validate_passes(self) -> None:
        """Valid data validates with exit code 0 and no XML written."""
        result = self.runner.invoke(cli, ["validate", "-t", MTYPE, "-d", DATA])
        assert result.exit_code == 0
        assert "no XML generated" in result.output

    def test_validate_with_scheme(self) -> None:
        """`--scheme` runs scheme validation under the validate command."""
        result = self.runner.invoke(
            cli, ["validate", "-t", MTYPE, "-d", DATA, "--scheme", "sepa-sct"]
        )
        assert result.exit_code in (0, 1)


class TestVersionsCommand:
    """The `versions` subcommand."""

    def setup_method(self) -> None:
        """Provide a fresh Click runner per test."""
        self.runner = CliRunner()

    def test_versions_table(self) -> None:
        """The default output names a known message type."""
        result = self.runner.invoke(cli, ["versions"])
        assert result.exit_code == 0
        assert MTYPE in result.output

    def test_versions_json(self) -> None:
        """`--json` emits a parseable array containing the known types."""
        result = self.runner.invoke(cli, ["versions", "--json"])
        assert result.exit_code == 0
        assert MTYPE in json.loads(result.output)


class TestInspectCommand:
    """The `inspect` subcommand."""

    def setup_method(self) -> None:
        """Provide a fresh Click runner per test."""
        self.runner = CliRunner()

    def test_inspect_text(self) -> None:
        """Text output reports the template's category."""
        result = self.runner.invoke(cli, ["inspect", MTYPE])
        assert result.exit_code == 0
        assert "category" in result.output

    def test_inspect_json(self) -> None:
        """JSON output round-trips the message type and input formats."""
        result = self.runner.invoke(cli, ["inspect", MTYPE, "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["message_type"] == MTYPE
        assert "csv" in payload["input_formats"]

    def test_inspect_unknown_type(self) -> None:
        """An unknown type exits 2 with an error message."""
        result = self.runner.invoke(cli, ["inspect", "pain.999.999.99"])
        assert result.exit_code == 2
        assert "Unknown message type" in result.output


class TestInitCommand:
    """The `init` subcommand."""

    def setup_method(self) -> None:
        """Provide a fresh Click runner per test."""
        self.runner = CliRunner()

    def test_init_writes_starter_csv(self, tmp_path) -> None:
        """A starter CSV is written and is non-empty."""
        out = tmp_path / "starter.csv"
        result = self.runner.invoke(cli, ["init", MTYPE, "-o", str(out)])
        assert result.exit_code == 0
        assert out.is_file()
        assert out.read_text().strip()

    def test_init_default_destination(self) -> None:
        """Without -o, the CSV lands at ./<message_type>.csv."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["init", MTYPE])
            assert result.exit_code == 0
            assert "Wrote starter CSV" in result.output

    def test_init_unknown_type(self) -> None:
        """An unknown type exits 2."""
        result = self.runner.invoke(cli, ["init", "pain.999.999.99"])
        assert result.exit_code == 2


class TestServeCommand:
    """The `serve` subcommand (REST API launcher)."""

    def setup_method(self) -> None:
        """Provide a fresh Click runner per test."""
        self.runner = CliRunner()

    def test_serve_invokes_uvicorn(self) -> None:
        """`serve` binds the configured host/port via uvicorn.run."""
        with patch("uvicorn.run") as run:
            result = self.runner.invoke(
                cli, ["serve", "--host", "0.0.0.0", "--port", "9100"]
            )
            assert result.exit_code == 0
            run.assert_called_once()
            assert run.call_args.kwargs["host"] == "0.0.0.0"
            assert run.call_args.kwargs["port"] == 9100

    def test_serve_without_api_extra(self) -> None:
        """A missing uvicorn yields a helpful exit-2 error."""
        with patch.dict("sys.modules", {"uvicorn": None}):
            result = self.runner.invoke(cli, ["serve"])
            assert result.exit_code == 2
            assert "api" in result.output.lower()


class TestMcpCommand:
    """The `mcp` subcommand (MCP server launcher)."""

    def setup_method(self) -> None:
        """Provide a fresh Click runner per test."""
        self.runner = CliRunner()

    def test_mcp_invokes_server_main(self) -> None:
        """`mcp` delegates to the MCP server entry point."""
        import sys
        from types import ModuleType

        fake = ModuleType("pain001.mcp.server")
        called = {}
        fake.main = lambda: called.setdefault("ran", True)  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"pain001.mcp.server": fake}):
            result = self.runner.invoke(cli, ["mcp"])
        assert result.exit_code == 0
        assert called.get("ran") is True

    def test_mcp_without_extra(self) -> None:
        """A missing mcp extra yields a helpful exit-2 error."""
        import sys

        with patch.dict(sys.modules, {"pain001.mcp.server": None}):
            result = self.runner.invoke(cli, ["mcp"])
        assert result.exit_code == 2
        assert "mcp" in result.output.lower()
