import unittest
import os
from pain001.core import process_files

from pain001.csv.load_csv_data import load_csv_data
from pain001.xml.register_namespaces import register_namespaces
from pain001.xml.validate_via_xsd import validate_via_xsd
from pain001.xml.xml_generator import xml_generator


class TestProcessFiles(unittest.TestCase):
    def test_process_files_valid_data(self):
        # Create a CSV file with valid data
        csv_file_path = os.path.join(os.path.dirname(
            __file__), "data/template.csv")

        # Read the XML template file
        xml_template_file = os.path.join(
            os.path.dirname(__file__), "data/template.xml")

        # Create an XSD file
        xsd_file = os.path.join(os.path.dirname(
            __file__), "data/template.xsd")
        with open(xsd_file) as f:
            xsd_file = f.read()

        # Define mapping dictionary between XML element tags and
        # CSV column names
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

        # Register the namespace prefixes
        register_namespaces()

        # Generate the updated XML file path
        xml_generator(data, mapping, xml_template_file, xsd_file)

        # Check that the output XML file was created
        output_xml_file = os.path.join(
            os.path.dirname(__file__), "data/template_updated.xml")
        self.assertTrue(os.path.exists(output_xml_file))

        # Validate the updated XML file against the XSD schema
        is_valid = validate_via_xsd(output_xml_file, xsd_file)
        self.assertTrue(is_valid)

        # Test process_files function
        process_files(xml_template_file, xsd_file, csv_file_path)
        assert os.path.exists(os.path.join(
            os.path.dirname(__file__), "data/template_updated.xml"))

    def test_process_files_invalid_data(self):
        try:
            process_files("invalid.xml", "invalid.xsd", "invalid.csv")
        except FileNotFoundError:
            pass
        else:
            assert False, "process_files() FileNotFoundError"

        assert os.path.exists(os.path.join(
            os.path.dirname(__file__), "data/invalid.xml")) is False
        assert os.path.exists(os.path.join(
            os.path.dirname(__file__), "data/invalid.xsd")) is False
        assert os.path.exists(os.path.join(
            os.path.dirname(__file__), "data/invalid.csv")) is False
