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
