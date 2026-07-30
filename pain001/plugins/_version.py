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

"""Single source of truth for the plugin-contract API version.

Lives in its own module so both ``pain001.plugins`` and
``pain001.plugins.registry`` can import it without a cycle.
"""

from __future__ import annotations

PAIN001_API_VERSION: tuple[int, int] = (0, 54)
"""Bumped only when the public plugin Protocols change."""
