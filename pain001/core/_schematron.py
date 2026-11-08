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

"""The Schematron check both generation paths run on a written file."""

from typing import Any


def schematron_failure(path: str, schematron: Any, what: str) -> str | None:
    """Return why ``path`` fails the Schematron rulebook, if it does.

    Args:
        path: The XML file just written.
        schematron: The rulebook preset or ``.sch`` path, or ``None``
            when no rulebook was requested.
        what: The start of the message, naming the file's role.

    Returns:
        The error message with the rulebook's report, or ``None`` when
        no rulebook was requested or the file passes it.
    """
    if schematron is None:
        return None
    from pain001.schematron import validate_schematron

    result = validate_schematron(path, rulebook=schematron)
    if result.is_valid:
        return None
    return (
        f"{what} '{path}' using '{schematron}': "
        f"{result.error_count} error(s).\n{result.format_report()}"
    )
