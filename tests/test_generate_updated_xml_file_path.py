from pain001.xml.generate_updated_xml_file_path import (
    generate_updated_xml_file_path,
)

# Test if the updated XML file path is generated correctly


def test_generate_updated_xml_file_path():
    # Test with a file path that has an extension
    xml_file_path = "tests/data/template.xml"
    expected_output = "tests/data/template_updated.xml"
    assert generate_updated_xml_file_path(
        xml_file_path
    ) == expected_output
