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

"""Install hints for formats handled by companion packages.

pain001 dispatches unknown extensions to the plugin registry, so a
format it does not bundle is not an error in itself — it means the
plugin that handles it is not installed. Saying so generically
("install a plugin that registers '.xlsx'") leaves the user to work out
*which* plugin, which is the part they do not know.

This module is the single place that maps an extension to the package
that handles it. It holds no import of the companion and no dependency
on it: it exists purely so the error message can name the thing to
install.

Keep it small. An entry belongs here only when the package is
published, first-party, and the sole obvious handler for that
extension — otherwise the hint becomes an advert, or worse, points at
something abandoned.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

#: Extension -> the pip target that registers a loader for it.
#:
#: Read-only so a caller cannot reshape a process-wide table while
#: composing an error message.
COMPANION_LOADERS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        ".xlsx": "pain001-loader-xlsx",
        ".xlsm": "pain001-loader-xlsx",
        ".gpg": "pain001[gpg]",
        ".asc": "pain001[gpg]",
    }
)


def install_hint(extension: str) -> str | None:
    """Return the pip target that handles ``extension``, if one is known.

    Args:
        extension: File extension including the leading dot. Matched
            case-insensitively, because Windows exports routinely
            produce ``.XLSX``.

    Returns:
        The pip install target (``"pain001-loader-xlsx"``), or ``None``
        when no first-party package claims the extension.

    Example:
        >>> install_hint(".XLSX")
        'pain001-loader-xlsx'
        >>> install_hint(".rtf") is None
        True
    """
    return COMPANION_LOADERS.get(extension.lower())
