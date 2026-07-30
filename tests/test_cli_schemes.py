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

"""End-to-end CLI tests for the --scheme rulebook flags."""

import json
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from pain001.cli.cli import main
from pain001.constants import TEMPLATES_DIR

_TPL = TEMPLATES_DIR / "pain.001.001.03"

_SEPA_VALID_ROW = {
    "payment_currency": "EUR",
    "debtor_account_IBAN": "DE89370400440532013000",
    "creditor_account_IBAN": "FR1420041010050500013M02606",
    "creditor_agent_BIC": "DEUTDEFF",
    "service_level_code": "SEPA",
    "payment_amount": "100.00",
    "debtor_name": "John Doe",
    "creditor_name": "Acme Corp",
    "remittance_information": "Invoice 12345",
}

# A row that passes XSD but breaks SEPA SCT: a non-EUR currency and an
# IBAN with a bad mod-97 checksum. The tests inject this explicitly rather
# than relying on the bundled sample being non-compliant (it is compliant).
_SEPA_VIOLATING_ROW = {
    **_SEPA_VALID_ROW,
    "payment_currency": "USD",
    "debtor_account_IBAN": "DE00INVALIDIBAN0000000",
}


def _base_args() -> list[str]:
    """Return CLI args pointing at the bundled pain.001.001.03 assets."""
    return [
        "-t",
        "pain.001.001.03",
        "-m",
        str(_TPL / "template.xml"),
        "-s",
        str(_TPL / "pain.001.001.03.xsd"),
        "-d",
        str(_TPL / "template.csv"),
    ]


class TestCliScheme(unittest.TestCase):
    """The bundled sample passes XSD but breaks SEPA SCT rules."""

    def setUp(self) -> None:
        """Set up a Click test runner."""
        self.runner = CliRunner()

    def test_scheme_text_reports_violations(self) -> None:
        """--scheme prints per-row violations and exits 1."""
        with patch(
            "pain001.cli.cli.load_payment_data",
            return_value=[dict(_SEPA_VIOLATING_ROW)],
        ):
            result = self.runner.invoke(
                main, [*_base_args(), "--scheme", "sepa-sct", "--dry-run"]
            )
        assert result.exit_code == 1
        assert "SEPA-" in result.output

    def test_scheme_explain_prints_remediation(self) -> None:
        """--explain adds a remediation hint under each violation."""
        with patch(
            "pain001.cli.cli.load_payment_data",
            return_value=[dict(_SEPA_VIOLATING_ROW)],
        ):
            result = self.runner.invoke(
                main,
                [
                    *_base_args(),
                    "--scheme",
                    "sepa-sct",
                    "--explain",
                    "--dry-run",
                ],
            )
        assert result.exit_code == 1
        assert "fix:" in result.output

    def test_scheme_json_output(self) -> None:
        """--scheme-format json emits a parseable result object."""
        with patch(
            "pain001.cli.cli.load_payment_data",
            return_value=[dict(_SEPA_VIOLATING_ROW)],
        ):
            result = self.runner.invoke(
                main,
                [
                    *_base_args(),
                    "--scheme",
                    "sepa-sct",
                    "--scheme-format",
                    "json",
                    "--dry-run",
                ],
            )
        assert result.exit_code == 1
        payload = next(
            json.loads(line)
            for line in result.output.splitlines()
            if line.startswith("{")
        )
        assert payload["profile"] == "sepa-sct"
        assert payload["is_valid"] is False
        assert payload["violations"]

    def test_unknown_scheme_exits_2(self) -> None:
        """An unknown profile name exits with code 2."""
        result = self.runner.invoke(
            main, [*_base_args(), "--scheme", "nope", "--dry-run"]
        )
        assert result.exit_code == 2

    def test_unknown_scheme_json_exits_2(self) -> None:
        """An unknown profile in JSON mode emits an error object, exit 2."""
        result = self.runner.invoke(
            main,
            [
                *_base_args(),
                "--scheme",
                "nope",
                "--scheme-format",
                "json",
                "--dry-run",
            ],
        )
        assert result.exit_code == 2
        assert '"error"' in result.output

    def test_scheme_gates_generation(self) -> None:
        """Without --dry-run, a scheme failure blocks generation."""
        with patch(
            "pain001.cli.cli.load_payment_data",
            return_value=[dict(_SEPA_VIOLATING_ROW)],
        ):
            result = self.runner.invoke(
                main, [*_base_args(), "--scheme", "sepa-sct"]
            )
        assert result.exit_code == 1
        assert "validation failed" in result.output.lower()

    def test_scheme_passes_for_compliant_data(self) -> None:
        """A SEPA-compliant row passes the scheme check (exit 0)."""
        with patch(
            "pain001.cli.cli.load_payment_data",
            return_value=[dict(_SEPA_VALID_ROW)],
        ):
            result = self.runner.invoke(
                main, [*_base_args(), "--scheme", "sepa-sct", "--dry-run"]
            )
        assert result.exit_code == 0
        assert "passed" in result.output.lower()

    def test_scheme_json_passes_for_compliant_data(self) -> None:
        """JSON output reports is_valid=True for compliant data (exit 0)."""
        with patch(
            "pain001.cli.cli.load_payment_data",
            return_value=[dict(_SEPA_VALID_ROW)],
        ):
            result = self.runner.invoke(
                main,
                [
                    *_base_args(),
                    "--scheme",
                    "sepa-sct",
                    "--scheme-format",
                    "json",
                    "--dry-run",
                ],
            )
        assert result.exit_code == 0
        payload = next(
            json.loads(line)
            for line in result.output.splitlines()
            if line.startswith("{")
        )
        assert payload["is_valid"] is True
        assert payload["violations"] == []


