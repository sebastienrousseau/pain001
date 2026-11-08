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

"""No commercial bank is named in anything this project publishes.

The maintainer's rule: public artefacts (the library wheel, the
website, the MCP and LSP servers) carry no bank names and no
bank-derived overlays. Public scheme rulebooks, central-bank and
clearing-system publications and ISO 20022 artefacts may be cited by
name; a source that is a bank's own document is described neutrally
("a Swedish bank's pain.001 implementation guide").

The wheel's file list is derived from ``[tool.poetry]`` in
pyproject.toml (``packages``, ``include`` and ``exclude``), the same
inputs the build backend reads, so a new data directory is scanned
the day it is added to the package. The published manual (``docs/``
and ``SCHEMES.md``, which it links) is scanned too.

``BANK_NAMES`` and ``BANK_ACRONYMS`` are the one place the denylist
lives. No allowlist exists: the ISO external code sets name central
banks and supervisors only ("Central Bank of Ireland", "De Nederlandsche
Bank (DNB)"), which the patterns below already leave alone. If a
future ISO release names a commercial bank in its own published text,
add an ``ALLOWED`` entry here naming the file and the exact phrase, and
say why in the commit; never edit ISO's text.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Bank and bank product names, matched case-insensitively as whole
#: words; a space matches any run of whitespace (YAML folds long lines).
BANK_NAMES = (
    # UK and Ireland
    "NatWest",
    "Bankline",
    "Barclays",
    "Lloyds",
    "Halifax",
    "Santander",
    "Royal Bank of Scotland",
    "Nationwide Building Society",
    "Coutts",
    "Metro Bank",
    "Virgin Money",
    "Clydesdale",
    "Bank of Ireland",
    "Allied Irish",
    "Ulster Bank",
    "Standard Chartered",
    # Continental Europe
    "Deutsche Bank",
    "DZ Bank",
    "Commerzbank",
    "Postbank",
    "Sparkasse",
    "Volksbank",
    "Raiffeisen",
    "UniCredit",
    "Intesa Sanpaolo",
    "BNP Paribas",
    "Societe Generale",
    "Société Générale",
    "Credit Agricole",
    "Crédit Agricole",
    "Natixis",
    "BBVA",
    "CaixaBank",
    "Sabadell",
    "Rabobank",
    "ABN AMRO",
    "ING Bank",
    "InsideBusiness",
    "KBC",
    "Belfius",
    "Erste Bank",
    "Credit Suisse",
    "UBS AG",
    # Nordics
    "Nordea",
    "Swedbank",
    "Handelsbanken",
    "Skandinaviska Enskilda",
    "Danske Bank",
    "DNB Bank",
    "Nykredit",
    # Americas
    "Citibank",
    "Citigroup",
    "CitiDirect",
    "Bank of America",
    "CashPro",
    "JPMorgan",
    "JP Morgan",
    "J.P. Morgan",
    "Wells Fargo",
    "Goldman Sachs",
    "Morgan Stanley",
    "Bank of New York",
    "State Street",
    "Huntington",
    "Cross River",
    "East West Bank",
    "PNC",
    "Truist",
    "Fifth Third",
    "Capital One",
    "KeyBank",
    "Silicon Valley Bank",
    "Royal Bank of Canada",
    "Bank of Montreal",
    "Scotiabank",
    "Toronto-Dominion",
    "Itau",
    "Bradesco",
    # Asia-Pacific and the Gulf
    "HSBCnet",
    "Hang Seng",
    "Bank of China",
    "Bank of East Asia",
    "United Overseas Bank",
    "Oversea-Chinese Banking",
    "Development Bank of Singapore",
    "Maybank",
    "Hong Leong",
    "RHB Bank",
    "Public Bank Berhad",
    "AmBank",
    "Mizuho",
    "Sumitomo Mitsui",
    "Mitsubishi UFJ",
    "Kasikornbank",
    "Bangkok Bank",
    "Westpac",
    "Commonwealth Bank",
    "National Australia Bank",
    "Emirates NBD",
    "Mashreq",
    "First Abu Dhabi",
    "Qatar National Bank",
    "Commercial Bank of Qatar",
    "Doha Bank",
    "Al Rajhi",
    # Payment firms that hold banking licences
    "Revolut",
    "Monzo",
    "Starling Bank",
)

#: Abbreviations, matched case-sensitively as whole words so that
#: ordinary words ("citing", "dbs" in a path) do not trip them.
BANK_ACRONYMS = (
    "ADCB",
    "ANZ",
    "BofA",
    "BNY",
    "CIMB",
    "Citi",
    "DBS",
    "HDFC",
    "HSBC",
    "ICBC",
    "ICICI",
    "ING",
    "MUFG",
    "OCBC",
    "QNB",
    "RBS",
    "SEB",
    "SMBC",
    "UOB",
)

#: A central bank is a public source ("Central Bank of Ireland"), never
#: a hit; the guard is fixed width as ``re`` lookbehind requires.
_NOT_CENTRAL = r"(?<!Central )"


def _phrase(name: str) -> str:
    return r"\s+".join(re.escape(word) for word in name.split())


DENYLIST = re.compile(
    "|".join(
        [
            rf"(?i:{_NOT_CENTRAL}\b(?:{'|'.join(map(_phrase, BANK_NAMES))})\b)",
            rf"\b(?:{'|'.join(BANK_ACRONYMS)})\b",
        ]
    )
)


def _poetry() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["tool"]["poetry"]


def _tracked(prefix: str) -> set[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", prefix],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return {p.decode() for p in out.split(b"\0") if p}


def wheel_files() -> list[Path]:
    """Every file the wheel ships, from the package configuration.

    ``packages`` takes the whole package tree (git-tracked files, as
    the backend skips what the VCS ignores), ``include`` adds the data
    globs and ``exclude`` removes paths.
    """
    poetry = _poetry()
    files: set[str] = set()
    for package in poetry["packages"]:
        files |= _tracked(package["include"])
    for pattern in poetry.get("include", []):
        glob = pattern if isinstance(pattern, str) else pattern["path"]
        files |= {
            str(p.relative_to(ROOT)) for p in ROOT.glob(glob) if p.is_file()
        }
    excluded = {
        str(p.relative_to(ROOT))
        for pattern in poetry.get("exclude", [])
        for p in ROOT.glob(pattern)
    }
    return sorted(
        ROOT / f
        for f in files - excluded
        if "__pycache__" not in f and (ROOT / f).is_file()
    )


def manual_files() -> list[Path]:
    """The published manual and the scheme catalogue it links."""
    return sorted(ROOT / f for f in _tracked("docs") | {"SCHEMES.md"})


def offenders(paths: list[Path]) -> list[str]:
    """``path:line: name`` for every denylisted name in ``paths``."""
    hits = []
    for path in paths:
        text = path.read_bytes().decode("utf-8", errors="ignore")
        hits.extend(
            f"{path.relative_to(ROOT)}:"
            f"{text.count(chr(10), 0, match.start()) + 1}: {match.group(0)}"
            for match in DENYLIST.finditer(text)
        )
    return hits


def test_wheel_file_list_covers_code_and_data() -> None:
    """The derived list is the shipped tree, not an empty set."""
    names = {str(p.relative_to(ROOT)) for p in wheel_files()}
    assert "pain001/validation/rails.py" in names
    assert any(n.endswith(".provenance.yaml") for n in names)
    assert any(n.startswith("pain001/test_fixtures/") for n in names)
    assert not any(n.startswith("pain001/tmp/") for n in names)


def test_denylist_matches_names_and_spares_central_banks() -> None:
    """The patterns catch a bank and leave public bodies alone."""
    for text in (
        "Nordea pain.001 examples",
        "UOB, OCBC and DBS pages",
        "Citi and Bank of\n  America notes",
        "as published by HSBC",
    ):
        assert DENYLIST.search(text), text
    for text in (
        "Central Bank of Ireland (CBI)",
        "Bank of England",
        "Deutsche Bundesbank",
        "citing the rulebook",
        "Bankgirot OCR reference rules",
        "Association of Banks in Singapore",
    ):
        assert not DENYLIST.search(text), text


def test_no_bank_name_in_shipped_files() -> None:
    """Nothing in the wheel names a commercial bank."""
    assert offenders(wheel_files()) == []


def test_no_bank_name_in_published_manual() -> None:
    """The manual and the scheme catalogue name no commercial bank."""
    assert offenders(manual_files()) == []
