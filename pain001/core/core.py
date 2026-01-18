# Copyright (C) 2023 Sebastien Rousseau.
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
#
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import sys
import time
from typing import Any, Union

import pain001.xml.generate_xml as xml_generate
import pain001.xml.register_namespaces as xml_namespaces
from pain001.constants import valid_xml_types
from pain001.context.context import Context
from pain001.data.loader import load_payment_data
from pain001.exceptions import XMLGenerationError
from pain001.logging_schema import (
    Events,
    Fields,
    log_event,
    log_process_error,
    log_process_start,
    log_process_success,
)
from pain001.security.path_validator import sanitize_for_log, validate_path

# CORRECTION: Circular import workaround. Imports moved to top-level.

# Configure structured logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def _validate_inputs(
    xml_message_type: str,
    xml_template_file_path: str,
    xsd_schema_file_path: str,
) -> tuple[str, str]:
    """Validate message type and required file paths.

    Raises:
        ValueError: If the XML message type is not supported.
        FileNotFoundError: If required files do not exist.
    """
    context_logger = Context.get_instance().get_logger()

    if xml_message_type not in valid_xml_types:
        error_message = (
            f"Error: Invalid XML message type: '{xml_message_type}'."
        )
        context_logger.error(
            f"{sanitize_for_log(error_message)}".replace("\n", "")
        )
        log_event(
            logger,
            logging.ERROR,
            Events.VALIDATION_ERROR,
            **{
                Fields.VALIDATION_TYPE: "message_type",
                Fields.MESSAGE_TYPE: xml_message_type,
                Fields.ERROR_MESSAGE: error_message,
            },
        )
        raise XMLGenerationError(error_message)

    try:
        safe_template_path = validate_path(
            xml_template_file_path, must_exist=True
        )
    except Exception as e:
        error_message = f"Error: XML template '{xml_template_file_path}' does not exist or is invalid: {e}."
        context_logger.error(
            f"{sanitize_for_log(error_message)}".replace("\n", "")
        )
        log_event(
            logger,
            logging.ERROR,
            Events.VALIDATION_ERROR,
            **{
                Fields.VALIDATION_TYPE: "template_file",
                Fields.TEMPLATE_PATH: xml_template_file_path,
                Fields.ERROR_MESSAGE: error_message,
            },
        )
        raise FileNotFoundError(error_message) from e

    try:
        safe_schema_path = validate_path(xsd_schema_file_path, must_exist=True)
    except Exception as e:
        error_message = f"Error: XSD schema file '{xsd_schema_file_path}' does not exist or is invalid: {e}."
        context_logger.error(
            f"{sanitize_for_log(error_message)}".replace("\n", "")
        )
        log_event(
            logger,
            logging.ERROR,
            Events.VALIDATION_ERROR,
            **{
                Fields.VALIDATION_TYPE: "schema_file",
                Fields.SCHEMA_PATH: xsd_schema_file_path,
                Fields.ERROR_MESSAGE: error_message,
            },
        )
        raise FileNotFoundError(error_message) from e

    return str(safe_template_path), str(safe_schema_path)


def _determine_data_source_type(
    data_file_path: Union[str, list[dict[str, Any]], dict[str, Any]],
) -> str:
    """Determine the type of the data source."""
    if isinstance(data_file_path, list):
        return "list"
    if isinstance(data_file_path, dict):
        return "dict"
    if not isinstance(data_file_path, str):
        return "unknown"

    if data_file_path.endswith(".db") or "sqlite" in data_file_path:
        return "sqlite"

    for ext in [".csv", ".jsonl", ".json", ".parquet"]:
        if data_file_path.endswith(ext):
            return ext.lstrip(".")

    return "file"


