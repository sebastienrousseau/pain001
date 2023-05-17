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

# Import the pain001 library functions
from .context import context
from .csv.validate_csv_data import validate_csv_data
from .csv.load_csv_data import load_csv_data
from .xml.register_namespaces import register_namespaces
from .xml.xml_generator import xml_generator
from pain001.constants.constants import valid_xml_types


def process_files(
    xml_message_type,
    xml_file_path,
    xsd_file_path,
    csv_file_path
):
    """
    This function, when called, generates an ISO 20022 payment message
    from a CSV file containing the payment data.

    The `process_files` function takes the following arguments:

    - **xml_message_type**: The type of the ISO 20022 payment message to
    generate. (Default value is `pain.001.001.03`)
    - **xml_file_path**: The path of the XML template file.
    - **xsd_file_path**: The path of the XSD schema file.
    - **csv_file_path**: The path of the CSV file containing the payment
    data.

    Args:
        - **xml_message_type (str)**: The type of XML message to
        generate. The following ISO 20022 Payment Initiation message
        types are supported:
            - `pain.001.001.03` - Customer Credit Transfer Initiation,
            - `pain.001.001.09` - Notification of Reversal,
        - **xml_file_path (str)**: The path of the XML template file.
        - **xsd_file_path (str)**: The path of the XSD schema file.
        - **csv_file_path (str)**: The path of the CSV file containing
        the payment data.

    Returns:
        The function returns a new XML file with the payment data in the
        ISO 20022 payment message format that was specified in the
        `xml_message_type` argument.

    Raises:
        ValueError: If the XML message type is not supported.
        FileNotFoundError: If the XML template file does not exist.
        FileNotFoundError: If the XSD schema file does not exist.
        FileNotFoundError: If the CSV file does not exist.
    """

    # Initialize the context and log a message.
    logger = context.Context.get_instance().get_logger()

    # Print out the command-line arguments for debugging purposes
    # print(f"Command-line arguments: {sys.argv}")

    # Looping through the payment initiation message types array and
    # check if the XML message type is supported.  If it is supported,
    # print out the XML message type and break out of the loop.  If it
    # is not supported, print out an error message and exit the program.
    if xml_message_type in valid_xml_types:
        logger.info(f"XML message type: {xml_message_type}")
    else:
        logger.error(
            f"Error: Invalid XML message type: `{xml_message_type}`."
        )
        sys.exit(1)

    # Define mapping dictionary between XML element tags and CSV column
    # names
    mapping = {
        "MsgId": "id",
        "CreDtTm": "date",
        "NbOfTxs": "nb_of_txs",
        "Nm": "initiator_name",
        "PmtInfId": "payment_information_id",
        "PmtMtd": "payment_method",
    }

    # Load CSV data into a list of dictionaries
    data = load_csv_data(csv_file_path)

    # Validate the CSV data
    if not validate_csv_data(data):
        logger.error("❌ Error: Invalid CSV data.")
        sys.exit(1)

    # Print out CSV data for debugging
    # print(f"CSV data: {data}")

    # Register the namespace prefixes and URIs for the XML message type
    register_namespaces(xml_message_type)

    # Generate the updated XML file path
    xml_generator(
        data,
        mapping,
        xml_message_type,
        xml_file_path,
        xsd_file_path
    )


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            "Usage: python3 -m pain001 <xml_message_type> "
            "<xml_file_path> <xsd_file_path> <csv_file_path> "
        )
        sys.exit(1)
    process_files(sys.argv[1], sys.argv[2], sys.argv[3])
