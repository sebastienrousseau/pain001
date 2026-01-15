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

from pain001.constants.constants import valid_xml_types
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
from pain001.xml.generate_xml import generate_xml
from pain001.xml.register_namespaces import register_namespaces

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
) -> None:
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
        context_logger.error(error_message)
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

    if not os.path.exists(xml_template_file_path):
        error_message = (
            f"Error: XML template '{xml_template_file_path}' does not exist."
        )
        context_logger.error(error_message)
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
        raise FileNotFoundError(error_message)

    if not os.path.exists(xsd_schema_file_path):
        error_message = (
            f"Error: XSD schema file '{xsd_schema_file_path}' does not exist."
        )
        context_logger.error(error_message)
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
        raise FileNotFoundError(error_message)


def _load_data(
    data_file_path: Union[str, list[dict[str, Any]], dict[str, Any]],
    start_time: float,
) -> list[dict[str, Any]]:
    """Load and validate payment data from files or Python objects."""
    # Determine data source type
    if isinstance(data_file_path, str):
        if data_file_path.endswith(".csv"):
            data_source_type = "csv"
        elif data_file_path.endswith(".db") or "sqlite" in data_file_path:
            data_source_type = "sqlite"
        elif data_file_path.endswith(".json"):
            data_source_type = "json"
        elif data_file_path.endswith(".jsonl"):
            data_source_type = "jsonl"
        elif data_file_path.endswith(".parquet"):
            data_source_type = "parquet"
        else:
            data_source_type = "file"
    elif isinstance(data_file_path, list):
        data_source_type = "list"
    elif isinstance(data_file_path, dict):
        data_source_type = "dict"
    else:
        data_source_type = "unknown"

    log_event(
        logger,
        logging.INFO,
        Events.DATA_LOAD_START,
        **{Fields.DATA_SOURCE_TYPE: data_source_type},
    )

    try:
        data = load_payment_data(data_file_path)
        duration_ms = int((time.time() - start_time) * 1000)
        log_event(
            logger,
            logging.INFO,
            Events.DATA_LOAD_SUCCESS,
            **{
                Fields.DATA_SOURCE_TYPE: data_source_type,
                Fields.RECORD_COUNT: len(data),
                Fields.DURATION_MS: duration_ms,
            },
        )
        return data
    except (FileNotFoundError, ValueError) as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_event(
            logger,
            logging.ERROR,
            Events.DATA_LOAD_ERROR,
            **{
                Fields.DATA_SOURCE_TYPE: data_source_type,
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
    register_namespaces(xml_message_type)


def _generate_and_log(
    data: list[dict[str, Any]],
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
            Fields.RECORD_COUNT: len(data),
        },
    )

    generate_xml(
        data,
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
    if isinstance(data_file_path, str):
        if data_file_path.endswith(".csv"):
            data_source_type = "csv"
        elif data_file_path.endswith(".db") or "sqlite" in data_file_path:
            data_source_type = "sqlite"
        elif data_file_path.endswith(".json"):
            data_source_type = "json"
        elif data_file_path.endswith(".jsonl"):
            data_source_type = "jsonl"
        elif data_file_path.endswith(".parquet"):
            data_source_type = "parquet"
        else:
            data_source_type = "file"
    elif isinstance(data_file_path, list):
        data_source_type = "list"
    elif isinstance(data_file_path, dict):
        data_source_type = "dict"
    else:
        data_source_type = "unknown"

    # Log process start
    start_time = log_process_start(logger, xml_message_type, data_source_type)

    try:
        _validate_inputs(
            xml_message_type, xml_template_file_path, xsd_schema_file_path
        )
        data = _load_data(data_file_path, start_time)
        _register_message_namespaces(xml_message_type)
        gen_duration = _generate_and_log(
            data,
            xml_message_type,
            xml_template_file_path,
            xsd_schema_file_path,
        )

        # Confirm success (template existence check retained for backward compatibility)
        if os.path.exists(xml_template_file_path):
            context_logger.info(
                f"Successfully generated XML file '{xml_template_file_path}'"
            )
            log_process_success(
                logger,
                start_time,
                xml_message_type,
                len(data),
                generation_ms=gen_duration,
            )
        else:
            error_msg = (
                f"Failed to generate XML file at '{xml_template_file_path}'"
            )
            context_logger.error(error_msg)
            log_event(
                logger,
                logging.ERROR,
                Events.XML_GENERATE_ERROR,
                **{
                    Fields.MESSAGE_TYPE: xml_message_type,
                    Fields.TEMPLATE_PATH: xml_template_file_path,
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
