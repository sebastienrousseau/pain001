# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Private registration seam: built-ins never import the concrete registry."""

from typing import Protocol

from pain001.plugins.contracts import (
    AbstractLoader,
    AbstractScheme,
    AbstractWriter,
)


class BuiltinRegistry(Protocol):
    """The existing registry operations needed to compose built-in plugins."""

    def register_loader(self, loader: AbstractLoader) -> None:
        """Register a built-in loader."""

    def register_scheme(self, scheme: AbstractScheme) -> None:
        """Register a built-in scheme."""

    def register_writer(self, writer: AbstractWriter) -> None:
        """Register a built-in writer."""

    def get_loader_for_extension(
        self, extension: str
    ) -> AbstractLoader | None:
        """Resolve an inner loader in the owning registry."""
