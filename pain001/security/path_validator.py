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

"""Path validation and sanitization to prevent security vulnerabilities."""

import os
import re
import tempfile
from pathlib import Path
from typing import Union

from pain001.constants import BASE_DIR


class PathValidationError(ValueError):
    """Raised when path validation fails."""


class SecurityError(PermissionError):
    """Raised when a security boundary is violated."""


def _is_allowed_directory(resolved_path: Path) -> bool:
    """Check if the path is within allowed directories.

    Args:
        resolved_path: The absolute Path object to check.

    Returns:
        True if the path is within allowed directories, False otherwise.
    """
    try:
        # Define base allowed directories
        allowed_bases = [
            Path.cwd().resolve(),
            Path(tempfile.gettempdir()).resolve(),
            Path(os.path.join(os.path.sep, "var", "tmp")).resolve(),
        ]

        # Use efficient pathlib ancestry check (Python 3.9+)
        return any(
            resolved_path == base or resolved_path.is_relative_to(base)
            for base in allowed_bases
        )

    except Exception:  # nosec B110
        return False


def validate_path(
    untrusted_path: Union[str, Path], must_exist: bool = False
) -> str:
    """Validate and resolve path to prevent directory traversal attacks.

    Args:
        untrusted_path: User-provided path (potentially malicious).
        must_exist: If True, raise error if path doesn't exist.

    Returns:
        Resolved absolute path as string (CodeQL taint-tracking compliant).

    Raises:
        PathValidationError: If path contains traversal attempts.
        FileNotFoundError: If must_exist=True and path doesn't exist.
    """
    if not untrusted_path:
        raise PathValidationError("Path cannot be empty")

    try:
        base = os.path.abspath(BASE_DIR)
        requested = os.path.abspath(untrusted_path)
    except (RuntimeError, OSError) as e:
        raise PathValidationError(f"Invalid path: {e}") from e

    # Reject paths with obvious traversal attempts (redundant with resolve() but good depth defense)
    if ".." in str(untrusted_path):
        raise PathValidationError("Invalid path: directory traversal detected")

    # Strict Boundary Check (CWE-22)
    if not requested.startswith(base):
        raise PermissionError("Security: Path traversal")

    # Check existence if required (CodeQL: return string for taint tracking)
    if must_exist and not Path(requested).exists():
        raise FileNotFoundError(f"Path does not exist: {requested}")

    return requested


def sanitize_for_log(user_input: str, max_length: int = 100) -> str:
    """Sanitize user input for safe logging (prevent log injection).

    Args:
        user_input: User-provided string (potentially malicious).
        max_length: Maximum length to include in log.

    Returns:
        Sanitized string safe for logging.
    """
    if not user_input:
        return ""

    # Remove newlines, carriage returns, and other control characters
    sanitized = re.sub(r"[\r\n\t\x00-\x1f\x7f-\x9f]", "", user_input)

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."

    return sanitized
