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
# See the License for the specific language governing permissions and
# limitations under the License.

"""Feature-matrix regression suite.

One end-to-end regression guard per documented Pain001 feature, mapped to
the README feature set. This complements the focused unit suite: it pins
the *behaviour* of every user-facing capability so a future change cannot
silently break a feature.

Coverage map (feature -> test class):

- XML generation, all 11 message types ...... TestGenerationMatrix
- Input formats (CSV/SQLite/JSON/JSONL/Parquet) TestInputFormats
- Library API (process_files, string, streaming) TestLibraryApi
- CLI (generate, dry-run, streaming, discovery) TestCliFeatures
- Scheme-aware validation (SCT/SDD/charset) ... TestSchemeFeatures
- REST API (all endpoints) .................... TestRestApi
- Parsers (pain.002, camt.053) ................ TestParsers
- Version migration ........................... TestMigration
- Observability hooks ......................... TestObservability
"""

import json
import os

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from pain001 import (
    generate_xml_string,
    parse_camt053_statement,
    parse_pain002_report,
    process_files,
    sanitize_to_charset,
    validate_scheme,
)
from pain001.api.app import app
from pain001.cli.cli import main
from pain001.constants import TEMPLATES_DIR, valid_xml_types
from pain001.csv.load_csv_data import load_csv_data
from pain001.data.loader import load_payment_data
from pain001.db.load_db_data import load_db_data

client = TestClient(app)

#: Every message type Pain001 can generate (source of truth: constants).
ALL_MESSAGE_TYPES = list(valid_xml_types)
_FIXTURES = "pain001/test_fixtures"


def _assets(message_type: str) -> tuple[str, str, str]:
    """Return (template.xml, xsd, template.csv) paths for a message type."""
    base = TEMPLATES_DIR / message_type
    return (
        str(base / "template.xml"),
        str(base / f"{message_type}.xsd"),
        str(base / "template.csv"),
    )


class TestGenerationMatrix:
    """Every supported message type generates valid ISO 20022 XML."""

    def test_all_message_types_are_present(self) -> None:
        """The matrix covers all ten pain.001 versions plus pain.008."""
        assert "pain.008.001.02" in ALL_MESSAGE_TYPES
        assert len([m for m in ALL_MESSAGE_TYPES if "pain.001" in m]) == 10

    @pytest.mark.parametrize("message_type", ALL_MESSAGE_TYPES)
    def test_generate_string_is_valid_xml(self, message_type: str) -> None:
        """generate_xml_string yields XSD-valid XML for each type."""
        template, xsd, csv = _assets(message_type)
        data = load_csv_data(csv)
        xml = generate_xml_string(data, message_type, template, xsd)
        assert xml.startswith("<?xml")
        assert message_type in xml  # the ISO 20022 namespace carries it

    @pytest.mark.parametrize("message_type", ALL_MESSAGE_TYPES)
    def test_process_files_writes_output(
        self, message_type: str, tmp_path
    ) -> None:
        """process_files writes a validated file for each type."""
        template, xsd, csv = _assets(message_type)
        out = process_files(
            message_type,
            template,
            xsd,
            csv,
            output_path=str(tmp_path / "out.xml"),
        )
        assert os.path.exists(out)
        assert os.path.getsize(out) > 0


class TestInputFormats:
    """Every input format normalises into the same payment rows."""

    MESSAGE_TYPE = "pain.001.001.03"

    def test_csv(self) -> None:
        """CSV input loads into payment rows."""
        _, _, csv = _assets(self.MESSAGE_TYPE)
        assert load_payment_data(csv)

    def test_sqlite(self) -> None:
        """SQLite input loads from the bundled 'pain001' table."""
        base = TEMPLATES_DIR / self.MESSAGE_TYPE
        rows = load_db_data(str(base / "template.db"), "pain001")
        assert rows

    def test_json_and_jsonl(self, tmp_path) -> None:
        """JSON array and JSON Lines inputs both load."""
        _, _, csv = _assets(self.MESSAGE_TYPE)
        rows = load_csv_data(csv)

        json_file = tmp_path / "data.json"
        json_file.write_text(json.dumps(rows))
        assert load_payment_data(str(json_file))

        jsonl_file = tmp_path / "data.jsonl"
        jsonl_file.write_text("\n".join(json.dumps(r) for r in rows))
        assert load_payment_data(str(jsonl_file))

    def test_parquet(self, tmp_path) -> None:
        """Parquet input loads when pyarrow is available."""
        pd = pytest.importorskip("pandas")
        _, _, csv = _assets(self.MESSAGE_TYPE)
        rows = load_csv_data(csv)
        parquet_file = tmp_path / "data.parquet"
        pd.DataFrame(rows).to_parquet(parquet_file)
        assert load_payment_data(str(parquet_file))


