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

"""Registry-driven XML message preparation pipeline."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from pain001.exceptions import PaymentValidationError

XmlDataPreparer = Callable[[list[dict[str, Any]]], dict[str, Any]]

_ALIAS_HINT = (
    "aliases are accepted ('amount' for payment_amount, 'currency' for "
    "payment_currency); nb_of_txs and ctrl_sum are computed automatically"
)


def _currency(row: dict[str, Any]) -> str:
    """Return the transaction currency, accepting either canonical key."""
    value = row.get("payment_currency") or row.get("currency") or ""
    return str(value).strip()


def _missing(row: dict[str, Any], fields: Sequence[str]) -> list[str]:
    """List the fields absent or blank in ``row``, preserving order."""
    missing: list[str] = []
    for field in fields:
        value = row.get(field)
        if value is None or str(value).strip() == "":
            missing.append(field)
    return missing


def _require_fields(
    data: list[dict[str, Any]],
    message_type: str,
    header_fields: Sequence[str],
    row_fields: Sequence[str],
    currency_required: bool = False,
) -> None:
    """Raise a single, complete error for every missing required field.

    Collects the missing header fields (from the first row) and the missing
    per-transaction fields (from every row) so a caller learns the whole
    shortfall in one shot instead of one KeyError per retry.

    Args:
        data: The payment rows.
        message_type: The target message type, used in the error text.
        header_fields: Fields required on the first row (message header).
        row_fields: Fields required on every row (one per transaction).
        currency_required: Whether each row must carry a currency
            (``payment_currency`` or its ``currency`` alias).

    Raises:
        PaymentValidationError: Listing every missing field at once.
    """
    problems: list[str] = []
    header_missing = _missing(data[0], header_fields)
    if header_missing:
        problems.append(", ".join(header_missing))
    for index, row in enumerate(data, start=1):
        row_missing = _missing(row, row_fields)
        if currency_required and not _currency(row):
            row_missing.append("currency (or payment_currency)")
        if row_missing:
            problems.append(f"row {index}: {', '.join(row_missing)}")
    if problems:
        raise PaymentValidationError(
            f"Missing required fields for {message_type}: "
            f"{'; '.join(problems)}. Provide them in one call - "
            f"{_ALIAS_HINT}.",
            field="records",
        )


def _prepare_xml_data_v03(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Prepare XML data for pain.001.001.03 message type."""
    _require_fields(
        data,
        "pain.001.001.03",
        header_fields=[
            "id",
            "date",
            "initiator_name",
            "initiator_street_name",
            "initiator_building_number",
            "initiator_postal_code",
            "initiator_town_name",
            "initiator_country_code",
            "payment_id",
            "requested_execution_date",
            "debtor_name",
            "debtor_street_name",
            "debtor_building_number",
            "debtor_postal_code",
            "debtor_town_name",
            "debtor_country_code",
            "debtor_account_IBAN",
            "debtor_agent_BIC",
        ],
        row_fields=[
            "payment_id",
            "creditor_agent_BIC",
            "creditor_name",
            "creditor_street_name",
            "creditor_building_number",
            "creditor_postal_code",
            "creditor_town_name",
            "creditor_country_code",
            "creditor_account_IBAN",
            "purpose_code",
            "reference_number",
            "reference_date",
        ],
        currency_required=True,
    )
    return {
        "id": data[0]["id"],
        "date": data[0]["date"],
        "nb_of_txs": data[0].get("nb_of_txs", len(data)),
        "initiator_name": data[0]["initiator_name"],
        "initiator_street_name": data[0]["initiator_street_name"],
        "initiator_building_number": data[0]["initiator_building_number"],
        "initiator_postal_code": data[0]["initiator_postal_code"],
        "initiator_town_name": data[0]["initiator_town_name"],
        "initiator_country_code": data[0]["initiator_country_code"],
        "payment_id": data[0]["payment_id"],
        "payment_method": data[0].get("payment_method", "TRF"),
        "batch_booking": data[0].get("batch_booking", "false"),
        "requested_execution_date": data[0]["requested_execution_date"],
        "debtor_name": data[0]["debtor_name"],
        "debtor_street_name": data[0]["debtor_street_name"],
        "debtor_building_number": data[0]["debtor_building_number"],
        "debtor_postal_code": data[0]["debtor_postal_code"],
        "debtor_town_name": data[0]["debtor_town_name"],
        "debtor_country_code": data[0]["debtor_country_code"],
        "debtor_account_IBAN": data[0]["debtor_account_IBAN"],
        "debtor_agent_BIC": data[0]["debtor_agent_BIC"],
        "charge_bearer": data[0].get("charge_bearer", "SLEV"),
        "transactions": [
            {
                "payment_id": row["payment_id"],
                "payment_amount": row.get("payment_amount", ""),
                "payment_currency": _currency(row),
                "charge_bearer": row.get("charge_bearer", "SLEV"),
                "creditor_agent_BIC": row["creditor_agent_BIC"],
                "creditor_name": row["creditor_name"],
                "creditor_street_name": row["creditor_street_name"],
                "creditor_building_number": row["creditor_building_number"],
                "creditor_postal_code": row["creditor_postal_code"],
                "creditor_town_name": row["creditor_town_name"],
                "creditor_country_code": row["creditor_country_code"],
                "creditor_account_IBAN": row["creditor_account_IBAN"],
                "purpose_code": row["purpose_code"],
                "reference_number": row["reference_number"],
                "reference_date": row["reference_date"],
            }
            for row in data
        ],
    }


