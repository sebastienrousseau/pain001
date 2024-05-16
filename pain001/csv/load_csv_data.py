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
# See the License for the specific language governing permissions and
# limitations under the License.

import csv

# Load the CSV file into a list of dictionaries with the column names as
# keys


def load_csv_data(file_path):
    """Load CSV data from a file.

    Args:
        file_path (str): The path to the CSV file.

    Returns:
        list: A list of dictionaries containing the CSV data.

    Raises:
        FileNotFoundError: If the file does not exist.
        IOError: If there is an issue reading the file.
        UnicodeDecodeError: If there is an issue decoding the file's content.
    """
    data = []
    try:
        with open(file_path, mode="r", encoding="utf-8") as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                data.append(row)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        raise
    except IOError:
        print(
            f"Error: An IOError occurred while reading the file '{
              file_path}'."
        )
        raise
    except UnicodeDecodeError:
        print(
            f"Error: A UnicodeDecodeError occurred while decoding the file '{
              file_path}'."
        )
        raise

    return data