class TestCliDataFailureTips(unittest.TestCase):
    """The CLI prints format-specific tips when data loading fails."""

    def setUp(self) -> None:
        """Set up a Click test runner."""
        self.runner = CliRunner()

    def _args(self, data_path: str) -> list[str]:
        return [
            "-t",
            "pain.001.001.03",
            "-m",
            str(_TPL / "template.xml"),
            "-s",
            str(_TPL / "pain.001.001.03.xsd"),
            "-d",
            data_path,
            "--dry-run",
        ]

    def test_json_failure_tip(self) -> None:
        """A JSON load failure prints a JSON-specific tip."""
        with patch("pain001.cli.cli.validate_via_xsd", return_value=True):
            with patch(
                "pain001.cli.cli.load_payment_data",
                side_effect=ValueError("bad json"),
            ):
                result = self.runner.invoke(main, self._args("data.json"))
        assert result.exit_code == 1
        assert "json" in result.output.lower()

    def test_parquet_failure_tip(self) -> None:
        """A Parquet load failure prints a pyarrow tip."""
        with patch("pain001.cli.cli.validate_via_xsd", return_value=True):
            with patch(
                "pain001.cli.cli.load_payment_data",
                side_effect=ValueError("bad parquet"),
            ):
                result = self.runner.invoke(main, self._args("data.parquet"))
        assert result.exit_code == 1
        assert "pyarrow" in result.output.lower()


class TestCliVerboseTraceback(unittest.TestCase):
    """The generation handler prints a traceback under --verbose."""

    def setUp(self) -> None:
        """Set up a Click test runner."""
        self.runner = CliRunner()

    def test_verbose_traceback_on_unexpected_error(self) -> None:
        """A generation error with --verbose prints a traceback, exit 1."""
        with patch(
            "pain001.cli.cli.process_files",
            side_effect=RuntimeError("boom"),
        ):
            with patch("pain001.cli.cli.validate_via_xsd", return_value=True):
                result = self.runner.invoke(main, [*_base_args(), "--verbose"])
        assert result.exit_code == 1
        assert "traceback" in result.output.lower()
