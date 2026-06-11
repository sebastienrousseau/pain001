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

"""Use built-in configuration profiles to preset CLI options.

Profiles bundle message type and streaming options under a single
name, so ``pain001 --profile sepa_credit_transfer -d payments.csv``
replaces several flags. This example lists the built-in profiles and
shows how a profile changes the resolved configuration.

Run from the repository root::

    python examples/04_config_profiles.py
"""

from pain001 import ConfigManager


def main() -> None:
    """List built-in profiles and resolve configuration with one."""
    manager = ConfigManager()

    print("Built-in profiles:")
    for name, settings in manager.presets.get("profiles", {}).items():
        print(f"  {name}: {settings}")

    resolved = manager.resolve({"profile": "instant_credit_transfer"})
    assert resolved["xml_message_type"] == "pain.001.001.06"
    assert resolved["streaming"] is True

    print("\nResolved with profile 'instant_credit_transfer':")
    print(f"  xml_message_type = {resolved['xml_message_type']}")
    print(f"  streaming        = {resolved['streaming']}")
    print(f"  chunk_size       = {resolved['chunk_size']}")


if __name__ == "__main__":
    main()
