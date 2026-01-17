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


def _is_allowed_directory(resolved_path: Path) -> bool:
    """Check if the path is within allowed directories.

    Args:
        resolved_path: The absolute Path object to check.

    Returns:
        True if the path is valid and within allowed directories, False otherwise.
    """
    path_str_resolved = str(resolved_path)
    temp_dir = tempfile.gettempdir()
    var_tmp = os.path.join(os.path.sep, "var", "tmp")
    allowed_dirs = [temp_dir, var_tmp, os.getcwd()]

    if not path_str_resolved.startswith(os.path.sep) or any(
        path_str_resolved.startswith(str(p)) for p in allowed_dirs
    ):
        return True

    if not resolved_path.exists():
        return True

    try:
        cwd = Path.cwd()
        # Check safely against all allowed bases
        for base in [cwd, Path(temp_dir), Path(var_tmp)]:
            if resolved_path.is_relative_to(base):
                return True
    except AttributeError:
        # Should not happen in Python 3.9+, but handled for safety
        if str(resolved_path).startswith(str(Path.cwd())):
            return True
    except Exception:  # nosec B110, B112
        pass

    return False


def validate_path(
    user_path: Union[str, Path], must_exist: bool = False
) -> Path:
    """Validate and resolve path to prevent directory traversal attacks.

    Args:
        user_path: User-provided path (potentially malicious).
        must_exist: If True, raise error if path doesn't exist.

    Returns:
        Resolved absolute Path object.

    Raises:
        PathValidationError: If path contains traversal attempts.
        FileNotFoundError: If must_exist=True and path doesn't exist.
    """
    if not user_path:
        raise PathValidationError("Path cannot be empty")

    # Convert to string if Path object
    path_str = str(user_path)

    # Reject paths with obvious traversal attempts
    if ".." in path_str:
        raise PathValidationError("Invalid path: directory traversal detected")

    # Resolve to absolute path (safe after traversal check)
    try:
        resolved = Path(path_str).resolve()  # nosec B108
    except (OSError, RuntimeError) as e:
        raise PathValidationError(f"Invalid path: {e}") from e

    # Check existence if required
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"Path does not exist: {resolved}")

    # Additional allowlist check for absolute paths (after existence check)
    # This prevents actual access to files outside expected areas
    if not _is_allowed_directory(resolved):
        raise PathValidationError(
            f"Path validation failed: Absolute path outside allowed directories: {resolved}"
        ) from None

    return resolved


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
