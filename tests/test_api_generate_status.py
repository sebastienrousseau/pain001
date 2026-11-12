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


"""``POST /generate`` documents the status of every verdict it gives."""

from pain001.api.app import app


def _generate_responses() -> dict:
    return app.openapi()["paths"]["/api/v1/generate"]["post"]["responses"]


def test_refused_data_is_documented_as_422():
    """Row errors and scheme violations come back as a 422 body."""
    schema = _generate_responses()["422"]["content"]["application/json"]
    refs = {option["$ref"] for option in schema["schema"]["anyOf"]}
    assert refs == {
        "#/components/schemas/GenerateXMLResponse",
        "#/components/schemas/HTTPValidationError",
    }


def test_errors_are_documented():
    """A refused input and an internal failure are documented."""
    responses = _generate_responses()
    assert {"200", "400", "422", "500"} <= set(responses)
