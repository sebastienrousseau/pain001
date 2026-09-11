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


def _one_of_missing(
    row: dict[str, Any], groups: Sequence[tuple[str, ...]]
) -> list[str]:
    """Groups where none of the alternatives is present, as ``a (or b)``."""
    missing: list[str] = []
    for group in groups:
        if _missing(row, group) == list(group):
            missing.append(f"{group[0]} (or {', '.join(group[1:])})")
    return missing


def _require_fields(
    data: list[dict[str, Any]],
    message_type: str,
    header_fields: Sequence[str],
    row_fields: Sequence[str],
    currency_required: bool = False,
    header_one_of: Sequence[tuple[str, ...]] = (),
    row_one_of: Sequence[tuple[str, ...]] = (),
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
        header_one_of: Groups of header fields of which one is required
            (an IBAN or an account number; a BIC or a clearing member id).
        row_one_of: The same for every row.

    Raises:
        PaymentValidationError: Listing every missing field at once.
    """
    problems: list[str] = []
    header_missing = _missing(data[0], header_fields) + _one_of_missing(
        data[0], header_one_of
    )
    if header_missing:
        problems.append(", ".join(header_missing))
    for index, row in enumerate(data, start=1):
        row_missing = _missing(row, row_fields) + _one_of_missing(
            row, row_one_of
        )
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
    """Prepare XML data for pain.001.001.03.

    The same vocabulary as the .09 family: an account is an IBAN or a
    number with a scheme, an agent a BIC or a clearing member id, and
    every other column is optional and rendered only when given. The
    columns the first version of this preparer demanded (addresses,
    purpose, referred document) are now optional; the referred document
    (``reference_number``, ``reference_date``) is still rendered when
    present. An LEI, a UETR and a date-time execution date have no
    element in .03 and are ignored.
    """
    _require_fields(
        data,
        "pain.001.001.03",
        header_fields=[
            "id",
            "date",
            "initiator_name",
            "payment_id",
            "requested_execution_date",
            "debtor_name",
        ],
        row_fields=["payment_id", "payment_amount", "creditor_name"],
        currency_required=True,
        header_one_of=[
            ("debtor_account_IBAN", "debtor_account_number"),
            ("debtor_agent_BIC", "debtor_agent_member_id"),
        ],
        row_one_of=[
            ("creditor_account_IBAN", "creditor_account_number"),
            ("creditor_agent_BIC", "creditor_agent_member_id"),
        ],
    )
    context = _context_v09(data)
    for tx, row in zip(context["transactions"], data, strict=True):
        tx["reference_number"] = _text(row, "reference_number")
        tx["reference_date"] = _text(row, "reference_date")
    context["requested_execution_date"] = _text(
        data[0], "requested_execution_date"
    )[:10]
    if context["batch_booking"] is None:
        context["batch_booking"] = "false"  # .03 always rendered it
    return context


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


def _text(row: dict[str, Any], key: str) -> str:
    """The row's value as stripped text, empty when absent."""
    value = row.get(key)
    return "" if value is None else str(value).strip()


def _address(row: dict[str, Any], prefix: str) -> dict[str, str] | None:
    """The party's postal address columns, or ``None`` when it has none."""
    keys = (
        "street_name",
        "building_number",
        "postal_code",
        "town_name",
        "country_subdivision",
        "country_code",
        "address_line",
    )
    address = {k: _text(row, f"{prefix}_{k}") for k in keys}
    return address if any(address.values()) else None


def _party(row: dict[str, Any], prefix: str) -> dict[str, str]:
    """The party's organisation identification columns."""
    return {
        "lei": _text(row, f"{prefix}_lei"),
        "id": _text(row, f"{prefix}_id"),
        "id_scheme": _text(row, f"{prefix}_id_scheme"),
        "id_scheme_proprietary": _text(row, f"{prefix}_id_scheme_proprietary"),
    }


def _agent(row: dict[str, Any], prefix: str) -> dict[str, Any]:
    """The agent's BIC, clearing member id and name columns."""
    address = {
        "town_name": _text(row, f"{prefix}_town_name"),
        "country_subdivision": _text(row, f"{prefix}_country_subdivision"),
        "country_code": _text(row, f"{prefix}_country_code"),
    }
    return {
        "bic": _text(row, f"{prefix}_BIC"),
        "clearing_system": _text(row, f"{prefix}_clearing_system"),
        "member_id": _text(row, f"{prefix}_member_id"),
        "name": _text(row, f"{prefix}_name"),
        "address": address if any(address.values()) else None,
    }


def _account(row: dict[str, Any], prefix: str) -> dict[str, str]:
    """The account's IBAN or number and scheme, and its currency."""
    return {
        "iban": _text(row, f"{prefix}_IBAN"),
        "number": _text(row, f"{prefix}_number"),
        "scheme": _text(row, f"{prefix}_scheme"),
        "scheme_proprietary": _text(row, f"{prefix}_scheme_proprietary"),
        "currency": _text(row, f"{prefix}_currency"),
    }


def _boolean(row: dict[str, Any], key: str) -> str | None:
    """``true``/``false`` for a boolean column, ``None`` when absent."""
    value = row.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return (
        "true"
        if str(value).strip().lower() in ("true", "1", "yes")
        else "false"
    )


#: ISO ExternalCreditorReferenceType1Code: rendered as Cd, anything else as Prtry.
_CREDITOR_REFERENCE_CODES = frozenset(
    {"DISP", "FXDR", "PUOR", "RADM", "RPIN", "SCOR"}
)


def _context_v09(data: list[dict[str, Any]]) -> dict[str, Any]:
    """The template context shared by the .03 and .09 to .13 preparers."""
    return _prepare_xml_data_v09_to_v12(data, gate=False)


def _prepare_xml_data_v09_to_v12(
    data: list[dict[str, Any]], gate: bool = True
) -> dict[str, Any]:
    """Prepare XML data for pain.001.001.09-13 message types.

    The mandatory columns are the ones the first version of this pipeline
    required; an account may be an IBAN or a number with a scheme, and an
    agent a BIC or a clearing member id. Every other column is optional
    and rendered only when given: payment type, addresses, party ids,
    account currency, ultimate parties, purpose, regulatory reporting,
    a structured creditor reference, UETR and instruction id. The
    transaction currency accepts both canonical spellings
    (``payment_currency`` and the JSON Schemas' ``currency``).
    """
    if gate:
        _require_fields(
            data,
            "pain.001.001.09",
            header_fields=[
                "id",
                "date",
                "initiator_name",
                "payment_id",
                "debtor_name",
            ],
            row_fields=["payment_id", "payment_amount", "creditor_name"],
            currency_required=True,
            header_one_of=[
                ("requested_execution_date", "requested_execution_datetime"),
                ("debtor_account_IBAN", "debtor_account_number"),
                ("debtor_agent_BIC", "debtor_agent_member_id"),
            ],
            row_one_of=[
                ("creditor_account_IBAN", "creditor_account_number"),
                ("creditor_agent_BIC", "creditor_agent_member_id"),
            ],
        )
    head = data[0]
    payment_type = {
        "instruction_priority": _text(head, "instruction_priority"),
        "service_level_code": _text(head, "service_level_code"),
        "local_instrument_code": _text(head, "local_instrument_code"),
        "local_instrument_proprietary": _text(
            head, "local_instrument_proprietary"
        ),
        "category_purpose_code": _text(head, "category_purpose_code"),
    }
    transactions = []
    for row in data:
        reference_type = _text(row, "creditor_reference_type")
        regulatory = {
            "indicator": _text(row, "regulatory_reporting_indicator"),
            "country": _text(row, "regulatory_reporting_country"),
            "code": _text(row, "regulatory_reporting_code"),
            "info": _text(row, "regulatory_reporting_info"),
        }
        transactions.append(
            {
                "instruction_id": _text(row, "instruction_id"),
                "payment_id": row["payment_id"],
                "uetr": _text(row, "uetr"),
                "payment_amount": row["payment_amount"],
                "payment_currency": _currency(row),
                "charge_bearer": row.get("charge_bearer", "SLEV"),
                "creditor_agent": _agent(row, "creditor_agent"),
                "creditor_agent_BIC": _text(row, "creditor_agent_BIC"),
                "creditor_name": row["creditor_name"],
                "creditor_address": _address(row, "creditor"),
                "creditor_account": _account(row, "creditor_account"),
                "creditor_account_IBAN": _text(row, "creditor_account_IBAN"),
                "ultimate_creditor_name": _text(row, "ultimate_creditor_name"),
                "purpose_code": _text(row, "purpose_code"),
                "regulatory": regulatory if any(regulatory.values()) else None,
                "remittance_information": row.get(
                    "remittance_information", ""
                ),
                "creditor_reference": _text(row, "creditor_reference"),
                "creditor_reference_type": reference_type,
                "creditor_reference_is_code": reference_type
                in _CREDITOR_REFERENCE_CODES,
                "creditor_reference_issuer": _text(
                    row, "creditor_reference_issuer"
                ),
                "additional_remittance_information": _text(
                    row, "additional_remittance_information"
                ),
                "supplementary_data": row.get("supplementary_data", ""),
            }
        )
    return {
        "id": head["id"],
        "date": head["date"],
        "nb_of_txs": head.get("nb_of_txs", len(data)),
        "ctrl_sum": head.get("ctrl_sum", ""),
        "initiator_name": head["initiator_name"],
        "initiator_address": _address(head, "initiator"),
        "initiator": _party(head, "initiator"),
        "payment_id": head["payment_id"],
        "payment_information_id": _text(head, "payment_information_id")
        or head["payment_id"],
        "payment_method": head.get("payment_method", "TRF"),
        "batch_booking": _boolean(head, "batch_booking"),
        "payment_nb_of_txs": head.get("nb_of_txs", len(data)),
        "payment_type": payment_type if any(payment_type.values()) else None,
        "requested_execution_date": _text(head, "requested_execution_date"),
        "requested_execution_datetime": _text(
            head, "requested_execution_datetime"
        ),
        "debtor_name": head["debtor_name"],
        "debtor_address": _address(head, "debtor"),
        "debtor": _party(head, "debtor"),
        "debtor_account": _account(head, "debtor_account"),
        "debtor_account_IBAN": _text(head, "debtor_account_IBAN"),
        "debtor_agent": _agent(head, "debtor_agent"),
        "debtor_agent_BIC": _text(head, "debtor_agent_BIC"),
        "ultimate_debtor_name": _text(head, "ultimate_debtor_name"),
        "charge_bearer": head.get("charge_bearer", "SLEV"),
        "transactions": transactions,
    }


def _prepare_xml_data_v08_direct_debit(
    data: list[dict[str, Any]],
) -> dict[str, Any]:
    """Prepare XML data for pain.008.001.02 and .08 direct debit messages."""
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
        # SeqTp lives in PmtTpInf. ISO allows PmtTpInf at either the
        # payment-information or the transaction level, but not a bare
        # <SeqTp> inside DrctDbtTxInf, which is what this template
        # emitted until the real pain.008.001.02 schema rejected it.
        "sequence_type": data[0].get("sequence_type", "RCUR"),
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
    # V13 (ISO, 19 Mar 2026) is additive over V12 for everything the
    # CSV pipeline fills: per docs/message-deltas.md it turns the
    # regulatory-reporting detail type into a Cd/Prtry choice, adds a
    # reporting code and structured securities data in remittance, and
    # removes nothing, so the V09-V12 preparation strategy applies.
    "pain.001.001.13": MessageDefinition(
        "pain.001.001.13", "modern_v09_to_v12", _prepare_xml_data_v09_to_v12
    ),
    "pain.008.001.02": MessageDefinition(
        "pain.008.001.02",
        "direct_debit_v02",
        _prepare_xml_data_v08_direct_debit,
    ),
    # V08 (ISO 2019, the version the EPC SEPA Direct Debit 2025
    # rulebooks and CBPR+ carry) keeps the V02 shape for everything the
    # CSV pipeline fills; the visible change is BICFI for BIC, which
    # lives in the template, so the V02 preparer applies unchanged.
    "pain.008.001.08": MessageDefinition(
        "pain.008.001.08",
        "direct_debit_v08",
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
