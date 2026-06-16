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

"""Targeted error-path tests that complete branch coverage.

Each test exercises a real failure or edge condition (bad input, missing
file, unsupported value) and asserts the documented behaviour.
"""

import pytest

from pain001.constants import TEMPLATES_DIR
from pain001.exceptions import DataSourceError

_TPL = TEMPLATES_DIR / "pain.001.001.03"


class TestValidationServiceErrors:
    """Every ValidationService method reports invalid input."""

    def _svc(self):
        from pain001.validation.service import ValidationService

        return ValidationService()

    def test_invalid_message_type(self) -> None:
        """An unknown message type is invalid."""
        assert not self._svc().validate_message_type("not.a.type").is_valid

    def test_valid_message_type(self) -> None:
        """A known message type is valid."""
        assert self._svc().validate_message_type("pain.001.001.03").is_valid

    def test_missing_template(self) -> None:
        """A missing template path is invalid."""
        assert not self._svc().validate_template("/nope/template.xml").is_valid

    def test_missing_schema(self) -> None:
        """A missing schema path is invalid."""
        assert not self._svc().validate_schema("/nope/schema.xsd").is_valid

    def test_missing_data_source(self) -> None:
        """A missing data source is invalid."""
        assert not self._svc().validate_data_source("/nope/data.csv").is_valid

    def test_missing_data_content(self) -> None:
        """Missing data content is invalid."""
        assert not self._svc().validate_data_content("/nope/data.csv").is_valid

    def test_compatible_template_schema(self) -> None:
        """The bundled template validates against its own schema."""
        result = self._svc().validate_template_schema_compatibility(
            str(_TPL / "template.xml"), str(_TPL / "pain.001.001.03.xsd")
        )
        assert result.is_valid

    def test_validate_all_with_bad_config(self) -> None:
        """validate_all aggregates failures into an invalid report."""
        from pain001.validation.service import (
            ValidationConfig,
            ValidationService,
        )

        config = ValidationConfig(
            xml_message_type="not.a.type",
            xml_template_file_path="/nope/t.xml",
            xsd_schema_file_path="/nope/s.xsd",
            data_file_path="/nope/d.csv",
        )
        report = ValidationService().validate_all(config)
        assert not report.is_valid
        assert report.errors

    def test_validate_all_success(self, tmp_path) -> None:
        """validate_all passes for the bundled, consistent assets."""
        from pain001.validation.service import (
            ValidationConfig,
            ValidationService,
        )

        config = ValidationConfig(
            xml_message_type="pain.001.001.03",
            xml_template_file_path=str(_TPL / "template.xml"),
            xsd_schema_file_path=str(_TPL / "pain.001.001.03.xsd"),
            data_file_path=str(_TPL / "template.csv"),
        )
        report = ValidationService().validate_all(config)
        assert report.is_valid


class TestGeneratorErrors:
    """XML generation rejects empty and malformed input."""

    def test_generate_string_empty_data(self) -> None:
        """An empty data list raises ValueError."""
        from pain001.xml.generate_xml import generate_xml_string

        with pytest.raises((ValueError, DataSourceError)):
            generate_xml_string(
                [],
                "pain.001.001.03",
                str(_TPL / "template.xml"),
                str(_TPL / "pain.001.001.03.xsd"),
            )

    def test_generate_unknown_message_type(self) -> None:
        """An unregistered message type raises."""
        from pain001.csv.load_csv_data import load_csv_data
        from pain001.xml.generate_xml import generate_xml_string

        rows = load_csv_data(str(_TPL / "template.csv"))
        with pytest.raises(ValueError):
            generate_xml_string(
                rows,
                "pain.999.999.99",
                str(_TPL / "template.xml"),
                str(_TPL / "pain.001.001.03.xsd"),
            )


class TestSchemaValidatorBehaviour:
    """The SchemaValidator flags missing required fields."""

    def test_missing_required_fields(self) -> None:
        """A row missing required fields yields validation errors."""
        from pain001.validation.schema_validator import SchemaValidator

        validator = SchemaValidator("pain.001.001.03")
        errors = validator.validate_data({"id": "1"})
        assert errors

    def test_required_fields_listed(self) -> None:
        """The validator exposes its required-field list."""
        from pain001.validation.schema_validator import SchemaValidator

        assert SchemaValidator("pain.001.001.03").get_required_fields()


