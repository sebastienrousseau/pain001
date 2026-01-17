import csv
import os
import sqlite3


def regenerate_db(version):
    base_path = f"pain001/templates/pain.001.001.{version}"
    csv_path = f"{base_path}/template.csv"
    db_path = f"{base_path}/template.db"

    print(f"Processing v{version}...")

    if not os.path.exists(csv_path):
        print(f"CSV not found: {csv_path}")
        return

    # Read CSV
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        data = list(reader)
        if not data:
            print(f"No data in {csv_path}")
            return
        columns = reader.fieldnames

    # Remove existing DB
    if os.path.exists(db_path):
        os.remove(db_path)

    # Create DB
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table
    col_def = ", ".join([f'"{col}" TEXT' for col in columns])
    cursor.execute(f"CREATE TABLE pain001 ({col_def})")

    # Insert data
    for row in data:
        placeholders = ", ".join(["?"] * len(columns))
        values = [row[col] for col in columns]
        cursor.execute(f"INSERT INTO pain001 VALUES ({placeholders})", values)

    conn.commit()
    conn.close()
    print(f"Regenerated {db_path}")


versions = [f"{i:02d}" for i in range(3, 12)]
for v in versions:
    regenerate_db(v)
