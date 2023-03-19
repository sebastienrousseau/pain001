import csv
from pain001.csv.load_csv_data import load_csv_data

# Test if the CSV data is loaded correctly


def test_load_csv_data():
    # Test with an existing CSV file
    csv_file_path = "tests/data/existing_file.csv"
    expected_output = [
        {"col1": "val1", "col2": "val2", "col3": "val3"},
        {"col1": "val4", "col2": "val5", "col3": "val6"},
        {"col1": "val7", "col2": "val8", "col3": "val9"},
    ]
    with open(csv_file_path, "w", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file, fieldnames=["col1", "col2", "col3"]
        )
        writer.writeheader()
        writer.writerows(expected_output)
    assert load_csv_data(csv_file_path) == expected_output

    # Test with a non-existing CSV file
    csv_file_path = "path/to/non_existing_file.csv"
    try:
        load_csv_data(csv_file_path)
    except FileNotFoundError as e:
        assert str(e) == f"CSV file '{csv_file_path}' does not exist."
    else:
        assert False, "Expected FileNotFoundError not raised."