def _prepare_xml_data_v04(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Prepare XML data for pain.001.001.04 message type."""
    return {
        "id": data[0].get("id", ""),
        "date": data[0].get("date", ""),
        "nb_of_txs": data[0].get("nb_of_txs", ""),
        "initiator_name": data[0].get("initiator_name", ""),
        "initiator_street": data[0].get("initiator_street_name", ""),
        "initiator_building_number": data[0].get(
            "initiator_building_number", ""
        ),
        "initiator_postal_code": data[0].get("initiator_postal_code", ""),
        "initiator_town": data[0].get("initiator_town_name", ""),
        "initiator_country": data[0].get("initiator_country_code", ""),
        "payment_information_id": data[0].get("payment_id", ""),
        "payment_method": data[0].get("payment_method", ""),
        "batch_booking": data[0].get("batch_booking", ""),
        "requested_execution_date": data[0].get(
            "requested_execution_date", ""
        ),
        "debtor_name": data[0].get("debtor_name", ""),
        "debtor_street": data[0].get("debtor_street_name", ""),
        "debtor_building_number": data[0].get("debtor_building_number", ""),
        "debtor_postal_code": data[0].get("debtor_postal_code", ""),
        "debtor_town": data[0].get("debtor_town_name", ""),
        "debtor_country": data[0].get("debtor_country_code", ""),
        "debtor_account_IBAN": data[0].get("debtor_account_IBAN", ""),
        "debtor_agent_BIC": data[0].get("debtor_agent_BIC", ""),
        "debtor_agent_account_IBAN": data[0].get(
            "debtor_agent_account_IBAN", ""
        ),
        "instruction_for_debtor_agent": data[0].get(
            "instruction_for_debtor_agent", ""
        ),
        "charge_bearer": data[0].get("charge_bearer", ""),
        "charge_account_IBAN": data[0].get("charge_account_IBAN", ""),
        "charge_agent_BICFI": data[0].get("charge_agent_BICFI", ""),
        "payment_instruction_id": data[0].get(
            "payment_instruction_id", data[0].get("payment_id", "")
        ),
        "payment_end_to_end_id": data[0].get(
            "payment_end_to_end_id", data[0].get("reference_number", "")
        ),
        "payment_currency": data[0].get("payment_currency", ""),
        "payment_amount": data[0].get("payment_amount", ""),
        "creditor_agent_BIC": data[0].get("creditor_agent_BIC", ""),
        "creditor_name": data[0].get("creditor_name", ""),
        "creditor_street": data[0].get("creditor_street_name", ""),
        "creditor_building_number": data[0].get(
            "creditor_building_number", ""
        ),
        "creditor_postal_code": data[0].get("creditor_postal_code", ""),
        "creditor_town": data[0].get("creditor_town_name", ""),
        "creditor_account_IBAN": data[0].get("creditor_account_IBAN", ""),
        "purpose_code": data[0].get("purpose_code", ""),
        "reference_number": data[0].get("reference_number", ""),
        "reference_date": data[0].get("reference_date", ""),
        "transactions": [
            {
                "payment_instruction_id": row.get("payment_id", ""),
                "payment_end_to_end_id": row.get("reference_number", ""),
                "payment_currency": row.get("payment_currency", "EUR"),
                "payment_amount": row.get("payment_amount", ""),
                "charge_bearer": row.get("charge_bearer", ""),
                "creditor_agent_BIC": row.get("creditor_agent_BIC", ""),
                "creditor_name": row.get("creditor_name", ""),
                "creditor_street": row.get("creditor_street_name", ""),
                "creditor_building_number": row.get(
                    "creditor_building_number", ""
                ),
                "creditor_postal_code": row.get("creditor_postal_code", ""),
                "creditor_town": row.get("creditor_town_name", ""),
                "creditor_account_IBAN": row.get("creditor_account_IBAN", ""),
                "purpose_code": row.get("purpose_code", ""),
                "reference_number": row.get("reference_number", ""),
                "reference_date": row.get("reference_date", ""),
            }
            for row in data
        ],
    }


def _prepare_xml_data_v05_to_v08(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Prepare XML data for pain.001.001.05-08 message types."""
    return {
        "id": data[0].get("id", ""),
        "date": data[0].get("date", ""),
        "nb_of_txs": data[0].get("nb_of_txs", ""),
        "ctrl_sum": data[0].get("ctrl_sum", ""),
        "initiator_name": data[0].get("initiator_name", ""),
        "initiator_street_name": data[0].get("initiator_street_name", ""),
        "initiator_building_number": data[0].get(
            "initiator_building_number", ""
        ),
        "initiator_postal_code": data[0].get("initiator_postal_code", ""),
        "initiator_town": data[0].get(
            "initiator_town_name", data[0].get("initiator_town", "")
        ),
        "initiator_country": data[0].get(
            "initiator_country_code", data[0].get("initiator_country", "")
        ),
        "ultimate_debtor_name": data[0].get(
            "ultimate_debtor_name", data[0].get("debtor_name", "")
        ),
        "service_level_code": data[0].get("service_level_code", "SEPA"),
        "requested_execution_date": data[0].get(
            "requested_execution_date", ""
        ),
        "payment_information_id": data[0].get("payment_information_id", ""),
        "payment_method": data[0].get("payment_method", "TRF"),
        "batch_booking": data[0].get("batch_booking", "false"),
        "debtor_name": data[0].get("debtor_name", ""),
        "debtor_street": data[0].get("debtor_street_name", ""),
        "debtor_building_number": data[0].get("debtor_building_number", ""),
        "debtor_postal_code": data[0].get("debtor_postal_code", ""),
        "debtor_town": data[0].get("debtor_town_name", ""),
        "debtor_country": data[0].get(
            "debtor_country_code", data[0].get("debtor_country", "")
        ),
        "debtor_account_IBAN": data[0].get("debtor_account_IBAN", ""),
        "debtor_agent_BIC": data[0].get("debtor_agent_BIC", ""),
        "transactions": [
            {
                "payment_id": row.get("payment_id", ""),
                "payment_instruction_id": row.get(
                    "payment_instruction_id", row.get("payment_id", "")
                ),
                "payment_end_to_end_id": row.get(
                    "payment_end_to_end_id", row.get("reference_number", "")
                ),
                "payment_amount": row.get("payment_amount", ""),
                "payment_currency": _currency(row),
                "charge_bearer": row.get("charge_bearer", "SLEV"),
                "creditor_agent_BIC": row.get(
                    "creditor_agent_BIC", row.get("creditor_agent_BICFI", "")
                ),
                "creditor_name": row.get("creditor_name", ""),
                "creditor_street": row.get("creditor_street_name", ""),
                "creditor_building_number": row.get(
                    "creditor_building_number", ""
                ),
                "creditor_postal_code": row.get("creditor_postal_code", ""),
                "creditor_town": row.get("creditor_town_name", ""),
                "creditor_country": row.get(
                    "creditor_country_code", row.get("creditor_country", "")
                ),
                "creditor_account_IBAN": row.get("creditor_account_IBAN", ""),
                "creditor_agent_BICFI": row.get("creditor_agent_BICFI", ""),
                "purpose_code": row.get("purpose_code", ""),
                "reference_number": row.get("reference_number", ""),
                "reference_date": row.get("reference_date", ""),
                "remittance_information": row.get(
                    "remittance_information", ""
                ),
            }
            for row in data
        ],
    }


def _prepare_xml_data_v09_to_v12(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Prepare XML data for pain.001.001.09-12 message types.

    The transaction currency accepts both canonical spellings
    (``payment_currency`` and the JSON Schemas' ``currency``); a missing
    currency is reported explicitly rather than silently rendering an
    empty ``Ccy`` attribute that only fails later at XSD validation.
    """
    _require_fields(
        data,
        "pain.001.001.09",
        header_fields=[
            "id",
            "date",
            "initiator_name",
            "payment_id",
            "requested_execution_date",
            "debtor_name",
            "debtor_account_IBAN",
            "debtor_agent_BIC",
        ],
        row_fields=[
            "payment_id",
            "payment_amount",
            "creditor_agent_BIC",
            "creditor_name",
            "creditor_account_IBAN",
        ],
        currency_required=True,
    )
    return {
        "id": data[0]["id"],
        "date": data[0]["date"],
        "nb_of_txs": data[0].get("nb_of_txs", len(data)),
        "initiator_name": data[0]["initiator_name"],
        "payment_id": data[0]["payment_id"],
        "payment_method": data[0].get("payment_method", "TRF"),
        "payment_nb_of_txs": data[0].get("nb_of_txs", len(data)),
        "requested_execution_date": data[0]["requested_execution_date"],
        "debtor_name": data[0]["debtor_name"],
        "debtor_account_IBAN": data[0]["debtor_account_IBAN"],
        "debtor_agent_BIC": data[0]["debtor_agent_BIC"],
        "charge_bearer": data[0].get("charge_bearer", "SLEV"),
        "transactions": [
            {
                "payment_id": row["payment_id"],
                "payment_amount": row["payment_amount"],
                "payment_currency": _currency(row),
                "charge_bearer": row.get("charge_bearer", "SLEV"),
                "creditor_agent_BIC": row["creditor_agent_BIC"],
                "creditor_name": row["creditor_name"],
                "creditor_account_IBAN": row["creditor_account_IBAN"],
                "remittance_information": row.get(
                    "remittance_information", ""
                ),
                "supplementary_data": row.get("supplementary_data", ""),
            }
            for row in data
        ],
    }


def _prepare_xml_data_v08_direct_debit(
    data: list[dict[str, Any]],
) -> dict[str, Any]:
    """Prepare XML data for pain.008.001.02 direct debit messages."""
    return {
        "id": data[0].get("id", ""),
        "date": data[0].get("date", ""),
        "nb_of_txs": data[0].get("nb_of_txs", ""),
        "ctrl_sum": data[0].get("ctrl_sum", ""),
        "initiator_name": data[0].get("initiator_name", ""),
        "payment_information_id": data[0].get("payment_information_id", ""),
        "payment_method": data[0].get("payment_method", "DD"),
        "batch_booking": str(data[0].get("batch_booking", "false")).lower(),
        "service_level_code": data[0].get("service_level_code", "SEPA"),
        "requested_execution_date": data[0].get(
            "requested_execution_date", ""
        ),
        "debtor_name": data[0].get("debtor_name", ""),
        "debtor_account_IBAN": data[0].get("debtor_account_IBAN", ""),
        "debtor_agent_BIC": data[0].get("debtor_agent_BIC", ""),
        "charge_bearer": data[0].get("charge_bearer", "SLEV"),
        "transactions": [
            {
                "payment_id": row.get("payment_id", ""),
                "payment_amount": row.get("payment_amount", ""),
                "payment_currency": row.get(
                    "payment_currency", row.get("currency", "EUR")
                ),
                "creditor_agent_BIC": row.get("creditor_agent_BIC", ""),
                "creditor_name": row.get("creditor_name", ""),
                "creditor_account_IBAN": row.get("creditor_account_IBAN", ""),
                "remittance_information": row.get(
                    "remittance_information", ""
                ),
                "mandate_id": row.get("mandate_id", ""),
                "date_of_signature": row.get("date_of_signature", ""),
                "sequence_type": row.get("sequence_type", "RCUR"),
            }
            for row in data
        ],
    }


@dataclass(frozen=True)
class MessageDefinition:
    """Registry entry for a supported message type."""

    message_type: str
    family: str
    preparer: XmlDataPreparer


MESSAGE_REGISTRY: dict[str, MessageDefinition] = {
    "pain.001.001.03": MessageDefinition(
        "pain.001.001.03", "legacy_v03", _prepare_xml_data_v03
    ),
    "pain.001.001.04": MessageDefinition(
        "pain.001.001.04", "legacy_v04", _prepare_xml_data_v04
    ),
    "pain.001.001.05": MessageDefinition(
        "pain.001.001.05", "legacy_v05_to_v08", _prepare_xml_data_v05_to_v08
    ),
    "pain.001.001.06": MessageDefinition(
        "pain.001.001.06", "legacy_v05_to_v08", _prepare_xml_data_v05_to_v08
    ),
    "pain.001.001.07": MessageDefinition(
        "pain.001.001.07", "legacy_v05_to_v08", _prepare_xml_data_v05_to_v08
    ),
    "pain.001.001.08": MessageDefinition(
        "pain.001.001.08", "legacy_v05_to_v08", _prepare_xml_data_v05_to_v08
    ),
    "pain.001.001.09": MessageDefinition(
        "pain.001.001.09", "modern_v09_to_v12", _prepare_xml_data_v09_to_v12
    ),
    "pain.001.001.10": MessageDefinition(
        "pain.001.001.10", "modern_v09_to_v12", _prepare_xml_data_v09_to_v12
    ),
    "pain.001.001.11": MessageDefinition(
        "pain.001.001.11", "modern_v09_to_v12", _prepare_xml_data_v09_to_v12
    ),
    "pain.001.001.12": MessageDefinition(
        "pain.001.001.12", "modern_v09_to_v12", _prepare_xml_data_v09_to_v12
    ),
    "pain.008.001.02": MessageDefinition(
        "pain.008.001.02",
        "direct_debit_v02",
        _prepare_xml_data_v08_direct_debit,
    ),
}


def get_message_definition(message_type: str) -> MessageDefinition:
    """Return the registry entry for a supported message type."""
    try:
        return MESSAGE_REGISTRY[message_type]
    except KeyError as exc:
        raise ValueError(f"Invalid XML message type: {message_type}") from exc


def prepare_xml_data(
    data: list[dict[str, Any]], message_type: str
) -> dict[str, Any]:
    """Prepare XML payload using the registry-driven pipeline."""
    return get_message_definition(message_type).preparer(data)
