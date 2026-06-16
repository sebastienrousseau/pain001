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

"""Exercise the MCP server's tools as plain functions.

The MCP server (``pain001-mcp``) exposes these over stdio to LLM clients;
here we call the same tool functions directly to show what they do. Run
the actual server with ``pain001-mcp`` after ``pip install pain001[mcp]``.

Run from the repository root::

    python examples/12_mcp_tools.py
"""

import sys

try:
    from pain001.mcp import server
except ImportError:
    print("mcp not installed; run `pip install pain001[mcp]`. Skipping.")
    sys.exit(0)

from pain001.constants import TEMPLATES_DIR
from pain001.csv.load_csv_data import load_csv_data


def main() -> None:
    """Call each MCP tool the way an LLM client would."""
    versions = server.list_supported_versions()
    print(f"list_supported_versions -> {len(versions)} types")

    info = server.inspect_template("pain.001.001.03")
    print(f"inspect_template -> {len(info['columns'])} required columns")

    rows = load_csv_data(
        str(TEMPLATES_DIR / "pain.001.001.03" / "template.csv")
    )
    xml = server.generate_payment_file("pain.001.001.03", rows)
    print(f"generate_payment_file -> {len(xml)} chars of validated XML")

    scheme = server.validate_payment_scheme(rows, profile="sepa-sct")
    print(
        "validate_payment_scheme -> "
        f"valid={scheme['is_valid']}, "
        f"{len(scheme['violations'])} violation(s)"
    )

    print("MCP tools example completed.")


if __name__ == "__main__":
    main()
