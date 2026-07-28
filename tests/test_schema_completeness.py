"""Every shipped XSD must be a real ISO schema, not a permissive stub.

``pain.001.001.12`` shipped a 475-byte placeholder whose body was a
single ``<xs:any processContents="lax"/>``. It parsed, it validated, and
it accepted literally any document — so ``-t pain.001.001.12`` reported
successful XSD validation while performing none. Nothing detected it:
no test asserted that a schema *rejects* anything, and the compatibility
matrix on the website advertised XSD validation for that version.

These tests fail if a stub is ever shipped again, in two independent
ways: structurally (the schema must not be a bare wildcard) and
behaviourally (the schema must reject a document full of nonsense).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / "pain001" / "templates"

# A genuine ISO schema for these messages is tens of kilobytes; the stub
# was 475 bytes. The threshold is deliberately far below the smallest
# real schema (pain.001.001.03, ~41 KB) so it flags placeholders without
# being brittle about future schema sizes.
MIN_REAL_SCHEMA_BYTES = 10_000


#: Versions shipping a placeholder schema instead of the ISO original.
#: These are expected failures, not accepted behaviour: the version is
#: advertised in valid_xml_types and the CLI reports successful XSD
#: validation while performing none. Marked strict, so the moment a real
#: schema is dropped in the test passes unexpectedly and CI fails until
#: the entry is removed from here.
# Empty: every shipped schema is now an ISO publication. The
# machinery stays so a placeholder can never be reintroduced
# silently — add a version here only with a dated reason.
KNOWN_PLACEHOLDER_SCHEMAS: set[str] = set()


def _schema_paths() -> list[Path]:
    paths = sorted(TEMPLATES.glob("*/*.xsd"))
    assert paths, "no schemas found — has the template layout changed?"
    return [
        pytest.param(
            p,
            marks=pytest.mark.xfail(
                strict=True,
                reason=(
                    f"{p.parent.name} ships a placeholder schema; obtain the "
                    "official XSD from iso20022.org or withdraw the version"
                ),
            ),
        )
        if p.parent.name in KNOWN_PLACEHOLDER_SCHEMAS
        else pytest.param(p)
        for p in paths
    ]


@pytest.mark.parametrize("xsd", _schema_paths(), ids=lambda p: p.parent.name)
def test_schema_is_not_a_placeholder(xsd: Path) -> None:
    """The schema must define real content, not a wildcard passthrough."""
    text = xsd.read_text(encoding="utf-8")

    assert len(text.encode()) >= MIN_REAL_SCHEMA_BYTES, (
        f"{xsd.parent.name}: schema is {len(text.encode())} bytes — that is "
        "a placeholder, not an ISO schema. Ship the official XSD or remove "
        "the version from valid_xml_types; do not advertise XSD validation "
        "that does not happen."
    )

    # A bare <xs:any> as the document body accepts anything.
    body_wildcards = re.findall(r"<xs:any\b[^>]*>", text)
    assert not body_wildcards or len(text.encode()) >= MIN_REAL_SCHEMA_BYTES, (
        f"{xsd.parent.name}: schema body is a wildcard passthrough"
    )

    # Real ISO schemas declare named complex types for the message model.
    assert text.count("<xs:complexType") >= 5, (
        f"{xsd.parent.name}: only {text.count('<xs:complexType')} complex "
        "type(s) — a real pain message model defines many"
    )


@pytest.mark.parametrize("xsd", _schema_paths(), ids=lambda p: p.parent.name)
def test_schema_rejects_nonsense(xsd: Path, tmp_path: Path) -> None:
    """Behavioural proof: the schema must reject a junk document.

    A schema that accepts this is not validating anything, whatever its
    size or shape.
    """
    from pain001.xml.validate_via_xsd import validate_via_xsd

    version = xsd.parent.name
    namespace = f"urn:iso:std:iso:20022:tech:xsd:{version}"
    junk = tmp_path / "junk.xml"
    junk.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Document xmlns="{namespace}">'
        "<TotalNonsense>this is not a payment message</TotalNonsense>"
        "</Document>\n",
        encoding="utf-8",
    )

    assert validate_via_xsd(str(junk), str(xsd)) is False, (
        f"{version}: schema accepted a document containing only "
        "<TotalNonsense> — it is not validating anything"
    )
