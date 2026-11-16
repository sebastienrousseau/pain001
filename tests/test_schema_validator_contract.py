# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Where SchemaValidator reads its schema from, and how, pinned exactly.

Mutation testing found that the default schema directory, the
confinement to that directory, the escape message and the file
encoding could each change without failing a test.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

import pytest

from pain001.validation import schema_validator
from pain001.validation.schema_validator import SchemaValidator

_TYPE = "pain.001.001.03"
_NAME = f"{_TYPE}.schema.json"


def test_the_default_schema_comes_from_the_package() -> None:
    """With no directory given, the bundled ``schemas/`` file is used."""
    package = Path(schema_validator.__file__).parent.parent
    expected = os.path.realpath(str(package / "schemas" / _NAME))
    assert SchemaValidator(_TYPE).schema_path == expected


def test_a_schema_linked_from_outside_its_directory_is_refused(
    tmp_path: Path,
) -> None:
    """The path check is confined to the schema directory."""
    outside = tmp_path / "outside.json"
    outside.write_text('{"type": "object"}', encoding="utf-8")
    schemas = tmp_path / "schemas"
    schemas.mkdir()
    (schemas / _NAME).symlink_to(outside)
    with pytest.raises(FileNotFoundError) as err:
        SchemaValidator(_TYPE, schema_dir=schemas)
    assert str(err.value).startswith("Schema validation failed: ")


def test_a_path_escaping_the_directory_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the checked path leaves the directory, the refusal says which."""
    monkeypatch.setattr(
        schema_validator,
        "validate_path",
        lambda *args, **kwargs: str(tmp_path.parent / "elsewhere.json"),
    )
    with pytest.raises(FileNotFoundError) as err:
        SchemaValidator(_TYPE, schema_dir=tmp_path)
    assert str(err.value) == (
        f"Schema path escapes schema directory: {tmp_path}"
    )


def test_the_schema_is_read_as_utf8(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The encoding is named, not left to the locale."""
    (tmp_path / _NAME).write_text('{"type": "object"}', encoding="utf-8")
    seen: list[dict[str, Any]] = []

    def spy(path: str, **kwargs: Any) -> io.StringIO:
        """Record the keyword arguments, then read the file."""
        seen.append(kwargs)
        return io.StringIO(Path(path).read_text(**kwargs))

    monkeypatch.setattr(schema_validator, "open", spy, raising=False)
    validator = SchemaValidator(_TYPE, schema_dir=tmp_path)
    assert validator.schema == {"type": "object"}
    assert seen == [{"encoding": "utf-8"}]
