#!/usr/bin/env python3

"""Measure large-batch XML generation throughput."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from pain001.core.core import process_files, process_files_streaming


def main() -> None:
    base = Path("pain001/templates/pain.001.001.03")
    schema = str((base / "pain.001.001.03.xsd").resolve())
    source_template = (base / "template.xml").read_text(encoding="utf-8")
    source_csv = (
        (base / "template.csv")
        .read_text(encoding="utf-8")
        .strip()
        .splitlines()
    )

    with tempfile.TemporaryDirectory(dir=".") as tmpdir:
        tmp_path = Path(tmpdir)
        data_file = tmp_path / "benchmark.csv"
        template_file = tmp_path / "template.xml"
        header, *rows = source_csv
        expanded_rows = [rows[i % len(rows)] for i in range(2000)]
        data_file.write_text(
            "\n".join([header, *expanded_rows]) + "\n", encoding="utf-8"
        )
        template_file.write_text(source_template, encoding="utf-8")

        started = time.perf_counter()
        process_files(
            "pain.001.001.03", str(template_file), schema, str(data_file)
        )
        non_stream_seconds = time.perf_counter() - started

        started = time.perf_counter()
        output_files = process_files_streaming(
            "pain.001.001.03",
            str(template_file),
            schema,
            str(data_file),
            chunk_size=500,
        )
        stream_seconds = time.perf_counter() - started

    print(f"non_stream_seconds={non_stream_seconds:.3f}")
    print(f"stream_seconds={stream_seconds:.3f}")
    print(f"stream_output_files={len(output_files)}")


if __name__ == "__main__":
    main()
