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

"""Stream a large batch into one XML file per chunk.

For batches too large to hold in memory, ``process_files_streaming``
chunks the input and writes one validated XML file per chunk, each with
its own computed ``NbOfTxs`` and ``CtrlSum``.

Run from the repository root::

    python examples/09_streaming_large_batch.py
"""

import tempfile
from pathlib import Path

from pain001.constants import TEMPLATES_DIR
from pain001.core.core import process_files_streaming

MESSAGE_TYPE = "pain.001.001.03"
TEMPLATE_DIR = TEMPLATES_DIR / MESSAGE_TYPE


def main() -> None:
    """Generate chunked XML files from the bundled sample data."""
    with tempfile.TemporaryDirectory() as tmp:
        written = process_files_streaming(
            MESSAGE_TYPE,
            str(TEMPLATE_DIR / "template.xml"),
            str(TEMPLATE_DIR / f"{MESSAGE_TYPE}.xsd"),
            str(TEMPLATE_DIR / "template.csv"),
            chunk_size=2,
            output_dir=tmp,
        )
        assert written, "expected at least one chunk file"
        for path in written:
            assert Path(path).exists()
        print(f"Streaming wrote {len(written)} chunk file(s):")
        for path in written:
            print(f"  {Path(path).name} ({Path(path).stat().st_size} bytes)")

    print("Streaming example completed.")


if __name__ == "__main__":
    main()
