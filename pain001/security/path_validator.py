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

import re
from pathlib import Path
from typing import Union


class PathValidationError(ValueError):
    """Raised when path validation fails."""

    pass


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

    # Resolve to absolute path
    try:
        resolved = Path(path_str).resolve()
    except (OSError, RuntimeError) as e:
        raise PathValidationError(f"Invalid path: {e}") from e

    # Check existence if required
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"Path does not exist: {resolved}")

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