class TestLibraryApi:
    """The programmatic API accepts files and in-memory rows."""

    MESSAGE_TYPE = "pain.001.001.03"

    def test_process_files_accepts_list_of_dicts(self, tmp_path) -> None:
        """process_files accepts a list[dict] instead of a file path."""
        template, xsd, csv = _assets(self.MESSAGE_TYPE)
        rows = load_csv_data(csv)
        out = process_files(
            self.MESSAGE_TYPE,
            template,
            xsd,
            rows,
            output_path=str(tmp_path / "out.xml"),
        )
        assert os.path.exists(out)

    def test_generate_xml_string_in_memory(self) -> None:
        """generate_xml_string returns XML without touching disk."""
        template, xsd, csv = _assets(self.MESSAGE_TYPE)
        xml = generate_xml_string(
            load_csv_data(csv), self.MESSAGE_TYPE, template, xsd
        )
        assert "<?xml" in xml


class TestCliFeatures:
    """Each documented CLI capability works end to end."""

    def setup_method(self) -> None:
        """Create a Click runner per test."""
        self.runner = CliRunner()

    def _args(self, message_type: str) -> list[str]:
        template, xsd, csv = _assets(message_type)
        return ["-t", message_type, "-m", template, "-s", xsd, "-d", csv]

    def test_help(self) -> None:
        """--help exits 0 and prints usage."""
        result = self.runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Usage" in result.output or "pain001" in result.output

    def test_list_templates(self) -> None:
        """--list-templates lists the bundled message types."""
        result = self.runner.invoke(main, ["--list-templates"])
        assert result.exit_code == 0
        assert "pain.001.001.03" in result.output

    def test_show_template(self) -> None:
        """--show-template prints metadata for one type."""
        result = self.runner.invoke(
            main, ["--show-template", "pain.001.001.12"]
        )
        assert result.exit_code == 0

    def test_dry_run(self) -> None:
        """--dry-run validates without generating, exit 0."""
        result = self.runner.invoke(
            main, [*self._args("pain.001.001.03"), "--dry-run"]
        )
        assert result.exit_code == 0

    def test_generate_to_output_dir(self, tmp_path) -> None:
        """Generation writes an XML file to -o."""
        result = self.runner.invoke(
            main,
            [*self._args("pain.001.001.03"), "-o", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert list(tmp_path.glob("*.xml"))

    def test_streaming(self, tmp_path) -> None:
        """--streaming chunks input into multiple files."""
        result = self.runner.invoke(
            main,
            [
                *self._args("pain.001.001.03"),
                "--streaming",
                "--chunk-size",
                "2",
                "-o",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert list(tmp_path.glob("*.xml"))

    def test_invalid_message_type_exits_2(self) -> None:
        """An invalid message type exits 2."""
        template, xsd, csv = _assets("pain.001.001.03")
        result = self.runner.invoke(
            main, ["-t", "pain.999", "-m", template, "-s", xsd, "-d", csv]
        )
        assert result.exit_code == 2


class TestSchemeFeatures:
    """Scheme rulebook validation and the charset guard."""

    def _row(self) -> dict[str, object]:
        return {
            "payment_currency": "EUR",
            "debtor_account_IBAN": "DE89370400440532013000",
            "creditor_account_IBAN": "FR1420041010050500013M02606",
            "payment_amount": "100.00",
            "service_level_code": "SEPA",
            "mandate_id": "MND-1",
            "sequence_type": "RCUR",
        }

    def test_sepa_sct_pass_and_fail(self) -> None:
        """SCT accepts a compliant row and flags a non-EUR one."""
        assert validate_scheme([self._row()], "sepa-sct").is_valid
        bad = self._row() | {"payment_currency": "USD"}
        assert not validate_scheme([bad], "sepa-sct").is_valid

    def test_sepa_sdd_mandate_rule(self) -> None:
        """SDD flags a missing mandate id."""
        bad = self._row() | {"mandate_id": ""}
        result = validate_scheme([bad], "sepa-sdd")
        assert not result.is_valid
        assert any(v.rule == "SDD-MNDT" for v in result.violations)

    def test_charset_sanitisation(self) -> None:
        """The charset guard transliterates accented text."""
        assert sanitize_to_charset("Café Zürich") == "Cafe Zurich"


class TestRestApi:
    """Every REST endpoint responds as documented."""

    _CSV = "pain001/templates/pain.001.001.03/template.csv"

    def test_health(self) -> None:
        """GET /api/health is healthy."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_validate(self) -> None:
        """POST /api/validate returns a validation report."""
        response = client.post(
            "/api/validate",
            json={
                "data_source": "csv",
                "file_path": self._CSV,
                "message_type": "pain.001.001.03",
            },
        )
        assert response.status_code == 200
        assert "is_valid" in response.json()

    def test_validate_with_scheme(self) -> None:
        """POST /api/validate honours a scheme."""
        response = client.post(
            "/api/validate",
            json={
                "data_source": "csv",
                "file_path": self._CSV,
                "message_type": "pain.001.001.03",
                "scheme": "sepa-sct",
            },
        )
        assert response.status_code == 200
        assert "scheme_violations" in response.json()

    def test_async_job_lifecycle(self) -> None:
        """POST /api/generate/async returns a job that can be polled."""
        response = client.post(
            "/api/generate/async",
            json={
                "data_source": "csv",
                "file_path": self._CSV,
                "message_type": "pain.001.001.03",
            },
        )
        assert response.status_code in (200, 202)
        job_id = response.json()["job_id"]
        status = client.get(f"/api/status/{job_id}")
        assert status.status_code == 200
        assert status.json()["job_id"] == job_id

    def test_openapi_docs(self) -> None:
        """Interactive docs are served."""
        assert client.get("/api/docs").status_code == 200


class TestParsers:
    """The pain.002 and camt.053 parsers read bundled samples."""

    def test_pain002_parser(self) -> None:
        """parse_pain002_report returns a structured dict."""
        result = parse_pain002_report(f"{_FIXTURES}/pain002_sample.xml")
        assert isinstance(result, dict)
        assert result

    def test_camt053_parser(self) -> None:
        """parse_camt053_statement returns a structured dict."""
        result = parse_camt053_statement(f"{_FIXTURES}/camt053_sample.xml")
        assert isinstance(result, dict)
        assert result


class TestMigration:
    """Version migration maps payment data between pain.001 versions."""

    def test_migrate_v03_to_v09(self, tmp_path) -> None:
        """VersionMapper maps v03 payment data to v09 and writes CSV."""
        from pain001.migration import VersionMapper

        _, _, csv = _assets("pain.001.001.03")
        mapper = VersionMapper()
        rows = mapper.migrate_file(csv, "pain.001.001.03", "pain.001.001.09")
        mapper.validate_migrated_rows(rows, "pain.001.001.09")
        out = tmp_path / "migrated.csv"
        mapper.write_csv(rows, str(out))
        assert out.exists()
        assert out.read_text().strip()


class TestObservability:
    """Metric callbacks fire during processing."""

    def test_metric_callback_receives_events(self, tmp_path) -> None:
        """A registered callback receives metric events."""
        from pain001 import (
            clear_metrics_callbacks,
            register_metrics_callback,
        )

        events = []
        register_metrics_callback(lambda e: events.append(e))
        try:
            template, xsd, csv = _assets("pain.001.001.03")
            process_files(
                "pain.001.001.03",
                template,
                xsd,
                csv,
                output_path=str(tmp_path / "out.xml"),
            )
        finally:
            clear_metrics_callbacks()
        assert events
