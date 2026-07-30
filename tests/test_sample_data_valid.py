# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Guard: every bundled sample CSV must pass the library's own validators.

The shipped sample data (template CSVs, examples, fixtures) once contained
IBANs with invalid mod-97 checksums and malformed BICs that went unnoticed
because nothing validated the samples against Pain001's own rules. This
suite closes that gap: it lints each sample with the LSP diagnostic engine —
the same validators the generator uses — and fails CI on any invalid
IBAN/BIC/currency cell, so bad sample data can never ship again.
"""

import csv
import glob

import pytest

from pain001.lsp.diagnostics import diagnostics_for_csv

_BLOCKING_CODES = {"invalid-iban", "invalid-bic", "invalid-currency"}

# Every sample CSV a user might copy or that the docs/tests rely on.
_SAMPLE_CSVS = sorted(
    glob.glob("pain001/templates/*/template.csv")
    + glob.glob("examples/data/*.csv")
    + ["pain001/test_fixtures/template.csv"]
)


def _message_type_for(path: str) -> str:
    """Infer the ISO 20022 message type a sample targets from its path.

    Args:
        path: Path to the sample CSV.

    Returns:
        The message type to validate the sample against.
    """
    return "pain.008.001.02" if "008" in path else "pain.001.001.03"


def test_sample_csvs_discovered() -> None:
    """The glob actually finds the bundled samples (guards against typos)."""
    assert len(_SAMPLE_CSVS) >= 12


@pytest.mark.parametrize("path", _SAMPLE_CSVS)
def test_sample_csv_has_no_invalid_iban_bic_currency(path: str) -> None:
    """Each bundled sample CSV is free of invalid IBAN/BIC/currency cells."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    diagnostics = [
        d
        for d in diagnostics_for_csv(text, _message_type_for(path))
        if d.code in _BLOCKING_CODES
    ]
    assert not diagnostics, "\n".join(
        f"{path}:{d.line + 1} [{d.code}] {d.message}" for d in diagnostics
    )


@pytest.mark.parametrize("path", _SAMPLE_CSVS)
def test_sample_csv_is_nonempty_and_parses(path: str) -> None:
    """Each sample parses as CSV and carries at least one data row."""
    with open(path, encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows, f"{path} has no data rows"
