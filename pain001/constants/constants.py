# Copyright (C) 2023-2024 Sebastien Rousseau.
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

# Defines the valid XML types for the ISO 20022 Payment Initiation
# message types that are supported by the pain001 library.
valid_xml_types = [
    "pain.001.001.03",  # Customer Credit Transfer Initiation (pain.001.001.03)
    "pain.001.001.04",  # Customer Direct Debit Initiation (pain.001.001.04)
    "pain.001.001.05",  # Request for Payment Status (pain.001.001.05)
    "pain.001.001.06",  # Notification of Payment Status (pain.001.001.06)
    "pain.001.001.07",  # Request for Reversal (pain.001.001.07)
    "pain.001.001.08",  # Notification of Reversal (pain.001.001.08)
    "pain.001.001.09",  # Request for Amendment (pain.001.001.09)
    "pain.001.001.10"  # Notification of Amendment (pain.001.001.10)
    "pain.001.001.11",  # Request for Cancellation (pain.001.001.11)
]
