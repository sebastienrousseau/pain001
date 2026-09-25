# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Regenerate API pages from importable packages, not XML data directories."""

import ast
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from sphinx.ext.apidoc import main

ROOT = Path(__file__).resolve().parents[1]


def generate() -> None:
    """Replace generated API pages, removing obsolete generated module pages."""
    with TemporaryDirectory(prefix="pain001-api-docs-") as directory:
        output = Path(directory)
        main(
            [
                "--force",
                "--module-first",
                "-o",
                str(output),
                str(ROOT / "pain001"),
                str(ROOT / "pain001/templates/pain.*"),
            ]
        )
        docs = ROOT / "docs"
        for old in docs.glob("pain001*.rst"):
            if not (output / old.name).exists():
                old.unlink()
        for page in output.glob("*.rst"):
            content = page.read_text()

            def package_members(match: re.Match[str]) -> str:
                """Index package-defined objects, not imported aliases twice."""
                module = match[1]
                source = ROOT / module.replace(".", "/") / "__init__.py"
                if not source.exists():
                    return match[0]
                names = [
                    node.name
                    for node in ast.parse(source.read_text()).body
                    if isinstance(
                        node,
                        (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
                    )
                    and not node.name.startswith("_")
                ]
                directive = f".. automodule:: {module}\n"
                if names:
                    directive += "   :members: " + ", ".join(names) + "\n"
                return directive

            content = re.sub(
                r"\.\. automodule:: ([\w.]+)\n(?:   :[^\n]+\n)+",
                package_members,
                content,
            )
            (docs / page.name).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    generate()
