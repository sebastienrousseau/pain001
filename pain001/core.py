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
from .csv.validate_csv_data import validate_csv_data
from .csv.load_csv_data import load_csv_data
from .xml.register_namespaces import register_namespaces
from .xml.xml_generator import xml_generator


def process_files(xml_file_path, xsd_file_path, csv_file_path):
    """This function, when called, generates a Customer-to-Bank Credit
    Transfer payload in a pain.001.001.03 format from a CSV file.

    Executes a command-line interface for the Pain001 library. The first
    argument is the path of the XML template file. The second argument
    is the path of the CSV file containing the payment data.

    Args:
        xml_file_path (str): The path of the XML template file.
        csv_file_path (str): The path of the CSV file containing the
        payment data.

    Returns:
        The generated XML file in the pain.001.001.03 format with the
        payment data.

    Raises:
        FileNotFoundError: If the XML template file does not exist.
        FileNotFoundError: If the CSV file does not exist.
    """

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
        print("Error: Invalid CSV data.")
        sys.exit(1)

    # Print out CSV data for debugging
    # print(f"CSV data: {data}")

    # Register the namespace prefixes
    register_namespaces()

    # Generate the updated XML file path
    xml_generator(data, mapping, xml_file_path, xsd_file_path)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            "Usage: python3 -m pain001 <xml_file_path> "
            "<xsd_file_path> <csv_file_path>"
        )
        sys.exit(1)
    process_files(sys.argv[1], sys.argv[2], sys.argv[3])
