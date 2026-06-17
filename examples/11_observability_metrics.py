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

"""Observe the pipeline with metric callbacks.

Register a callback and Pain001 emits structured metric events as it
loads, validates, and renders — ready to forward to Prometheus,
OpenTelemetry, CloudWatch, or a log line.

Run from the repository root::

    python examples/11_observability_metrics.py
"""

import tempfile
from pathlib import Path

from pain001 import (
    clear_metrics_callbacks,
    process_files,
    register_metrics_callback,
)
from pain001.constants import TEMPLATES_DIR

TEMPLATE_DIR = TEMPLATES_DIR / "pain.001.001.03"


def main() -> None:
    """Capture metric events emitted during a generation run."""
    events = []
    register_metrics_callback(lambda event: events.append(event))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            process_files(
                "pain.001.001.03",
                str(TEMPLATE_DIR / "template.xml"),
                str(TEMPLATE_DIR / "pain.001.001.03.xsd"),
                str(TEMPLATE_DIR / "template.csv"),
                output_path=str(Path(tmp) / "out.xml"),
            )
    finally:
        clear_metrics_callbacks()

    assert events, "expected at least one metric event"
    print(f"Captured {len(events)} metric event(s):")
    for event in events[:8]:
        print(f"  {event.name} {event.attributes}")

    print("Observability example completed.")


if __name__ == "__main__":
    main()
