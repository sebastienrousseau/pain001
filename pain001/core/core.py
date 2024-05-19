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

# Import the standard libraries
import sys
import os

# Import the pain001 library functions
from pain001.constants.constants import valid_xml_types
from pain001.context.context import Context
from pain001.csv.load_csv_data import load_csv_data
from pain001.csv.validate_csv_data import validate_csv_data
from pain001.db.load_db_data import load_db_data
from pain001.db.validate_db_data import validate_db_data
from pain001.xml.register_namespaces import register_namespaces
from pain001.xml.generate_xml import generate_xml


def process_files(
    xml_message_type,
    xml_template_file_path,
    xsd_schema_file_path,
    data_file_path,
):
    """
    This function generates an ISO 20022 payment message from a CSV or SQLite
    file containing the payment data.

    Args:
        xml_message_type (str): The type of XML message to generate. Valid
        options are 'pain.001.001.03', 'pain.001.001.04', 'pain.001.001.05',
        'pain.001.001.06' and 'pain.001.001.09'.
        xml_template_file_path (str): The path of the XML template file.
        xsd_schema_file_path (str): The path of the XSD schema file.
        data_file_path (str): The path of the CSV or SQLite file containing the
        payment data.

    Returns:
        None

    Raises:
        ValueError: If the XML message type is not supported.
        FileNotFoundError: If the XML template file does not exist.
        FileNotFoundError: If the XSD schema file does not exist.
        FileNotFoundError: If the Data file does not exist.
    """

    # Initialize the context and log a message.
    logger = Context.get_instance().get_logger()

    # Loop through the payment initiation message types and check if the XML
    # message type is supported.
    if xml_message_type not in valid_xml_types:
        error_message = (
            f"Error: Invalid XML message type: '{xml_message_type}'."
        )
        logger.error(error_message)
        raise ValueError(error_message)

    # Check if the XML template file exists
    if not os.path.exists(xml_template_file_path):
        error_message = (
            f"Error: XML template '{xml_template_file_path}' "
            f"does not exist."
        )
        logger.error(error_message)
        raise FileNotFoundError(error_message)

    # Check if the XSD schema file exists
    if not os.path.exists(xsd_schema_file_path):
        error_message = (
            f"Error: XSD schema file '{xsd_schema_file_path}' "
            f"does not exist."
        )
        logger.error(error_message)
        raise FileNotFoundError(error_message)

    # Sanitize the path to the data file.
    data_file_path = os.path.normpath(data_file_path)

    # Check if the data file exists
    if not os.path.exists(data_file_path):
        error_message = f"Error: Data file '{data_file_path}' does not exist."
        logger.error(error_message)
        raise FileNotFoundError(error_message)

    # Define mapping dictionary between XML element tags and CSV column names
    # mapping = {
    #     "MsgId": "id",
    #     "CreDtTm": "date",
    #     "NbOfTxs": "nb_of_txs",
    #     "Nm": "initiator_name",
    #     "PmtInfId": "payment_information_id",
    #     "PmtMtd": "payment_method",
    # }

    # Determine the type of data file (CSV or SQLite)
    is_csv = data_file_path.endswith(".csv")
    is_sqlite = data_file_path.endswith(".db")

    # Load data into a list of dictionaries based on the file type
    if is_csv:
        data = load_csv_data(data_file_path)
        if not validate_csv_data(data):
            error_message = "Error: Invalid CSV data."
            logger.error(error_message)
            raise ValueError(error_message)
    elif is_sqlite:
        data = load_db_data(data_file_path, table_name="pain001")
        if not validate_db_data(data):
            error_message = "Error: Invalid SQLite data."
            logger.error(error_message)
            raise ValueError(error_message)
    else:
        error_message = "Error: Unsupported data file type."
        logger.error(error_message)
        raise ValueError(error_message)

    # Register the namespace prefixes and URIs for the XML message type
    register_namespaces(xml_message_type)

    # Generate the updated XML file path
    generate_xml(
        data,
        xml_message_type,
        xml_template_file_path,
        xsd_schema_file_path,
    )

    # Confirm the XML file has been created
    if os.path.exists(xml_template_file_path):
        logger.info(
            f"Successfully generated XML file '{xml_template_file_path}'"
        )
    else:
        logger.error(
            f"Failed to generate XML file at '{xml_template_file_path}'"
        )


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
