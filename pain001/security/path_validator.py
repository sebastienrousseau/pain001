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


def validate_path(
    untrusted_path: Union[str, Path],
    must_exist: bool = False,
    base_dir: Union[str, Path, None] = None,
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

    # Work with a string representation for initial validation/normalization
    path_str = str(untrusted_path)

    # Quick traversal guard before constructing Path object
    if ".." in path_str:
        raise PathValidationError("Path contains invalid traversal sequences")

    # Normalize the path string to collapse any redundant separators/components
    normalized_str = os.path.normpath(path_str)

    try:
        # Convert to Path object and resolve absolute path
        # resolve() handles symlinks and removes '..' components (CWE-22 mitigation)
        resolved_path = Path(normalized_str).resolve()
    except (RuntimeError, OSError) as e:
        raise PathValidationError(f"Invalid path: {e}") from e

    # Determine allowed bases
    if base_dir is not None:
        base_resolved = Path(base_dir).resolve()
        allowed_bases = [base_resolved]
    else:
        # Default allowed bases
        allowed_bases = [
            Path.cwd().resolve(),
            Path(tempfile.gettempdir()).resolve(),
            Path(os.path.join(os.path.sep, "var", "tmp")).resolve(),
        ]

    # Strict boundary check: resolved path must be within at least one
    # allowed base.  The str.startswith() guard is a pattern that static
    # analysis tools (including CodeQL) recognise as a path-injection
    # sanitiser barrier (CWE-22).
    resolved_str = str(resolved_path)
    for base in allowed_bases:
        base_str = str(base)
        if resolved_str == base_str or resolved_str.startswith(
            base_str + os.sep
        ):
            # Path is within this allowed base — safe to use.
            if must_exist and not resolved_path.exists():
                raise FileNotFoundError(
                    f"Path does not exist: {resolved_path}"
                )
            return resolved_str

    if base_dir:
        raise SecurityError(
            f"Path '{resolved_path}' escapes base directory '{base_dir}'."
        )
    raise SecurityError(
        f"Path '{resolved_path}' is outside allowed directories."
    )


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
