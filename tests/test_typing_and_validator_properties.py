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

"""Regression tests for the PEP 561 ``py.typed`` marker and property tests
asserting the in-memory and on-disk XSD validators agree.

The typing tests guard a real gap: the package is ``mypy --strict`` clean
internally, but without the ``py.typed`` marker shipped in the
distribution, downstream consumers get none of those types. If the marker
is ever dropped from the source tree or the packaging include list, these
tests fail before a release goes out.
"""

import importlib.util
import os
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from pain001.xml.validate_via_xsd import (
    validate_via_xsd,
    validate_xml_string_via_xsd,
)

# --------------------------------------------------------------------------
# PEP 561 py.typed marker
# --------------------------------------------------------------------------


def _package_dir() -> str:
    """Return the installed ``pain001`` package directory."""
    spec = importlib.util.find_spec("pain001")
    assert spec is not None and spec.origin is not None
    return os.path.dirname(spec.origin)


def test_py_typed_marker_present() -> None:
    """The ``py.typed`` marker must sit beside the package ``__init__``."""
    marker = os.path.join(_package_dir(), "py.typed")
    assert os.path.isfile(marker), (
        "pain001 declares itself typed (mypy --strict) but the PEP 561 "
        "py.typed marker is missing — downstream consumers would not see "
        "the annotations. Restore pain001/py.typed and its packaging "
        "include entries."
    )


def test_py_typed_marker_is_empty() -> None:
    """PEP 561 marks a package as typed with an empty ``py.typed`` file."""
    marker = os.path.join(_package_dir(), "py.typed")
    assert os.path.getsize(marker) == 0


# --------------------------------------------------------------------------
# XSD validator equivalence: in-memory (serverless) vs on-disk
# --------------------------------------------------------------------------

_XSD = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
    '  <xs:element name="Document">'
    "    <xs:complexType>"
    "      <xs:sequence>"
    '        <xs:element name="Amt" type="xs:decimal"/>'
    "      </xs:sequence>"
    "    </xs:complexType>"
    "  </xs:element>"
    "</xs:schema>"
)


@settings(max_examples=60, deadline=None)
@given(
    amount=st.decimals(
        min_value=0,
        max_value=10**9,
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ),
    valid=st.booleans(),
)
def test_string_and_file_validators_agree(amount: object, valid: bool) -> None:
    """`validate_xml_string_via_xsd` and `validate_via_xsd` must return the
    same verdict for the same document.

    The in-memory validator exists for the serverless/API path where XML
    never touches disk; a divergence between it and the on-disk path would
    let a document that passes one gate fail the other, silently, depending
    on deployment shape. This property pins them together across a range of
    valid and deliberately-invalid documents.
    """
    if valid:
        xml = f'<?xml version="1.0"?><Document><Amt>{amount}</Amt></Document>'
    else:
        # `Amt` is required by the schema; omitting it must be rejected.
        xml = '<?xml version="1.0"?><Document></Document>'

    with tempfile.TemporaryDirectory() as tmp:
        xsd_path = os.path.join(tmp, "schema.xsd")
        with open(xsd_path, "w", encoding="utf-8") as fh:
            fh.write(_XSD)

        from_string = validate_xml_string_via_xsd(xml, xsd_path)

        xml_path = os.path.join(tmp, "doc.xml")
        with open(xml_path, "w", encoding="utf-8") as fh:
            fh.write(xml)
        from_file = validate_via_xsd(xml_path, xsd_path)

    assert from_string == from_file
    assert from_string is valid
