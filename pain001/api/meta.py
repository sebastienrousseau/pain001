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

"""OpenAPI metadata for the REST API: tag groups, description, reference page.

Kept apart from :mod:`pain001.api.app` so the application module holds
routes and wiring only.
"""

from __future__ import annotations

from typing import Any

CANCEL_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"description": "No job has this id"},
    409: {"description": "The job has already finished; it is left as it was"},
}

GENERATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"description": "The input file or a scheme name was refused"},
    422: {
        "description": (
            "Rows failed validation or a scheme rule (`success: false`, "
            "with `validation_errors` or `scheme_violations`), or the "
            "request body is malformed (`detail`)"
        ),
        "content": {
            "application/json": {
                "schema": {
                    "anyOf": [
                        {"$ref": "#/components/schemas/GenerateXMLResponse"},
                        {"$ref": "#/components/schemas/HTTPValidationError"},
                    ]
                }
            }
        },
    },
    500: {"description": "Generation failed inside the server"},
}
"""The error statuses ``POST /generate`` answers, for the OpenAPI document."""

# OpenAPI tag metadata — drives the grouped, described sections in the
# interactive docs and any generated SDKs.
TAGS_METADATA = [
    {
        "name": "Health",
        "description": "Liveness and version probe for load balancers.",
    },
    {
        "name": "Validation",
        "description": (
            "Validate payment data against the XSD schema and, optionally, "
            "a payment-scheme rulebook — without producing a file."
        ),
    },
    {
        "name": "Generation",
        "description": (
            "Generate ISO 20022 XML synchronously or as a background job, "
            "and download the result."
        ),
    },
    {
        "name": "Job Management",
        "description": "Poll, cancel, and manage asynchronous generation jobs.",
    },
    {
        "name": "Faces",
        "description": (
            "Project a pain.001 document into another standard's JSON "
            "shape (UK Open Banking, Berlin Group, ISO 20022 names) with a "
            "loss report of every element not carried."
        ),
    },
    {
        "name": "UI",
        "description": (
            "Backing endpoints for the hosted dashboard at `/api/v1/ui`: "
            "the same validation and generation, fed with an uploaded "
            "file's content instead of a server-side path."
        ),
    },
]

API_DESCRIPTION = """\
RESTful API for ISO 20022 **pain.001** / **pain.008** XML generation and
validation.

* **Versioned** — all endpoints are served under `/api/v1`; the unversioned
  `/api/*` paths remain as a backwards-compatible alias.
* **Authenticated** — set `PAIN001_API_KEY` to require a
  `Authorization: Bearer <key>` header (open in local development).
* **Rate limited** — set `PAIN001_RATE_LIMIT` (e.g. `100/minute`) to cap
  requests per client.

Interactive reference: [`/api/reference`](/api/reference) ·
OpenAPI document: [`/openapi.json`](/openapi.json) ·
Dashboard: [`/api/v1/ui`](/api/v1/ui) (disable with `PAIN001_UI_DISABLED=1`)
"""

# The interactive Scalar reference page served at ``/api/reference``.
SCALAR_HTML = """\
<!doctype html>
<html>
  <head>
    <title>Pain001 REST API — Reference</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body>
    <script
      id="api-reference"
      data-url="/openapi.json"></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
  </body>
</html>
"""
