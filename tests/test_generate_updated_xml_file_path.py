from pain001.xml.generate_updated_xml_file_path import (
    generate_updated_xml_file_path,
)

# Test if the updated XML file path is generated correctly


def test_generate_updated_xml_file_path():
    # Test with a file path that has an extension
    xml_file_path = "tests/data/template.xml"
    payment_initiation_message_type = "pain.001.001.03"
    expected_output = "tests/data/pain.001.001.03.xml"
    assert (
        generate_updated_xml_file_path(
            xml_file_path, payment_initiation_message_type
        )
        == expected_output
    )
