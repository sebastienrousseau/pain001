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

"""ISO 20022 payment data version migration utilities."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

import yaml

from pain001.constants import TEMPLATES_DIR
from pain001.csv.load_csv_data import load_csv_data
from pain001.db.load_db_data import load_db_data
from pain001.exceptions import DataSourceError
from pain001.json.load_json_data import load_json_data, load_jsonl_data
from pain001.parquet.load_parquet_data import load_parquet_data
from pain001.xml.generate_xml import generate_xml_string


class VersionMapper:
    """Migrate payment rows from older pain.001 variants to newer ones."""

    _MODERN_FIELDS = [
        "id",
        "date",
        "nb_of_txs",
        "initiator_name",
        "payment_id",
        "payment_method",
        "requested_execution_date",
        "debtor_name",
        "debtor_account_IBAN",
        "debtor_agent_BIC",
        "charge_bearer",
        "payment_amount",
        "payment_currency",
        "creditor_agent_BIC",
        "creditor_name",
        "creditor_account_IBAN",
        "remittance_information",
    ]

    def __init__(self) -> None:
        self.mappings_dir = Path(__file__).resolve().parent / "mappings"

    @staticmethod
    def normalize_version(version: str) -> str:
        """Normalize short or full version labels to vNN form."""
        raw = version.strip().lower()
        if raw.startswith("pain.001.001."):
            return f"v{raw.rsplit('.', maxsplit=1)[-1]}"
        if raw.startswith("v"):
            return raw
        return f"v{raw}"

    def load_mapping(self, from_version: str, to_version: str) -> dict[str, Any]:
        """Load YAML mapping or fall back to generic legacy-to-modern mapping."""
        source = self.normalize_version(from_version)
        target = self.normalize_version(to_version)
        mapping_file = self.mappings_dir / f"{source}_to_{target}.yaml"
        if mapping_file.exists():
            with open(mapping_file, encoding="utf-8") as handle:
                return yaml.safe_load(handle) or {}

        if self._is_supported_generic_pair(source, target):
            return self._generic_legacy_to_modern_mapping()

        raise DataSourceError(
            f"Unsupported migration path: {from_version} -> {to_version}"
        )

    @staticmethod
    def _is_supported_generic_pair(source: str, target: str) -> bool:
        legacy = {"v03", "v04", "v05", "v06", "v07", "v08"}
        modern = {"v09", "v10", "v11"}
        return source in legacy and target in modern

    def migrate_rows(
        self,
        rows: list[dict[str, Any]],
        from_version: str,
        to_version: str,
    ) -> list[dict[str, Any]]:
        """Migrate loaded payment rows to the target version shape."""
        if not rows:
            raise DataSourceError("No payment rows supplied for migration")

        mapping = self.load_mapping(from_version, to_version)
        migrated: list[dict[str, Any]] = []
        for row in rows:
            migrated_row: dict[str, Any] = {}
            for target_field, source_field in mapping.get("field_map", {}).items():
                migrated_row[target_field] = row.get(source_field, "")

            for target_field, candidates in mapping.get("fallbacks", {}).items():
                if migrated_row.get(target_field):
                    continue
                for candidate in candidates:
                    value = row.get(candidate, "")
                    if value not in ("", None):
                        migrated_row[target_field] = value
                        break

            for target_field, default_value in mapping.get("defaults", {}).items():
                if migrated_row.get(target_field) in ("", None):
                    migrated_row[target_field] = default_value

            migrated.append(migrated_row)

        self._normalize_group_fields(migrated)
        return migrated

    def migrate_file(
        self,
        source_path: str,
        from_version: str,
        to_version: str,
    ) -> list[dict[str, Any]]:
        """Load, migrate, and return payment rows from a source file."""
        rows = self._load_source_rows(source_path)
        return self.migrate_rows(rows, from_version, to_version)

    def write_csv(
        self,
        rows: list[dict[str, Any]],
        output_path: str,
    ) -> str:
        """Persist migrated rows as CSV."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self._MODERN_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return str(output)

    def validate_migrated_rows(
        self, rows: list[dict[str, Any]], to_version: str
    ) -> bool:
        """Validate migrated rows by generating target-version XML."""
        normalized = self.normalize_version(to_version)
        message_type = f"pain.001.001.{normalized[1:]}"
        template_dir = TEMPLATES_DIR / message_type
        template_path = template_dir / "template.xml"
        schema_path = template_dir / f"{message_type}.xsd"
        generate_xml_string(
            rows,
            message_type,
            str(template_path),
            str(schema_path),
        )
        return True

    @classmethod
    def default_output_path(
        cls, source_path: str, to_version: str
    ) -> str:
        """Build the default migrated CSV path next to the source file."""
        source = Path(source_path)
        normalized = cls.normalize_version(to_version)
        return str(source.with_name(f"{source.stem}_{normalized}.csv"))

    @staticmethod
    def _normalize_group_fields(rows: list[dict[str, Any]]) -> None:
        """Keep shared header values consistent across migrated rows."""
        first = rows[0]
        first.setdefault("nb_of_txs", str(len(rows)))
        for row in rows:
            for field in (
                "id",
                "date",
                "nb_of_txs",
                "initiator_name",
                "payment_method",
                "requested_execution_date",
                "debtor_name",
                "debtor_account_IBAN",
                "debtor_agent_BIC",
                "charge_bearer",
            ):
                if row.get(field) in ("", None):
                    row[field] = first.get(field, "")
            row.setdefault("payment_currency", "EUR")
            row.setdefault("payment_method", "TRF")
            row.setdefault("charge_bearer", "SLEV")
            if row.get("remittance_information") in ("", None):
                row["remittance_information"] = row.get("payment_id", "")

    @staticmethod
    def _generic_legacy_to_modern_mapping() -> dict[str, Any]:
        """Fallback mapping for legacy pain.001 rows to modern targets."""
        return {
            "field_map": {
                "id": "id",
                "date": "date",
                "nb_of_txs": "nb_of_txs",
                "initiator_name": "initiator_name",
                "payment_id": "payment_id",
                "payment_method": "payment_method",
                "requested_execution_date": "requested_execution_date",
                "debtor_name": "debtor_name",
                "debtor_account_IBAN": "debtor_account_IBAN",
                "debtor_agent_BIC": "debtor_agent_BIC",
                "charge_bearer": "charge_bearer",
                "payment_amount": "payment_amount",
                "payment_currency": "payment_currency",
                "creditor_agent_BIC": "creditor_agent_BIC",
                "creditor_name": "creditor_name",
                "creditor_account_IBAN": "creditor_account_IBAN",
            },
            "defaults": {
                "payment_method": "TRF",
                "charge_bearer": "SLEV",
            },
            "fallbacks": {
                "creditor_agent_BIC": ["creditor_agent_BIC", "creditor_agent_BICFI"],
                "remittance_information": [
                    "remittance_information",
                    "reference_number",
                    "payment_id",
                ],
            },
        }

    @staticmethod
    def _load_source_rows(source_path: str) -> list[dict[str, Any]]:
        """Load migration input without enforcing generation-time row validation."""
        ext = os.path.splitext(source_path)[1].lower()
        if ext == ".csv":
            return load_csv_data(source_path)
        if ext == ".db":
            return load_db_data(source_path, table_name="pain001")
        if ext == ".json":
            return load_json_data(source_path)
        if ext == ".jsonl":
            return load_jsonl_data(source_path)
        if ext == ".parquet":
            return load_parquet_data(source_path)
        raise DataSourceError(f"Unsupported migration source file: {source_path}")
