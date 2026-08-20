# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Errors for formats handled by a companion package (issue #180).

pain001 dispatches unknown extensions to the plugin registry, so an
`.xlsx` file is not an unsupported format — it means the package that
handles it is not installed. Issue #180 requires the error to say which
package that is:

    Given pain001 is installed without pain001-loader-xlsx
    When I run `pain001 -t pain.001.001.03 -d payments.xlsx`
    Then I get a clear error: "No loader registered for .xlsx; install
    pain001-loader-xlsx"
"""

from __future__ import annotations

import pytest

from pain001.data.loader import _load_from_file
from pain001.exceptions import DataSourceError
from pain001.plugins.companions import COMPANION_LOADERS, install_hint


@pytest.mark.parametrize(
    ("extension", "package"),
    [
        (".xlsx", "pain001-loader-xlsx"),
        (".xlsm", "pain001-loader-xlsx"),
        (".gpg", "pain001[gpg]"),
        (".asc", "pain001[gpg]"),
    ],
)
def test_known_formats_map_to_their_package(
    extension: str, package: str
) -> None:
    """Every companion format names the package that handles it."""
    assert install_hint(extension) == package


@pytest.mark.parametrize("extension", [".XLSX", ".Xlsx", ".GPG"])
def test_hint_lookup_is_case_insensitive(extension: str) -> None:
    """Windows exports routinely produce upper-case extensions."""
    assert install_hint(extension) is not None


def test_unknown_extension_has_no_hint() -> None:
    """An extension nobody claims must not invent a package name."""
    assert install_hint(".rtf") is None


def test_companion_table_is_read_only() -> None:
    """A process-wide table must not be reshapable by a caller."""
    with pytest.raises(TypeError):
        COMPANION_LOADERS[".doc"] = "pain001-loader-word"  # type: ignore[index]


def test_xlsx_error_names_the_package(tmp_path) -> None:
    """The acceptance criterion, as a test."""
    target = tmp_path / "payments.xlsx"
    target.write_bytes(b"not really xlsx")

    with pytest.raises(DataSourceError) as excinfo:
        _load_from_file(str(target))

    message = str(excinfo.value)
    assert "No loader registered for .xlsx" in message
    assert "pain001-loader-xlsx" in message


def test_xlsx_error_does_not_fall_back_to_the_generic_text(
    tmp_path,
) -> None:
    """A named hint replaces the "install a plugin" text, not adds to it.

    Emitting both would leave the user reading two competing
    instructions in one message.
    """
    target = tmp_path / "payments.xlsx"
    target.write_bytes(b"not really xlsx")

    with pytest.raises(DataSourceError) as excinfo:
        _load_from_file(str(target))

    assert "Unsupported file type" not in str(excinfo.value)


def test_unknown_extension_keeps_the_generic_error(tmp_path) -> None:
    """Formats with no companion still get the discovery hint."""
    target = tmp_path / "payments.rtf"
    target.write_bytes(b"{\\rtf1}")

    with pytest.raises(DataSourceError) as excinfo:
        _load_from_file(str(target))

    message = str(excinfo.value)
    assert "Unsupported file type" in message
    assert "pain001 plugins list" in message


def test_a_registered_plugin_wins_over_the_hint(monkeypatch, tmp_path) -> None:
    """Installing the companion must stop the error, not reword it.

    The hint is for the *absence* of a loader. Once one is registered
    for the extension, dispatch has to proceed to it.
    """
    from pain001.plugins import registry

    class _StubXlsxLoader:
        meta = type(
            "M",
            (),
            {
                "name": "xlsx",
                "version": "0.1.0",
                "description": "stub",
                "api_version": (0, 54),
                "source": "test",
            },
        )()
        extensions = (".xlsx",)

        def load(self, path: str):  # pragma: no cover - not reached
            raise AssertionError("stub loader should not be invoked")

    monkeypatch.setattr(
        registry,
        "get_loader_for_extension",
        lambda ext: _StubXlsxLoader() if ext == ".xlsx" else None,
    )

    target = tmp_path / "payments.xlsx"
    target.write_bytes(b"stub")

    with pytest.raises(Exception) as excinfo:
        _load_from_file(str(target))

    # Whatever happens next, it is no longer the "not installed" error.
    assert "No loader registered for .xlsx" not in str(excinfo.value)
