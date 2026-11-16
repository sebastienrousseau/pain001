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

"""Import a heavy dependency when it is first used, not when imported.

The standard library's recipe (``importlib.util.LazyLoader``): the
module object is bound and registered at once, and its code runs on the
first attribute access. pain001 uses it for xmlschema, which costs about
60 ms to import and which ``pain001 --help`` never touches.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import threading
from types import ModuleType

#: Serialises lazy_module so two threads never both create the module.
_LOCK = threading.Lock()
#: The lazy modules lazy_module made, by name.
_CREATED: dict[str, ModuleType] = {}


def lazy_module(name: str) -> ModuleType:
    """Return ``name``, loaded on first attribute access.

    Args:
        name: The absolute module name.

    Returns:
        The module already imported (waiting for an import another
        thread has in progress), or a lazily loading one registered in
        ``sys.modules`` so every other importer shares it.
    """
    with _LOCK:
        module = sys.modules.get(name)
        if module is None:
            return _register_lazy(name)
        if module is _CREATED.get(name):
            return module
    # Another thread may still be running this module's code: the import
    # system waits for it, where a sys.modules lookup alone would hand
    # out the half-initialised module. Waiting outside the lock keeps two
    # unrelated imports from blocking each other.
    return importlib.import_module(name)


def _register_lazy(name: str) -> ModuleType:
    """Create, register and return a lazily loading ``name``.

    The caller holds ``_LOCK``.

    Args:
        name: The absolute module name.

    Returns:
        The lazily loading module, registered in ``sys.modules``.

    Raises:
        ModuleNotFoundError: If the module is not installed.
    """
    spec = importlib.util.find_spec(name)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)
    loader = importlib.util.LazyLoader(spec.loader)
    spec.loader = loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    _CREATED[name] = module
    return module


__all__ = ["lazy_module"]
