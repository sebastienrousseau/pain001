# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Check async loading/generation against the synchronous XML result."""

import asyncio

from pain001.async_adapter import (
    generate_xml_string_async,
    load_payment_data_async,
)
from pain001.constants import TEMPLATES_DIR
from pain001.xml.generate_xml import generate_xml_string


async def main() -> None:
    """Generate real XSD-validated XML without blocking the caller's event loop."""
    edition = "pain.001.001.03"
    directory = TEMPLATES_DIR / edition
    rows = await load_payment_data_async(str(directory / "template.csv"))
    args = (
        rows,
        edition,
        str(directory / "template.xml"),
        str(directory / f"{edition}.xsd"),
    )
    actual = await generate_xml_string_async(*args)
    assert actual == generate_xml_string(*args)
    assert edition in actual
    print("Async loading and generation: byte-exact synchronous parity")


if __name__ == "__main__":
    asyncio.run(main())
