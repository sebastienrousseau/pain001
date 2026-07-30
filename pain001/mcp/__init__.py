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

"""Model Context Protocol (MCP) server for Pain001.

Exposes Pain001's generation and validation as MCP tools, resources, and
prompts so LLM clients (Claude Desktop, etc.) can build and check ISO
20022 payment files. Install with ``pip install "pain001[mcp]"`` and run
``pain001-mcp``.
"""