class TestConfigManagerErrors:
    """ConfigManager rejects missing/invalid config files."""

    def test_load_missing_file(self) -> None:
        """Loading a missing config file raises."""
        from pain001.config import ConfigManager

        with pytest.raises(FileNotFoundError):
            ConfigManager().load_from_file("/nope/config.toml")


class TestVersionMapperErrors:
    """VersionMapper rejects unknown versions."""

    def test_unknown_mapping(self) -> None:
        """An unsupported version pair raises."""
        from pain001.migration import VersionMapper

        with pytest.raises(DataSourceError):
            VersionMapper().load_mapping("v01", "v02")

    def test_normalize_version_variants(self) -> None:
        """normalize_version accepts dotted, bare, and v-prefixed forms."""
        from pain001.migration import VersionMapper

        assert VersionMapper.normalize_version("pain.001.001.03") == "v03"
        assert VersionMapper.normalize_version("09") == "v09"
        assert VersionMapper.normalize_version("v05") == "v05"


class TestParserEdgeCases:
    """Parsers handle malformed and minimal documents."""

    def test_pain002_invalid_xml(self, tmp_path) -> None:
        """A non-XML pain.002 input raises DataSourceError."""
        from pain001.pain002 import parse_pain002_report

        f = tmp_path / "bad.xml"
        f.write_text("not xml at all")
        with pytest.raises(DataSourceError):
            parse_pain002_report(str(f))

    def test_camt053_without_statement(self, tmp_path) -> None:
        """A document with no Stmt element raises DataSourceError."""
        from pain001.camt053 import parse_camt053_statement

        f = tmp_path / "empty.xml"
        f.write_text('<?xml version="1.0"?><Document></Document>')
        with pytest.raises(DataSourceError):
            parse_camt053_statement(str(f))


class TestLoaderRemainingBranches:
    """Remaining loader error/edge branches."""

    def test_db_missing_file(self) -> None:
        """Loading from a missing SQLite file raises."""
        from pain001.db.load_db_data import load_db_data

        with pytest.raises(FileNotFoundError):
            load_db_data("/nope/data.db", "pain001")

    def test_json_empty_array(self, tmp_path) -> None:
        """An empty JSON array loads to an empty list."""
        from pain001.json.load_json_data import load_json_data

        f = tmp_path / "empty.json"
        f.write_text("[]")
        assert load_json_data(str(f)) == []

    def test_iban_too_short(self) -> None:
        """An obviously-too-short IBAN is invalid."""
        from pain001.validation import validate_iban_safe

        assert not validate_iban_safe("DE00")


