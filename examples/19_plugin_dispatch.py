# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Register a synthetic loader and exercise actual eager/streaming dispatch.

Registration is process-local. Packaging entry points is covered by the
companion plugin template; this example neither installs nor removes plugins.
"""

from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

from pain001.constants import TEMPLATES_DIR
from pain001.csv.load_csv_data import load_csv_data
from pain001.data.loader import load_payment_data, load_payment_data_streaming
from pain001.plugins import (
    PAIN001_API_VERSION,
    LoaderResult,
    PluginMeta,
    registry,
)


class SyntheticLoader:
    """Treat an example-only extension as a CSV of synthetic payment rows."""

    meta = PluginMeta(
        "example-loader",
        "0.0.1",
        "Synthetic CSV",
        api_version=PAIN001_API_VERSION,
    )
    extensions = (".example-payments",)

    def load(self, source: str) -> LoaderResult:
        """Read the same validated fixture used by the built-in CSV loader."""
        return LoaderResult(rows=load_csv_data(source))

    def load_streaming(
        self, source: str, chunk_size: int
    ) -> Iterator[LoaderResult]:
        """Yield bounded batches with the same order and content."""
        rows = self.load(source).rows
        for offset in range(0, len(rows), chunk_size):
            yield LoaderResult(rows=rows[offset : offset + chunk_size])


def main() -> None:
    """Verify that registration changes execution, not just discovery."""
    registry.list_plugins()
    registry.register_loader(SyntheticLoader())
    fixture = TEMPLATES_DIR / "pain.001.001.03" / "template.csv"
    with TemporaryDirectory(dir=".") as directory:
        source = Path(directory) / "payments.example-payments"
        source.write_bytes(fixture.read_bytes())
        eager = load_payment_data(str(source))
        batches = list(load_payment_data_streaming(str(source), chunk_size=1))
        assert eager == load_csv_data(str(fixture))
        assert batches and all(len(batch) == 1 for batch in batches)
        assert [row for batch in batches for row in batch] == eager
    print("Registered loader: eager and streaming dispatch preserve all rows")


if __name__ == "__main__":
    main()
