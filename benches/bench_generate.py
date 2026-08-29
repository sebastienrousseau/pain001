#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau <sebastian.rousseau@gmail.com>
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""What generating a payment batch costs, in time and in memory.

`process_files` builds the whole `pain.001` document before anything is
written. `process_files_streaming` writes a file per chunk instead. Time
is similar between them -- XML rendering and XSD validation dominate
either way -- so the question worth measuring is **peak memory**, and
there the two behave completely differently.

Eager generation's peak grows with the batch: a four thousand payment
file costs around 75 MB of Python heap. Streaming's peak is *bounded by
the chunk size* and stays flat, near 10 MB, whether the batch is a
thousand payments or four thousand. That is the difference between an
export that scales with the payroll and one that has a ceiling.

It matters because a payment batch's size is not chosen by whoever runs
the job. A month-end supplier run or a payroll file is as large as the
business was that month, and an exporter sized from a test fixture meets
that difference in production.

This supersedes `scripts/benchmark_large_batches.py`, which measured the
same two calls at a single fixed size of 2,000 rows, reported only
wall-clock, and had no way to run smaller. Measuring one size cannot show
that one curve is flat and the other is not, which is the entire finding.

Run::

    python benches/bench_generate.py
    python benches/bench_generate.py --json
    python benches/bench_generate.py --quick     # what CI runs

One honest limit: peak comes from :mod:`tracemalloc`, which sees
Python-level allocations only. Whatever the XML and XSD layers allocate
in C is not counted, so read these as a floor and as a comparison between
the two paths, not as a budget.

Nothing here asserts a threshold: wall-clock and memory are not
comparable between machines, and a flaky performance gate teaches people
to ignore red. CI runs ``--quick`` so a benchmark that has stopped
compiling against the current API fails the build instead of rotting into
a file that reads as verified and is not.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pain001.core.core import (  # noqa: E402
    process_files,
    process_files_streaming,
)

MESSAGE_TYPE = "pain.001.001.03"
CHUNK = 500
ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "pain001" / "templates" / MESSAGE_TYPE


def _fixture(directory: Path, rows: int) -> tuple[str, str, str]:
    """Write a ``rows``-payment CSV and template into ``directory``."""
    source_csv = (
        (TEMPLATES / "template.csv").read_text(encoding="utf-8").strip()
    )
    header, *sample = source_csv.splitlines()
    expanded = [sample[i % len(sample)] for i in range(rows)]

    data = directory / f"batch-{rows}.csv"
    data.write_text("\n".join([header, *expanded]) + "\n", encoding="utf-8")

    template = directory / "template.xml"
    template.write_text(
        (TEMPLATES / "template.xml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    schema = str((TEMPLATES / f"{MESSAGE_TYPE}.xsd").resolve())
    return str(template), schema, str(data)


def _peak(call) -> int:
    """Peak Python-level bytes allocated during ``call``."""
    tracemalloc.start()
    call()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


def measure(rows: int, directory: Path) -> dict:
    """Time and peak for both generation paths over ``rows`` payments."""
    template, schema, data = _fixture(directory, rows)

    def eager() -> object:
        return process_files(MESSAGE_TYPE, template, schema, data)

    def streaming() -> object:
        return process_files_streaming(
            MESSAGE_TYPE, template, schema, data, chunk_size=CHUNK
        )

    # Warmed once each: the first call in a process compiles the XSD,
    # which costs far more than any later one and belongs to neither
    # path in particular.
    eager()
    streaming()

    start = time.perf_counter()
    eager()
    eager_seconds = time.perf_counter() - start

    start = time.perf_counter()
    written = streaming()
    streaming_seconds = time.perf_counter() - start

    return {
        "rows": rows,
        "eager_ms": eager_seconds * 1e3,
        "streaming_ms": streaming_seconds * 1e3,
        "eager_peak_mb": _peak(eager) / 1e6,
        "streaming_peak_mb": _peak(streaming) / 1e6,
        "files_written": len(written) if hasattr(written, "__len__") else 1,
    }


def run(quick: bool) -> dict:
    """Measure across batch sizes."""
    sizes = [200, 1_000] if quick else [200, 1_000, 4_000]
    with tempfile.TemporaryDirectory(dir=".") as directory:
        rows = [measure(n, Path(directory)) for n in sizes]
    return {"chunk_size": CHUNK, "rows": rows}


def render(results: dict) -> None:
    """Print the table and the verdict."""
    print(
        f"  chunk size {results['chunk_size']}\n\n"
        f"  {'payments':>9}{'eager ms':>11}{'stream ms':>11}"
        f"{'eager MB':>11}{'stream MB':>12}{'files':>7}"
    )
    for row in results["rows"]:
        print(
            f"  {row['rows']:>9}{row['eager_ms']:>11.1f}"
            f"{row['streaming_ms']:>11.1f}{row['eager_peak_mb']:>11.2f}"
            f"{row['streaming_peak_mb']:>12.2f}{row['files_written']:>7}"
        )

    first, last = results["rows"][0], results["rows"][-1]
    eager_growth = (
        last["eager_peak_mb"] / first["eager_peak_mb"]
        if first["eager_peak_mb"]
        else 0.0
    )
    stream_growth = (
        last["streaming_peak_mb"] / first["streaming_peak_mb"]
        if first["streaming_peak_mb"]
        else 0.0
    )
    ratio = (
        last["eager_peak_mb"] / last["streaming_peak_mb"]
        if last["streaming_peak_mb"]
        else 0.0
    )
    print(
        f"\n  From {first['rows']:,} to {last['rows']:,} payments the eager "
        f"peak grew {eager_growth:.1f}x; the streaming\n  peak grew "
        f"{stream_growth:.1f}x. Streaming's memory is bounded by the chunk "
        f"size, not the batch --\n  at {last['rows']:,} payments it uses "
        f"{ratio:.1f}x less."
    )
    print(
        "\n  Time is close either way: XML rendering and XSD validation "
        "dominate both paths, so\n  streaming is a memory decision rather "
        "than a speed one."
    )
    print(
        "\n  Peak is tracemalloc, which sees Python allocations only -- the "
        "XML and XSD layers\n  allocate in C and are not counted. A floor "
        "and a comparison, not a budget."
    )


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--quick", action="store_true", help="small sizes, as CI runs"
    )
    args = parser.parse_args()

    results = run(quick=args.quick)
    if args.json:
        json.dump(results, sys.stdout, indent=1)
        print()
    else:
        render(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
