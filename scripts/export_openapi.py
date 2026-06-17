#!/usr/bin/env python3
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

"""Export the Pain001 REST API's OpenAPI document.

Writes the schema produced by the FastAPI app to a file (default
``openapi.json``), ready to feed to an SDK generator such as
``openapi-generator-cli``::

    python scripts/export_openapi.py openapi.json
    npx @openapitools/openapi-generator-cli generate \\
        -i openapi.json -g python -o ./pain001-client

Requires the ``api`` extra: ``pip install "pain001[api]"``.
"""

import json
import sys

from pain001.api.app import app


def main(argv: list[str] | None = None) -> int:
    """Write the OpenAPI schema to the path given as the first argument.

    Args:
        argv: Optional argument vector (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (``0`` on success).
    """
    args = sys.argv[1:] if argv is None else argv
    output = args[0] if args else "openapi.json"
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(app.openapi(), handle, indent=2)
    print(f"Wrote OpenAPI schema to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
