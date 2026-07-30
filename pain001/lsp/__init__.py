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

"""Language Server Protocol support for Pain001 payment CSV files.

The :mod:`pain001.lsp.diagnostics` module holds the pure, dependency-free
diagnostic engine (testable without any LSP runtime). :mod:`pain001.lsp.server`
wires it to an editor over stdio using ``pygls`` (install the ``lsp`` extra).
"""

from pain001.lsp.diagnostics import (
    Diagnostic,
    Severity,
    diagnostics_for_csv,
)

__all__ = ["Diagnostic", "Severity", "diagnostics_for_csv"]
