import csv
import os

# Load the CSV file into a list of dictionaries with the column names as
# keys


def load_csv_data(csv_file_path):
    if not os.path.exists(csv_file_path):
        raise FileNotFoundError(
            f"CSV file '{csv_file_path}' does not exist."
        )

    data = []
    with open(csv_file_path, "r") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            data.append(row)
    return data
