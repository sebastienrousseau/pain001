# Copyright (C) 2023-2026 Sebastien Rousseau.
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

"""The Python pain001 module."""

__version__ = "0.0.47"

__all__ = ["main", "process_files", "__version__"]


def __getattr__(name):
    if name == "main":
        from pain001.__main__ import main

        return main
    if name == "process_files":
        from pain001.core.core import process_files

        return process_files
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
