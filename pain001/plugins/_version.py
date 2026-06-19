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

"""Single source of truth for the plugin-contract API version.

Lives in its own module so both ``pain001.plugins`` and
``pain001.plugins.registry`` can import it without a cycle.
"""

from __future__ import annotations

PAIN001_API_VERSION: tuple[int, int] = (0, 54)
"""Bumped only when the public plugin Protocols change."""
