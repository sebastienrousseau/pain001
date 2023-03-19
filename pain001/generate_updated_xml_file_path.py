import os

# Generate the path to the updated XML file based on the path to the
# original XML file


def generate_updated_xml_file_path(xml_file_path):
    return os.path.splitext(xml_file_path)[0] + "_updated.xml"