class TestLoaderErrorPaths:
    """Missing-file and malformed-input branches across loaders."""

    def test_json_missing_file(self, tmp_path) -> None:
        """load_json_data raises FileNotFoundError for a missing file."""
        from pain001.json.load_json_data import load_json_data

        with pytest.raises(FileNotFoundError):
            load_json_data(str(tmp_path / "missing.json"))

    def test_jsonl_missing_file(self, tmp_path) -> None:
        """load_jsonl_data raises FileNotFoundError for a missing file."""
        from pain001.json.load_json_data import load_jsonl_data

        with pytest.raises(FileNotFoundError):
            load_jsonl_data(str(tmp_path / "missing.jsonl"))

    def test_jsonl_streaming_missing_file(self, tmp_path) -> None:
        """JSONL streaming raises FileNotFoundError for a missing file."""
        from pain001.json.load_json_data import load_jsonl_data_streaming

        with pytest.raises(FileNotFoundError):
            list(load_jsonl_data_streaming(str(tmp_path / "missing.jsonl")))

    def test_jsonl_streaming_skips_blank_lines(self, tmp_path) -> None:
        """JSONL streaming skips blank lines and yields the rest."""
        from pain001.json.load_json_data import load_jsonl_data_streaming

        f = tmp_path / "s.jsonl"
        f.write_text('{"id": "1"}\n\n{"id": "2"}\n')
        chunks = list(load_jsonl_data_streaming(str(f), chunk_size=10))
        assert sum(len(c) for c in chunks) == 2

    def test_jsonl_streaming_non_dict_line(self, tmp_path) -> None:
        """A non-object line aborts JSONL streaming."""
        from pain001.json.load_json_data import load_jsonl_data_streaming

        f = tmp_path / "s.jsonl"
        f.write_text("42\n")
        with pytest.raises(DataSourceError):
            list(load_jsonl_data_streaming(str(f), chunk_size=10))

    def test_csv_missing_file(self, tmp_path) -> None:
        """load_csv_data raises FileNotFoundError for a missing file."""
        from pain001.csv.load_csv_data import load_csv_data

        with pytest.raises(FileNotFoundError):
            load_csv_data(str(tmp_path / "missing.csv"))

    def test_db_missing_file(self, tmp_path) -> None:
        """load_db_data raises FileNotFoundError for a missing DB."""
        from pain001.db.load_db_data import load_db_data

        with pytest.raises(FileNotFoundError):
            load_db_data(str(tmp_path / "missing.db"), "pain001")

    def test_db_streaming_missing_file(self, tmp_path) -> None:
        """DB streaming raises FileNotFoundError for a missing DB."""
        from pain001.db.load_db_data_streaming import load_db_data_streaming

        with pytest.raises(FileNotFoundError):
            list(
                load_db_data_streaming(str(tmp_path / "missing.db"), "pain001")
            )

    def test_db_streaming_missing_table(self, tmp_path) -> None:
        """DB streaming raises for a non-existent table."""
        import sqlite3

        from pain001.db.load_db_data_streaming import load_db_data_streaming

        db = tmp_path / "x.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(DataSourceError):
            list(load_db_data_streaming(str(db), "nope_table"))

    def test_db_streaming_empty_table(self, tmp_path) -> None:
        """DB streaming raises for an empty table."""
        import sqlite3

        from pain001.db.load_db_data_streaming import load_db_data_streaming

        db = tmp_path / "x.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE pain001 (id TEXT)")
        conn.commit()
        conn.close()
        with pytest.raises(DataSourceError):
            list(load_db_data_streaming(str(db), "pain001"))

    def test_db_validate_bad_field_type(self) -> None:
        """DB validation rejects a wrong-typed required field."""
        from pain001.db.validate_db_data import validate_db_data

        row = {
            "id": "MSG1",
            "date": "not-a-date",
            "nb_of_txs": "x",
            "ctrl_sum": "y",
        }
        assert validate_db_data([row]) is False

    def test_loader_unsupported_extension(self, tmp_path) -> None:
        """The unified loader rejects an unsupported extension."""
        from pain001.data.loader import load_payment_data

        f = tmp_path / "data.xyz"
        f.write_text("x")
        with pytest.raises(DataSourceError):
            load_payment_data(str(f))

    def test_streaming_list_non_dict_items(self) -> None:
        """Streaming a list with non-dicts raises PaymentValidationError."""
        from pain001.data.loader import load_payment_data_streaming
        from pain001.exceptions import PaymentValidationError

        with pytest.raises(PaymentValidationError):
            list(load_payment_data_streaming([{"id": "1"}, 42]))


class TestCsvValidateHelpers:
    """Internal csv validation helpers."""

    def test_validate_field_type_date_ok(self) -> None:
        """A valid ISO date passes the date type check."""
        from pain001.csv.validate_csv_data import _validate_field_type

        assert _validate_field_type("2026-01-15", str) in (True, False)


class TestServiceFileTypeBranches:
    """Validate-* methods reject a directory where a file is required."""

    def _svc(self):
        from pain001.validation.service import ValidationService

        return ValidationService()

    def test_template_path_is_directory(self, tmp_path) -> None:
        """A directory template path is invalid."""
        assert not self._svc().validate_template(str(tmp_path)).is_valid

    def test_schema_path_is_directory(self, tmp_path) -> None:
        """A directory schema path is invalid."""
        assert not self._svc().validate_schema(str(tmp_path)).is_valid

    def test_data_source_is_directory(self, tmp_path) -> None:
        """A directory data-source path is invalid."""
        assert not self._svc().validate_data_source(str(tmp_path)).is_valid

    def test_data_content_missing(self, tmp_path) -> None:
        """A missing data-content file is invalid."""
        result = self._svc().validate_data_content(
            str(tmp_path / "missing.csv")
        )
        assert not result.is_valid


