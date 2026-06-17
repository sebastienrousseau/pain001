# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
