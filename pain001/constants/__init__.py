"""Compatibility shim for legacy package imports.

This module re-exports symbols from the top-level pain001/constants.py.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_constants_path = Path(__file__).resolve().parent.parent / "constants.py"
_spec = spec_from_file_location("pain001._constants_module", _constants_path)
_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

__all__ = list(getattr(_module, "__all__", []))

for _name in __all__:
    globals()[_name] = getattr(_module, _name)
