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

# XML generator function that creates the XML file from the CSV data
# and the mapping dictionary between XML tags and CSV columns names and
# writes it to a file in the same directory as the CSV file

# pylint: disable=duplicate-code

# Import the CSV library
import logging
import os
import warnings
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader

from pain001.exceptions import PaymentValidationError
from pain001.security import validate_path
from pain001.xml.generate_updated_xml_file_path import (
    generate_updated_xml_file_path,
)
from pain001.xml.validate_via_xsd import validate_xml_string_via_xsd

logger = logging.getLogger(__name__)

_AMOUNT_EXPONENT = Decimal("0.01")


def _format_amount(value: Any, row_index: int) -> str:
    """Normalize a monetary amount to an exact two-decimal string.

    Amounts are handled with Decimal end-to-end: floats are converted via
    their shortest string representation so binary artifacts are surfaced
    (and rejected) rather than silently rounded into the payment file.

    Raises:
        PaymentValidationError: If the amount is missing, not a number,
            not positive, or carries more than two decimal places.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise PaymentValidationError(
            f"Row {row_index}: payment_amount is required",
            field="payment_amount",
        )
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation as e:
        raise PaymentValidationError(
            f"Row {row_index}: payment_amount {value!r} is not a number",
            field="payment_amount",
        ) from e
    if not amount.is_finite() or amount <= 0:
        raise PaymentValidationError(
            f"Row {row_index}: payment_amount must be a positive amount, "
            f"got {value!r}",
            field="payment_amount",
        )
    quantized = amount.quantize(_AMOUNT_EXPONENT)
    if amount != quantized:
        raise PaymentValidationError(
            f"Row {row_index}: payment_amount {value!r} has more than two "
            "decimal places; round it explicitly before generating",
            field="payment_amount",
        )
    return f"{quantized:.2f}"


def _normalize_financial_fields(
    data: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str, str]:
    """Normalize amounts and compute batch totals from the actual rows.

    Returns:
        Tuple of (rows with normalized payment_amount, nb_of_txs, ctrl_sum)
        where nb_of_txs and ctrl_sum are computed from the data instead of
        trusting caller-provided header fields.
    """
    normalized: list[dict[str, Any]] = []
    total = Decimal("0.00")
    for index, row in enumerate(data, start=1):
        formatted = _format_amount(row.get("payment_amount"), index)
        total += Decimal(formatted)
        updated = dict(row)
        updated["payment_amount"] = formatted
        normalized.append(updated)
    return normalized, str(len(normalized)), f"{total:.2f}"


def _prepare_xml_data_v03(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Prepare XML data for pain.001.001.03 message type."""
    return {
        "id": data[0]["id"],
        "date": data[0]["date"],
        "nb_of_txs": data[0]["nb_of_txs"],
        "initiator_name": data[0]["initiator_name"],
        "initiator_street_name": data[0]["initiator_street_name"],
        "initiator_building_number": data[0]["initiator_building_number"],
        "initiator_postal_code": data[0]["initiator_postal_code"],
        "initiator_town_name": data[0]["initiator_town_name"],
        "initiator_country_code": data[0]["initiator_country_code"],
        "payment_id": data[0]["payment_id"],
        "payment_method": data[0]["payment_method"],
        "batch_booking": data[0]["batch_booking"],
        "requested_execution_date": data[0]["requested_execution_date"],
        "debtor_name": data[0]["debtor_name"],
        "debtor_street_name": data[0]["debtor_street_name"],
        "debtor_building_number": data[0]["debtor_building_number"],
        "debtor_postal_code": data[0]["debtor_postal_code"],
        "debtor_town_name": data[0]["debtor_town_name"],
        "debtor_country_code": data[0]["debtor_country_code"],
        "debtor_account_IBAN": data[0]["debtor_account_IBAN"],
        "debtor_agent_BIC": data[0]["debtor_agent_BIC"],
        "charge_bearer": data[0]["charge_bearer"],
        "transactions": [
            {
                "payment_id": row["payment_id"],
                "payment_amount": row.get("payment_amount", ""),
                "payment_currency": row.get("payment_currency", ""),
                "charge_bearer": row["charge_bearer"],
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
            for row in data[0:]
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
            for row in data[0:]
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
                "payment_currency": row.get("payment_currency", ""),
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


def _prepare_xml_data_v09_to_v11(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Prepare XML data for pain.001.001.09-11 message types."""
    return {
        "id": data[0]["id"],
        "date": data[0]["date"],
        "nb_of_txs": data[0]["nb_of_txs"],
        "initiator_name": data[0]["initiator_name"],
        "payment_id": data[0]["payment_id"],
        "payment_method": data[0]["payment_method"],
        "payment_nb_of_txs": data[0]["nb_of_txs"],
        "requested_execution_date": data[0]["requested_execution_date"],
        "debtor_name": data[0]["debtor_name"],
        "debtor_account_IBAN": data[0]["debtor_account_IBAN"],
        "debtor_agent_BIC": data[0]["debtor_agent_BIC"],
        "charge_bearer": data[0]["charge_bearer"],
        "transactions": [
            {
                "payment_id": row["payment_id"],
                "payment_amount": row["payment_amount"],
                "payment_currency": row.get("payment_currency", ""),
                "charge_bearer": row["charge_bearer"],
                "creditor_agent_BIC": row["creditor_agent_BIC"],
                "creditor_name": row["creditor_name"],
                "creditor_account_IBAN": row["creditor_account_IBAN"],
                "creditor_remittance_information": row[
                    "remittance_information"
                ],
            }
            for row in data[0:]
        ],
    }


def generate_xml_string(
    data: list[dict[str, Any]],
    payment_initiation_message_type: str,
    xml_template_path: str,
    xsd_schema_path: str,
) -> str:
    """Generate ISO 20022 pain.001 XML content as a string (in-memory).

    This function is ideal for serverless architectures, REST APIs, and
    microservices where XML needs to be returned without writing to disk.

    Args:
        data: List of dictionaries containing payment data.
        payment_initiation_message_type: Message type (e.g., "pain.001.001.03").
        xml_template_path: Path to the Jinja2 XML template file.
        xsd_schema_path: Path to XSD schema file for validation.

    Returns:
        str: The generated and validated XML content.

    Raises:
        ValueError: If message type is invalid or data is empty.
        RuntimeError: If XML validation fails against XSD schema.

    Examples:
        >>> data = [{"id": "MSG001", "date": "2026-01-15", ...}]
        >>> xml_str = generate_xml_string(
        ...     data,
        ...     "pain.001.001.03",
        ...     "templates/pain.001.001.03/template.xml",
        ...     "templates/pain.001.001.03/pain.001.001.03.xsd"
        ... )  # doctest: +SKIP
        >>> xml_str.startswith('<?xml')
        True
    """
    # Define mapping between XML types and data preparation functions
    xml_data_preparers = {
        "pain.001.001.03": _prepare_xml_data_v03,
        "pain.001.001.04": _prepare_xml_data_v04,
        "pain.001.001.05": _prepare_xml_data_v05_to_v08,
        "pain.001.001.06": _prepare_xml_data_v05_to_v08,
        "pain.001.001.07": _prepare_xml_data_v05_to_v08,
        "pain.001.001.08": _prepare_xml_data_v05_to_v08,
        "pain.001.001.09": _prepare_xml_data_v09_to_v11,
        "pain.001.001.10": _prepare_xml_data_v09_to_v11,
        "pain.001.001.11": _prepare_xml_data_v09_to_v11,
    }

    # Validate template path
    try:
        xml_template_path = validate_path(xml_template_path)
    except Exception as e:
        raise ValueError(f"Invalid template path: {e}") from e

    # Validate schema path
    try:
        xsd_schema_path = validate_path(xsd_schema_path)
    except Exception as e:
        raise ValueError(f"Invalid schema path: {e}") from e

    # Validate message type
    if payment_initiation_message_type not in xml_data_preparers:
        raise ValueError(
            f"Invalid XML message type: {payment_initiation_message_type}"
        )

    # Check if data is not empty
    if not data:
        raise ValueError("No data to process - data list is empty")

    # Normalize amounts (Decimal, 2dp) and compute batch totals from the
    # rows themselves — header fields like NbOfTxs/CtrlSum must never be
    # trusted from input or the message becomes internally inconsistent.
    data, nb_of_txs, ctrl_sum = _normalize_financial_fields(data)

    # Prepare XML data using appropriate function
    preparer = xml_data_preparers[payment_initiation_message_type]
    xml_data = preparer(data)
    xml_data["nb_of_txs"] = nb_of_txs
    if "payment_nb_of_txs" in xml_data:
        xml_data["payment_nb_of_txs"] = nb_of_txs
    if "ctrl_sum" in xml_data:
        xml_data["ctrl_sum"] = ctrl_sum

    # Create a Jinja2 environment and load template
    template_dir = os.path.dirname(xml_template_path)
    template_file = os.path.basename(xml_template_path)
    # Use current directory if path has no directory component
    loader_path = template_dir if template_dir else "."

    env = Environment(loader=FileSystemLoader(loader_path), autoescape=True)
    template = env.get_template(template_file)

    # Render the template to string
    xml_content = template.render(**xml_data)

    # Validate the XML content against the XSD schema
    is_valid = validate_xml_string_via_xsd(xml_content, xsd_schema_path)

    if not is_valid:
        raise RuntimeError(
            f"Generated XML failed validation against {xsd_schema_path}"
        )

    return xml_content


def generate_xml(
    data: list[dict[str, Any]],
    payment_initiation_message_type: str,
    xml_file_path: str,
    xsd_file_path: str,
    output_path: Optional[str] = None,
) -> str:
    """Generates an ISO 20022 pain.001 XML file from input data.

    This function writes XML to a file. For in-memory XML generation
    (serverless/API use cases), use generate_xml_string() instead.

    Args:
        data: List of dictionaries containing payment data
        payment_initiation_message_type: String indicating message type
        such as "pain.001.001.03, pain.001.001.04, pain.001.001.05,
        pain.001.001.06, pain.001.001.07, pain.001.001.08, etc."
        xml_file_path: Path to the Jinja2 XML template file
        xsd_file_path: Path to XML schema file for validation
        output_path: Explicit path to write the generated XML file to.
            Parent directories are created if needed. When omitted, the
            file is written next to the template (deprecated behavior
            that only works when the template lives under the current
            working directory).

    Returns:
        The path the XML file was written to.

    Raises:
        ValueError: If message type is invalid or data is empty.
        RuntimeError: If XML validation fails.
    """
    # Generate XML content as string
    xml_content = generate_xml_string(
        data, payment_initiation_message_type, xml_file_path, xsd_file_path
    )

    if output_path is not None:
        safe_xml_path = os.path.realpath(str(output_path))
        os.makedirs(os.path.dirname(safe_xml_path) or ".", exist_ok=True)
    else:
        warnings.warn(
            "Calling generate_xml without output_path writes next to the "
            "template and requires it to be under the current working "
            "directory; pass output_path explicitly instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Legacy behavior: derive the output path from the template path.
        updated_xml_file_path = generate_updated_xml_file_path(
            xml_file_path, payment_initiation_message_type
        )

        try:
            safe_xml_path = validate_path(updated_xml_file_path)  # nosec B108
        except Exception as e:
            raise ValueError(f"Path validation failed: {e}") from e

        # Explicit startswith guard for CodeQL CWE-22 sanitiser recognition.
        cwd_prefix = str(os.path.realpath(os.getcwd()))
        if not safe_xml_path.startswith(cwd_prefix + os.sep):
            raise ValueError(
                f"Output path outside working directory: {safe_xml_path}"
            )

    with open(safe_xml_path, "w", encoding="utf-8") as xml_file:  # nosec B108
        xml_file.write(xml_content)

    logger.info("XML file created at %s", safe_xml_path)
    return safe_xml_path
