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

"""Validate every face payload against its target's published schema.

Each payment face (ADR-0005) names a target specification. This script
downloads that specification at a pinned revision, refuses it unless
its SHA-256 matches, and validates the face's payload for every pain.001
file in the corpus the face accepts against the request-body schema.
The specifications are read, never vendored: the Berlin Group
repository's licence is CC BY-ND 4.0.

Usage:
    python scripts/check_face_contracts.py [--cache DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft4Validator

from pain001.corpus import list_files
from pain001.faces import FaceError, project_face


@dataclass(frozen=True)
class Spec:
    """A pinned specification file and the schemas a face must satisfy."""

    url: str
    sha256: str
    schemas: tuple[str, ...]


OB_COMMIT = "484a1795680d9852600247878b9fd2bfe584c0aa"
BG_COMMIT = "1df06aea61492917653218cf564db99fd57e24a8"
SPECS = {
    # Open Banking Read/Write API v4.0.1, MIT Open Licence.
    "uk_open_banking": Spec(
        "https://raw.githubusercontent.com/OpenBankingUK/read-write-api-specs/"
        f"{OB_COMMIT}/dist/openapi/payment-initiation-openapi.json",
        "c02efa09f0ea1baaffd5ae0d4e68d7f3f996b94ac3ec66752e7bf5ec5cee3285",
        ("OBWriteDomesticConsent4", "OBWriteDomestic2"),
    ),
    # NextGenPSD2 XS2A Framework v1.3.16 (2025-11-27).
    "berlin_group": Spec(
        "https://gitlab.com/api/v4/projects/68556348/repository/files/"
        "Core%20PSD2%20Compliancy%2Fpsd2-api_v1.3.16-2025-11-27.openapi.yaml"
        f"/raw?ref={BG_COMMIT}",
        "ab6893b24fe06e773b53af42d10fad465cbe11935d67e2c2d69a6c3efd688b4b",
        ("paymentInitiation_json", "bulkPaymentInitiation_json"),
    ),
}
# A ConsentId turns the consent body into the payment body.
BINDINGS = {"OBWriteDomestic2": {"ConsentId": "contract-check"}}


def fetch(spec: Spec, cache: Path) -> dict[str, Any]:
    """The specification, downloaded once and checked against its pin."""
    target = cache / spec.sha256
    if not target.exists():
        cache.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(spec.url, timeout=60) as response:
            target.write_bytes(response.read())
    data = target.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != spec.sha256:
        target.unlink()
        raise SystemExit(
            f"{spec.url}: SHA-256 {digest} does not match the pin"
        )
    loaded: dict[str, Any] = yaml.safe_load(data.decode("utf-8"))
    return loaded


def validator(document: dict[str, Any], schema: str) -> Draft4Validator:
    """A validator for one component schema, resolving ``#/components``.

    The schema is the spec's ``components`` with a root reference, so
    every ``#/components/schemas/...`` reference resolves inside it.
    """
    return Draft4Validator(
        {
            "$ref": f"#/components/schemas/{schema}",
            "components": document["components"],
        }
    )


def check_face(
    face: str, document: dict[str, Any]
) -> tuple[int, int, list[str]]:
    """``(validated, refused, errors)`` for one face over the corpus."""
    validators = {
        name: validator(document, name) for name in SPECS[face].schemas
    }
    validated = refused = 0
    errors: list[str] = []
    for corpus_file in list_files():
        if not corpus_file.version.startswith("pain.001"):
            continue
        xml = corpus_file.path.read_text(encoding="utf-8")
        for name, check in validators.items():
            try:
                result = project_face(xml, face, bindings=BINDINGS.get(name))
            except FaceError:
                refused += 1
                continue
            body = result.payload
            if name.startswith("bulk") != ("payments" in body):
                continue
            validated += 1
            errors += [
                f"{face} {name} {corpus_file.path.name}: {e.json_path}: {e.message}"
                for e in check.iter_errors(body)
            ]
    return validated, refused, errors


def main(argv: list[str] | None = None) -> int:
    """Check every payment face against its pinned target schema."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--cache", type=Path, default=Path(".cache/face-specs")
    )
    args = parser.parse_args(argv)
    failures = 0
    for face, spec in SPECS.items():
        validated, refused, errors = check_face(face, fetch(spec, args.cache))
        print(
            f"{face}: {validated} payloads valid against {', '.join(spec.schemas)}; {refused} refusals"
        )
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        failures += len(errors)
        if validated == 0:
            print(f"  {face}: nothing was validated", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
