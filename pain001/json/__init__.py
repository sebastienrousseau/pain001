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

"""JSON data loaders for pain001."""

# pylint: disable=duplicate-code
from pain001.json.load_json_data import (
    load_json_data,
    load_json_data_streaming,
    load_jsonl_data,
    load_jsonl_data_streaming,
)

__all__ = [
    "load_json_data",
    "load_json_data_streaming",
    "load_jsonl_data",
    "load_jsonl_data_streaming",
]