def _load_data(
    data_file_path: Union[str, list[dict[str, Any]], dict[str, Any]],
    start_time: float,
) -> list[dict[str, Any]]:
    """Load and validate payment data from files or Python objects."""
    # Determine data source type
    data_source_kind = _determine_data_source_type(data_file_path)

    log_event(
        logger,
        logging.INFO,
        Events.DATA_LOAD_START,
        **{Fields.DATA_SOURCE_TYPE: data_source_kind},
    )

    try:
        payment_data = load_payment_data(data_file_path)
        duration_ms = int((time.time() - start_time) * 1000)
        log_event(
            logger,
            logging.INFO,
            Events.DATA_LOAD_SUCCESS,
            **{
                Fields.DATA_SOURCE_TYPE: data_source_kind,
                Fields.RECORD_COUNT: len(payment_data),
                Fields.DURATION_MS: duration_ms,
            },
        )
        return payment_data
    except (FileNotFoundError, ValueError) as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_event(
            logger,
            logging.ERROR,
            Events.DATA_LOAD_ERROR,
            **{
                Fields.DATA_SOURCE_TYPE: data_source_kind,
                Fields.ERROR_TYPE: type(e).__name__,
                Fields.ERROR_MESSAGE: str(e),
                Fields.DURATION_MS: duration_ms,
            },
        )
        raise


def _register_message_namespaces(xml_message_type: str) -> None:
    """Register XML namespace prefixes and URIs for the given message type."""
    log_event(
        logger,
        logging.INFO,
        Events.NAMESPACE_REGISTER,
        **{Fields.MESSAGE_TYPE: xml_message_type},
    )
    xml_namespaces.register_namespaces(xml_message_type)


def _generate_and_log(
    payment_data: list[dict[str, Any]],
    xml_message_type: str,
    xml_template_file_path: str,
    xsd_schema_file_path: str,
) -> int:
    """Generate the XML and return generation duration in milliseconds."""
    gen_start = time.time()
    log_event(
        logger,
        logging.INFO,
        Events.XML_GENERATE_START,
        **{
            Fields.MESSAGE_TYPE: xml_message_type,
            Fields.RECORD_COUNT: len(payment_data),
        },
    )

    xml_generate.generate_xml(
        payment_data,
        xml_message_type,
        xml_template_file_path,
        xsd_schema_file_path,
    )

    return int((time.time() - gen_start) * 1000)


def process_files(
    xml_message_type: str,
    xml_template_file_path: str,
    xsd_schema_file_path: str,
    data_file_path: Union[str, list[dict[str, Any]], dict[str, Any]],
) -> None:
    """
    Generate an ISO 20022 payment message from various data sources.

    Args:
        xml_message_type: XML message type (e.g., 'pain.001.001.03').
        xml_template_file_path: Path to the XML template file.
        xsd_schema_file_path: Path to the XSD schema file.
        data_file_path: File path (CSV/DB/JSON/Parquet) or Python data (list/dict).

    Raises:
        ValueError: If the XML message type is not supported or data is invalid.
        FileNotFoundError: If required files do not exist.
    """

    # Initialize context and timing
    context_logger = Context.get_instance().get_logger()

    # Determine data source type
    data_source_kind = _determine_data_source_type(data_file_path)

    # Log process start
    start_time = log_process_start(logger, xml_message_type, data_source_kind)

    try:
        safe_template_path, safe_schema_path = _validate_inputs(
            xml_message_type, xml_template_file_path, xsd_schema_file_path
        )
        payment_data = _load_data(data_file_path, start_time)
        _register_message_namespaces(xml_message_type)
        gen_duration = _generate_and_log(
            payment_data,
            xml_message_type,
            safe_template_path,
            safe_schema_path,
        )

        # Confirm success (template existence check retained for backward compatibility)
        if os.path.exists(safe_template_path):
            context_logger.info(
                f"Successfully generated XML file '{safe_template_path}'".replace(
                    "\n", ""
                )
            )
            log_process_success(
                logger,
                start_time,
                xml_message_type,
                len(payment_data),
                generation_ms=gen_duration,
            )
        else:
            error_msg = (
                f"Failed to generate XML file at '{safe_template_path}'"
            )
            context_logger.error(
                f"{sanitize_for_log(error_msg)}".replace("\n", "")
            )
            log_event(
                logger,
                logging.ERROR,
                Events.XML_GENERATE_ERROR,
                **{
                    Fields.MESSAGE_TYPE: xml_message_type,
                    Fields.TEMPLATE_PATH: safe_template_path,
                    Fields.ERROR_MESSAGE: error_msg,
                },
            )

    except Exception as e:
        log_process_error(logger, e, xml_message_type)
        raise


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(
            "Usage: python3 -m pain001 "
            + " ".join(
                [
                    "<xml_message_type>",
                    "<xml_template_file_path>",
                    "<xsd_schema_file_path>",
                    "<data_file_path>",
                ]
            )
        )

        sys.exit(1)
    process_files(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
