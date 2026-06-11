# Copyright (C) 2023-2026 Sebastien Rousseau.
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

"""Parametrized template/schema asset tests for all pain.001 versions.

Replaces the nine near-identical test_pain001_v03..v11 modules with one
parametrized suite covering the live generation path
(``generate_xml_string``) plus the bundled assets (XSD, Jinja2 template,
CSV and SQLite fixtures) for every supported message version.
"""

import csv
import sqlite3
import xml.etree.ElementTree as et  # nosec B405 - parsing trusted test assets
from pathlib import Path

import pytest

from pain001.constants import valid_xml_types
from pain001.xml.generate_xml import generate_xml_string

VERSIONS = list(valid_xml_types)

TEMPLATES_ROOT = Path("pain001/templates")


def _template_dir(version: str) -> Path:
    return TEMPLATES_ROOT / version


def _load_csv_rows(version: str) -> list:
    csv_path = _template_dir(version) / "template.csv"
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.version_compat
@pytest.mark.parametrize("version", VERSIONS)
class TestVersionAssets:
    """Bundled asset sanity checks per message version."""

    def test_xsd_exists(self, version):
        xsd = _template_dir(version) / f"{version}.xsd"
        assert xsd.exists(), f"XSD file not found: {xsd}"

    def test_jinja2_template_exists_and_has_variables(self, version):
        template = _template_dir(version) / "template.xml"
        assert template.exists(), f"Template not found: {template}"
        content = template.read_text(encoding="utf-8")
        assert "{{" in content and "}}" in content

    def test_csv_template_has_required_columns(self, version):
        csv_path = _template_dir(version) / "template.csv"
        assert csv_path.exists(), f"CSV template not found: {csv_path}"
        with open(csv_path, encoding="utf-8") as f:
            headers = csv.DictReader(f).fieldnames
        assert headers is not None
        for col in ["id", "date", "nb_of_txs", "initiator_name"]:
            assert col in headers, f"Missing required column: {col}"

    def test_db_template_is_valid_sqlite(self, version):
        db_path = _template_dir(version) / "template.db"
        assert db_path.exists(), f"DB template not found: {db_path}"
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            assert cursor.fetchall() is not None
        finally:
            conn.close()


@pytest.mark.version_compat
@pytest.mark.parametrize("version", VERSIONS)
class TestVersionGeneration:
    """Live generation path checks per message version."""

    def test_generate_xml_string_well_formed(self, version):
        data = _load_csv_rows(version)[:2]
        template = _template_dir(version) / "template.xml"
        xsd = _template_dir(version) / f"{version}.xsd"

        xml_string = generate_xml_string(
            data, version, str(template), str(xsd)
        )

        root = et.fromstring(xml_string)  # nosec B314 - output we generated
        assert root is not None
        assert version in xml_string
        expected_root = (
            "CstmrDrctDbtInitn"
            if version.startswith("pain.008")
            else "CstmrCdtTrfInitn"
        )
        assert expected_root in xml_string
        assert "GrpHdr" in xml_string
        assert "PmtInf" in xml_string
