import csv
import os
import sqlite3
import sys
from typing import Any

# Ensure we can import pain001
sys.path.append(os.getcwd())

from pain001.core.core import process_files  # noqa: E402

# Constants
ISO_VERSIONS = [f"pain.001.001.{str(i).zfill(2)}" for i in range(3, 12)]
TEMPLATE_PATH_FMT = "pain001/templates/{version}/template.xml"
XSD_PATH_FMT = "pain001/templates/{version}/{version}.xsd"
CSV_PATH = "tests/data/template.csv"
DB_PATH = "tests/data/test_matrix.db"


def setup_sqlite_db(data: list[dict[str, Any]]):
    """Create a temporary SQLite DB with table 'pain001' populated with data."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if not data:
        return

    # Create table 'pain001'
    columns = list(data[0].keys())
    col_def = ", ".join([f'"{col}" TEXT' for col in columns])
    cursor.execute(f"CREATE TABLE pain001 ({col_def})")

    for row in data:
        placeholders = ", ".join(["?"] * len(columns))
        values = [row[col] for col in columns]
        cursor.execute(f"INSERT INTO pain001 VALUES ({placeholders})", values)

    conn.commit()
    conn.close()


def run_matrix_test():
    print("----------------------------------------------------------------")
    print(" MATRIX TEST: 4 Input Sources x 9 ISO Versions")
    print("----------------------------------------------------------------")

    # 1. Prepare Data Payload from CSV
    try:
        # Detect delimiter
        with open(CSV_PATH, encoding="utf-8") as f:
            line = f.readline()
            delimiter = ";" if ";" in line else ","

        with open(CSV_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            data_list = list(reader)
    except Exception as e:
        print(f"CRITICAL: Failed to load CSV data: {e}")
        sys.exit(1)

    if not data_list:
        print("CRITICAL: No data in CSV")
        sys.exit(1)

    # Prepare DB
    setup_sqlite_db(data_list)

    print(f"Data Loaded: {len(data_list)} records from {CSV_PATH}")

    pass_count = 0
    total_count = 0

    # 2. Iterate Versions
    for version in ISO_VERSIONS:
        print(f"\n>> Version: {version}")

        template_file = TEMPLATE_PATH_FMT.format(version=version)
        xsd_file = XSD_PATH_FMT.format(version=version)

        # Expected output path
        output_file = os.path.join(
            os.path.dirname(template_file), f"{version}.xml"
        )

        # Verify assets exist
        if not os.path.exists(template_file):
            print(f"   [SKIP] Template not found: {template_file}")
            continue

        sources = [
            ("List", data_list),
            ("Dict", data_list[0]),
            ("SQLite", DB_PATH),
            ("CSV", CSV_PATH),
        ]

        for source_name, source_data in sources:
            total_count += 1
            print(f"   - {source_name: <8} ... ", end="", flush=True)

            # Clean existing output
            if os.path.exists(output_file):
                os.remove(output_file)

            try:
                # Capture stdout to silence logs unless error
                # sys.stdout = open(os.devnull, 'w') # Actually don't silence for now to see errors

                process_files(version, template_file, xsd_file, source_data)

                # Check for output
                if os.path.exists(output_file):
                    print("PASS")
                    pass_count += 1
                else:
                    print("FAIL (No Output Created)")
            except SystemExit:
                # Catch sys.exit(1) from generate_xml
                print("FAIL (Process Exited)")
            except Exception as e:
                print(f"FAIL (Exception: {e})")
            finally:
                # sys.stdout = sys.__stdout__
                pass

    print("----------------------------------------------------------------")
    print(f"RESULT: {pass_count}/{total_count} PASSED")
    if pass_count == total_count:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    run_matrix_test()
