# Copyright (C) 2023-2024 Sebastien Rousseau.
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
import logging

logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")


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
        ValueError: If the CSV file is empty.
    """
    data = []
    try:
        with open(file_path, mode="r", encoding="utf-8") as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                data.append(row)
    except FileNotFoundError:
        logging.error(f"File '{file_path}' not found.")
        raise
    except IOError:
        logging.error(
            f"An IOError occurred while reading the file '{file_path}'."
        )
        raise
    except UnicodeDecodeError:
        logging.error(
            "A UnicodeDecodeError occurred while decoding the file '"
            + file_path
            + "'."
        )
        raise

    if not data:
        raise ValueError(f"The CSV file '{file_path}' is empty.")

    return data
