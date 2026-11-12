# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Check every async wrapper against its synchronous counterpart."""

import asyncio
import contextlib
import shutil
import tempfile
from pathlib import Path

from pain001 import generate_xml_string
from pain001.async_adapter import (
    generate_xml_string_async,
    load_payment_data_async,
    process_files_async,
    process_files_streaming_async,
    validate_all_async,
)
from pain001.constants import TEMPLATES_DIR
from pain001.core.core import process_files, process_files_streaming
from pain001.validation.service import ValidationConfig, ValidationService

EDITION = "pain.001.001.03"
DIRECTORY = TEMPLATES_DIR / EDITION
TEMPLATE = DIRECTORY / "template.xml"
XSD = DIRECTORY / f"{EDITION}.xsd"
DATA_FILE = Path(__file__).resolve().parent / "data" / "payments.csv"


def _read(path: str | Path) -> str:
    """Return a generated file's text."""
    return Path(path).read_text(encoding="utf-8")


async def check_string_generation() -> None:
    """Generate real XSD-validated XML without blocking the event loop."""
    rows = await load_payment_data_async(str(DIRECTORY / "template.csv"))
    args = (rows, EDITION, str(TEMPLATE), str(XSD))
    actual = await generate_xml_string_async(*args)
    assert actual == generate_xml_string(*args)
    assert EDITION in actual
    print("Async loading and generation: byte-exact synchronous parity")


async def check_process_files() -> None:
    """Compare process_files_async with process_files on the same CSV."""
    actual = await process_files_async(
        EDITION,
        TEMPLATE.name,
        XSD.name,
        DATA_FILE.name,
        output_path=f"async/{EDITION}.xml",
    )
    expected = process_files(
        EDITION,
        TEMPLATE.name,
        XSD.name,
        DATA_FILE.name,
        output_path=f"sync/{EDITION}.xml",
    )
    assert Path(actual).parent.name == "async"
    assert _read(actual) == _read(expected)
    print("Async process_files: byte-exact synchronous parity")


async def check_streaming() -> None:
    """Compare chunked async generation with process_files_streaming."""
    args = (EDITION, TEMPLATE.name, XSD.name, DATA_FILE.name)
    actual = await process_files_streaming_async(*args, 2, output_dir="async")
    expected = process_files_streaming(*args, 2, output_dir="sync")
    assert len(actual) == len(expected) == 2
    assert [_read(path) for path in actual] == [
        _read(path) for path in expected
    ]
    print(f"Async streaming: {len(actual)} chunk files, synchronous parity")


async def check_validation() -> None:
    """Compare validate_all_async with ValidationService.validate_all."""
    service = ValidationService()
    config = ValidationConfig(
        xml_message_type=EDITION,
        xml_template_file_path=str(TEMPLATE),
        xsd_schema_file_path=str(XSD),
        data_file_path=str(DATA_FILE),
    )
    report = await validate_all_async(service, config)
    assert report == service.validate_all(config)
    assert report.is_valid, report.errors
    print(f"Async validation: {len(report.results)} checks, same report")


async def main() -> None:
    """Run each async wrapper and check it against the sync result."""
    await check_string_generation()
    # The file-path wrappers only accept paths under the working
    # directory, so work in a temp dir holding copies of the inputs.
    with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp):
        Path("sync").mkdir()
        Path("async").mkdir()
        for source in (TEMPLATE, XSD, DATA_FILE):
            shutil.copy(source, tmp)
        await check_process_files()
        await check_streaming()
    await check_validation()


if __name__ == "__main__":
    asyncio.run(main())
