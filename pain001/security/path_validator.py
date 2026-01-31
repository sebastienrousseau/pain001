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

        resolved_str = str(resolved_path)
        return any(
            resolved_str == str(base)
            or resolved_str.startswith(str(base) + os.sep)
            for base in allowed_bases
        )

    except Exception:  # nosec B110
        return False


def _resolve_within_allowed_bases(
    untrusted_path: Union[str, Path],
    base_dir: Union[str, Path, None] = None,
) -> str:
    """Resolve and validate that a path is within allowed directories.

    This is the core validation logic, separated so that its return value
    is marked as taint-free by the CodeQL neutralModel extension.  The
    ``validate_path`` wrapper adds the optional existence check on the
    *already-clean* return value, keeping ``os.path.exists`` outside the
    tainted data-flow graph.

    Returns:
        Resolved absolute path string proven to be within allowed bases.

    Raises:
        PathValidationError: If path is empty or contains traversal.
        SecurityError: If path escapes all allowed directories.
    """
    if not untrusted_path:
        raise PathValidationError("Path cannot be empty")

    path_str = str(untrusted_path)

    if ".." in path_str:
        raise PathValidationError("Path contains invalid traversal sequences")

    normalized_str = os.path.normpath(path_str)

    try:
        resolved_str = os.path.realpath(normalized_str)
    except (RuntimeError, OSError) as e:
        raise PathValidationError(f"Invalid path: {e}") from e

    if base_dir is not None:
        base_str = os.path.realpath(str(base_dir))
        allowed_bases = [base_str]
    else:
        allowed_bases = [
            os.path.realpath(os.getcwd()),
            os.path.realpath(tempfile.gettempdir()),
            os.path.realpath(os.path.join(os.path.sep, "var", "tmp")),
        ]

    for base in allowed_bases:
        if resolved_str == base or resolved_str.startswith(base + os.sep):
            return base + resolved_str[len(base) :]

    if base_dir:
        raise SecurityError(
            f"Path '{resolved_str}' escapes base directory '{base_dir}'."
        )
    raise SecurityError(
        f"Path '{resolved_str}' is outside allowed directories."
    )


def validate_path(
    untrusted_path: Union[str, Path],
    must_exist: bool = False,
    base_dir: Union[str, Path, None] = None,
) -> str:
    """Validate and resolve path to prevent directory traversal attacks.

    Args:
        untrusted_path: User-provided path (potentially malicious).
        must_exist: If True, raise error if path doesn't exist.
        base_dir: Optional base directory to constrain resolution.

    Returns:
        Resolved absolute path as string (CodeQL taint-tracking compliant).

    Raises:
        PathValidationError: If path contains traversal attempts.
        SecurityError: If path escapes allowed directories.
        FileNotFoundError: If must_exist=True and path doesn't exist.
    """
    # Core validation — return value is taint-free per neutralModel.
    safe_path = _resolve_within_allowed_bases(untrusted_path, base_dir)

    if must_exist and not os.path.exists(safe_path):
        raise FileNotFoundError(f"Path does not exist: {safe_path}")

    return safe_path


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
