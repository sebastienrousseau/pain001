# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Measure cold discovery with ten synthetic installed entry-point plugins.

Run with the development interpreter. Fixtures are generated in a temporary
site directory, never installed into the user's environment. Report timings,
not a hardware-independent performance threshold or external-author review.
"""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    """Generate ten distribution fixtures and time fresh interpreter discovery."""
    with TemporaryDirectory(prefix="pain001-discovery-") as directory:
        site = Path(directory)
        for index in range(10):
            name = f"synthetic_loader_{index}"
            (site / f"{name}.py").write_text(
                "from pain001.plugins import PluginMeta, LoaderResult\n"
                "class Loader:\n"
                f"    meta = PluginMeta(name='{name}', version='0.0.1', "
                "description='Synthetic benchmark', api_version=(0, 54))\n"
                f"    extensions = ('.synthetic{index}',)\n"
                "    def load(self, path):\n"
                "        return LoaderResult(rows=[], source_hint=path)\n"
                "    def load_streaming(self, path, chunk_size):\n"
                "        yield self.load(path)\n",
                encoding="utf-8",
            )
            dist = site / f"{name}-0.0.1.dist-info"
            dist.mkdir()
            (dist / "METADATA").write_text(
                f"Metadata-Version: 2.1\nName: {name}\nVersion: 0.0.1\n",
                encoding="utf-8",
            )
            (dist / "entry_points.txt").write_text(
                f"[pain001.loaders]\n{name} = {name}:Loader\n",
                encoding="utf-8",
            )
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(site), environment.get("PYTHONPATH", "")]
        )
        script = "\n".join(
            [
                "import json, time",
                "started = time.perf_counter()",
                "from pain001.plugins import registry",
                "plugins = registry.list_plugins('loader')",
                "elapsed = time.perf_counter() - started",
                "count = sum(p.meta.name.startswith('synthetic_loader_') for p in plugins)",
                "assert count == 10, count",
                "print(json.dumps({'plugins': count, 'seconds': elapsed}))",
            ]
        )
        samples = []
        for _ in range(3):
            result = subprocess.run(
                [sys.executable, "-c", script],
                env=environment,
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            samples.append(json.loads(result.stdout))
        print(
            json.dumps(
                {
                    "python": platform.python_version(),
                    "platform": platform.platform(),
                    "samples": samples,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
