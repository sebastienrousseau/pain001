def generate_examples():
    versions = [
        "pain.001.001.03",
        "pain.001.001.04",
        "pain.001.001.05",
        "pain.001.001.06",
        "pain.001.001.07",
        "pain.001.001.08",
        "pain.001.001.09",
        "pain.001.001.10",
        "pain.001.001.11",
    ]

    # Use the fixed unique data file
    csv_path = "tests/data/valid_data_unique.csv"

    # I'll use the pain001 module directly to be sure
    from pain001.csv.load_csv_data import load_csv_data
    from pain001.xml.generate_xml import generate_xml

    data = load_csv_data(csv_path)

    for version in versions:
        template_dir = f"pain001/templates/{version}"
        xml_template = f"{template_dir}/template.xml"
        xsd_schema = f"{template_dir}/{version}.xsd"
        output_file = f"{template_dir}/{version}.xml"

        print(f"Generating {output_file}...")
        try:
            # generate_xml takes xml_file_path as the input template path,
            # and determines output path automatically (base_dir + message_type.xml)
            generate_xml(data, version, xml_template, xsd_schema)
            print("Success")
        except SystemExit:
            print(f"Failed (SystemExit) for {version}")
        except Exception as e:
            print(f"Failed {version}: {e}")


if __name__ == "__main__":
    generate_examples()
