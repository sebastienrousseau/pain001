# Copyright (C) 2023 Sebastien Rousseau.
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
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""JSON schema files for ISO 20022 payment message validation.

This package contains JSON Schema definitions for validating payment data
before generating ISO 20022 XML messages. Schemas are available for all
supported pain.001.001 versions (03-11).

Usage:
    from pathlib import Path
    schema_dir = Path(__file__).parent
    schema_path = schema_dir / "pain.001.001.03.schema.json"
"""

__all__ = []
