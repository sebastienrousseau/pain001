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

"""Parquet data loaders for pain001 (optional feature)."""

from pain001.parquet.load_parquet_data import (
    HAS_PARQUET_SUPPORT,
    load_parquet_data,
    load_parquet_data_streaming,
)

__all__ = [
    "HAS_PARQUET_SUPPORT",
    "load_parquet_data",
    "load_parquet_data_streaming",
]
