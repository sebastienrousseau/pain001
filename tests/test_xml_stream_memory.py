# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""Writing a large file costs the rows, not copies of the document.

Each run happens in a child process so its peak resident memory
(``resource.getrusage``) is its own. Marked ``slow``: CI runs them, and
``-m "not slow"`` skips them locally.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from pain001.constants import TEMPLATES_DIR, valid_xml_types
from pain001.xml import generate_xml as gx
from pain001.xml.message_registry import prepare_xml_data
from pain001.xml.payment_records import (
    _normalize_financial_fields,
    _RowChanges,
    canonical_for_reading,
)

ROWS = 100_000
TYPE = "pain.001.001.03"
BUNDLE = TEMPLATES_DIR / TYPE
TEMPLATE = str(BUNDLE / "template.xml")
XSD = str(BUNDLE / f"{TYPE}.xsd")


def _sample(message_type: str = TYPE) -> list[dict[str, Any]]:
    """The bundled sample rows of ``message_type``."""
    path = TEMPLATES_DIR / message_type / "template.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


# Builds ROWS distinct rows from the bundled .03 sample, writes them with
# the named function, and prints the peak RSS and the file size.
_CHILD = """
import csv, json, os, resource, sys
from pain001.constants import TEMPLATES_DIR
from pain001.xml import generate_xml as gx
from pain001.xml.register_namespaces import register_namespaces

mode, count = sys.argv[1], int(sys.argv[2])
mt = "pain.001.001.03"
bundle = TEMPLATES_DIR / mt
with (bundle / "template.csv").open(encoding="utf-8", newline="") as fh:
    sample = [dict(row) for row in csv.DictReader(fh)]
rows = []
for index in range(count):
    row = dict(sample[index % len(sample)])
    row["end_to_end_id"] = f"E2E{index:08d}"
    rows.append(row)
register_namespaces(mt)
template = str(bundle / "template.xml")
if mode == "stream":
    path = gx.stream_xml_to_file(rows, mt, template, "out.xml")
else:
    path = gx.generate_xml(
        rows, mt, template, str(bundle / f"{mt}.xsd"), "out.xml"
    )
if sys.platform == "darwin":
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # bytes
else:
    # Linux carries ru_maxrss across exec, so a child started by a large
    # pytest process would report the parent's peak. VmHWM belongs to
    # this process's own address space.
    with open("/proc/self/status", encoding="ascii") as fh:
        line = next(x for x in fh if x.startswith("VmHWM:"))
    peak = int(line.split()[1]) * 1024  # kB
print(json.dumps({"peak": peak, "size": os.path.getsize(path)}))
"""


def _run(mode: str, tmp_path: Path) -> dict[str, int]:
    """Run the child in ``tmp_path``; return its peak RSS and file size."""
    root = str(Path(__file__).resolve().parent.parent)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (root, env.get("PYTHONPATH")) if part
    )
    done = subprocess.run(  # noqa: S603 - our own interpreter and code
        [sys.executable, "-c", _CHILD, mode, str(ROWS)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    result: dict[str, int] = json.loads(done.stdout.strip().splitlines()[-1])
    return result


@pytest.mark.slow
def test_streaming_100k_rows_stays_under_400_mb(tmp_path: Path) -> None:
    """stream_xml_to_file validates its staged file without a tree."""
    result = _run("stream", tmp_path)
    assert result["size"] > 100 * 2**20
    assert result["peak"] < 400 * 2**20, result


@pytest.mark.slow
def test_default_path_peaks_under_four_times_the_output(
    tmp_path: Path,
) -> None:
    """generate_xml holds no string, encoded copy or tree of the file."""
    result = _run("eager", tmp_path)
    assert result["peak"] < 4 * result["size"], result


# --- the default path renders straight to the file -----------------------


def test_the_default_path_never_holds_the_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """generate_xml writes what generate_xml_string returns, without it."""
    expected = gx.generate_xml_string(_sample(), TYPE, TEMPLATE, XSD)

    def refuse(*_args: Any) -> str:
        raise AssertionError("the default path rendered a string")

    monkeypatch.setattr(gx, "generate_xml_string", refuse)
    written = gx.generate_xml(
        _sample(), TYPE, TEMPLATE, XSD, str(tmp_path / "out.xml")
    )
    assert Path(written).read_text(encoding="utf-8") == expected


def test_the_default_path_refuses_an_invalid_document(tmp_path: Path) -> None:
    """An XSD violation is reported and nothing is published."""
    rows = _sample()
    rows[1]["creditor_agent_BIC"] = "NOT A BIC"
    with pytest.raises(RuntimeError, match="failed validation.*BIC"):
        gx.generate_xml(rows, TYPE, TEMPLATE, XSD, str(tmp_path / "x.xml"))
    assert list(tmp_path.iterdir()) == []


def test_an_envelope_still_renders_the_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wrapping needs the whole document, so it takes the eager path."""
    calls: list[int] = []
    real = gx.generate_xml_string

    def spy(*args: Any) -> str:
        calls.append(1)
        return real(*args)

    monkeypatch.setattr(gx, "generate_xml_string", spy)
    written = gx.generate_xml(
        _sample(), TYPE, TEMPLATE, XSD, str(tmp_path / "e.xml"), True
    )
    assert calls == [1]
    assert "AppHdr" in Path(written).read_text(encoding="utf-8")


# --- compact normalised rows ----------------------------------------------


@pytest.mark.parametrize("message_type", valid_xml_types)
def test_compact_rows_prepare_the_same_data(message_type: str) -> None:
    """The preparers see the same rows, compact or copied."""
    rows = _sample(message_type)
    full, count, total = _normalize_financial_fields(rows)
    compact, compact_count, compact_total = _normalize_financial_fields(
        rows, compact=True
    )
    assert (compact_count, compact_total) == (count, total)
    assert all(type(row) is _RowChanges for row in compact)
    assert prepare_xml_data(compact, message_type) == prepare_xml_data(
        full, message_type
    )


def test_a_compact_row_answers_lookups_like_the_full_row() -> None:
    """Changed keys come from the changes, the rest from the input."""
    row = {"payment_amount": "5", "name": "A", "batch_booking": True}
    full, _, _ = _normalize_financial_fields([row])
    (compact,), _, _ = _normalize_financial_fields([row], compact=True)
    assert row == {"payment_amount": "5", "name": "A", "batch_booking": True}
    assert set(dict.keys(compact)) < set(full[0])  # only the changes
    for key in full[0]:
        assert key in compact
        assert compact[key] == compact.get(key) == full[0][key]
    assert "missing" not in compact
    assert compact.get("missing", "default") == "default"
    with pytest.raises(KeyError):
        compact["missing"]


def test_canonical_rows_are_read_without_a_copy() -> None:
    """A row already canonical is returned as is; an alias is copied."""
    row = _sample()[0]
    assert canonical_for_reading(row) is row
    aliased = {"amount": "1.00"}
    copied = canonical_for_reading(aliased)
    assert copied is not aliased
    assert copied["payment_amount"] == "1.00"


def test_the_deprecation_warning_names_the_caller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without output_path, the warning points at generate_xml's caller."""
    monkeypatch.chdir(tmp_path)
    template = tmp_path / "template.xml"
    template.write_text(Path(TEMPLATE).read_text(encoding="utf-8"))
    with pytest.warns(DeprecationWarning, match="without output_path") as got:
        gx.generate_xml(_sample(), TYPE, str(template), XSD)
    assert got[0].filename == __file__
