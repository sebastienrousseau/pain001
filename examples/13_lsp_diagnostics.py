# Copyright (C) 2023-2026 Pain001. All rights reserved.
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

"""Lint a payment CSV with the Pain001 LSP diagnostic engine.

This is the same engine the ``pain001-lsp`` language server feeds to an
editor — but it has no LSP/editor dependency, so it runs anywhere (here, in
CI, or in your own pre-commit hook). Install the server for editor
integration with ``pip install "pain001[lsp]"``.

Run from the repository root::

    python examples/13_lsp_diagnostics.py
"""

from pain001.lsp import Severity, diagnostics_for_csv

# A document with one clean row and one row seeded with four mistakes:
# a bad IBAN, a bad BIC, a non-ISO currency, and a non-Latin character.
DOCUMENT = """\
id,payment_amount,currency,debtor_name,debtor_account_IBAN,debtor_agent_BIC,creditor_name,creditor_account_IBAN
1,150,EUR,Acme Corp,DE89370400440532013000,BANKDEFFXXX,Globex,DE89370400440532013000
2,150,EURO,Café Solé,DE00INVALID,NOTABIC,Globex,DE89370400440532013000
"""


def main() -> None:
    """Lint the sample document and print the diagnostics found."""
    diagnostics = diagnostics_for_csv(DOCUMENT)

    codes = {d.code for d in diagnostics}
    for diag in diagnostics:
        label = Severity(diag.severity).name
        print(
            f"line {diag.line + 1}, col {diag.col_start:>3}  "
            f"[{label:<7}] {diag.code}: {diag.message}"
        )

    # The seeded row must surface each class of problem.
    expected = {
        "invalid-iban",
        "invalid-bic",
        "invalid-currency",
        "invalid-charset",
    }
    assert expected <= codes, f"missing diagnostics: {expected - codes}"

    # The clean first row must not produce any diagnostics.
    assert all(d.line == 2 for d in diagnostics), "clean row was flagged"
    print(f"\n✓ Found all {len(expected)} expected problem classes.")


if __name__ == "__main__":
    main()