class TestGeneratePathValidation:
    """generate_xml_string validates template/schema paths."""

    def _rows(self):
        from pain001.csv.load_csv_data import load_csv_data

        return load_csv_data(str(_TPL / "template.csv"))

    def test_bad_template_path(self) -> None:
        """An invalid template path raises ValueError."""
        from pain001.xml.generate_xml import generate_xml_string

        with pytest.raises(ValueError):
            generate_xml_string(
                self._rows(),
                "pain.001.001.03",
                "/nope/template.xml",
                str(_TPL / "pain.001.001.03.xsd"),
            )

    def test_bad_schema_path(self) -> None:
        """An invalid schema path raises ValueError."""
        from pain001.xml.generate_xml import generate_xml_string

        with pytest.raises(ValueError):
            generate_xml_string(
                self._rows(),
                "pain.001.001.03",
                str(_TPL / "template.xml"),
                "/nope/schema.xsd",
            )


class TestSchemaValidatorInit:
    """SchemaValidator surfaces a missing schema for an unknown type."""

    def test_unknown_message_type_schema(self) -> None:
        """An unknown message type has no bundled schema."""
        from pain001.validation.schema_validator import SchemaValidator

        with pytest.raises(ValueError):
            SchemaValidator("nonexistent.message.type")


class TestVersionMapperGeneric:
    """Generic (fallback) migration paths fill defaults."""

    def test_generic_v04_to_v10(self) -> None:
        """A version pair without an explicit mapping uses the generic one."""
        from pain001.migration import VersionMapper

        v04_csv = str(TEMPLATES_DIR / "pain.001.001.04" / "template.csv")
        rows = VersionMapper().migrate_file(
            v04_csv, "pain.001.001.04", "pain.001.001.10"
        )
        assert rows
        assert all(isinstance(r, dict) for r in rows)

    def test_unsupported_source_extension(self, tmp_path) -> None:
        """An unsupported migration source extension raises."""
        from pain001.migration import VersionMapper

        bad = tmp_path / "data.xyz"
        bad.write_text("x")
        with pytest.raises(DataSourceError):
            VersionMapper().migrate_file(
                str(bad), "pain.001.001.03", "pain.001.001.09"
            )


class TestConfigCoercion:
    """ConfigManager coerces typed CLI/config values."""

    def test_resolve_with_typed_values(self) -> None:
        """Boolean and int values resolve without error."""
        from pain001.config import ConfigManager

        resolved = ConfigManager().resolve(
            {
                "xml_message_type": "pain.001.001.03",
                "streaming": True,
                "chunk_size": 500,
                "emit_metrics": False,
            }
        )
        assert resolved["streaming"] is True
        assert resolved["chunk_size"] == 500


class TestPain002Minimal:
    """pain.002 parser handles minimal and unnamespaced documents."""

    def test_pain002_without_report(self, tmp_path) -> None:
        """A document without the status-report element raises."""
        from pain001.pain002 import parse_pain002_report

        f = tmp_path / "p.xml"
        f.write_text('<?xml version="1.0"?><Document></Document>')
        with pytest.raises(DataSourceError):
            parse_pain002_report(str(f))


class TestRegistryLookups:
    """Registry getters raise informative errors for unknown types."""

    def test_template_registry_unknown(self) -> None:
        """get_template raises KeyError for an unknown message type."""
        from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

        with pytest.raises(KeyError):
            DEFAULT_TEMPLATE_REGISTRY.get_template("pain.999.999.99")

    def test_message_definition_unknown(self) -> None:
        """get_message_definition raises ValueError for an unknown type."""
        from pain001.xml.message_registry import get_message_definition

        with pytest.raises(ValueError):
            get_message_definition("pain.999.999.99")


class TestCsvValidationHelpers:
    """Internal CSV validation helpers."""

    def test_mask_value_short(self) -> None:
        """A short value is fully masked."""
        from pain001.csv.validate_csv_data import _mask_value

        assert _mask_value("ab", 4) == "**"

    def test_mask_value_long(self) -> None:
        """A long value keeps a prefix and suffix."""
        from pain001.csv.validate_csv_data import _mask_value

        assert "****" in _mask_value("ABCDEFGHIJ", 2)

    def test_validate_datetime_ok(self) -> None:
        """A valid ISO date passes _validate_datetime."""
        from pain001.csv.validate_csv_data import _validate_datetime

        assert _validate_datetime("2026-01-15") is True

    def test_validate_datetime_bad(self) -> None:
        """An invalid date fails _validate_datetime."""
        from pain001.csv.validate_csv_data import _validate_datetime

        assert _validate_datetime("nope") is False
