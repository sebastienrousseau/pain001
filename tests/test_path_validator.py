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

"""Unit tests for the path_validator module."""

import os
import tempfile
from pathlib import Path

import pytest

from pain001.security.path_validator import (
    PathValidationError,
    SecurityError,
    _is_allowed_directory,
    sanitize_for_log,
    validate_path,
)


class TestPathValidator:
    """Test cases for path validation and sanitization."""

    def test_validate_path_valid_cwd(self):
        """Test validation of a file in the current working directory."""
        cwd_file = Path("pain001/test_fixtures/test_file_cwd.txt")
        cwd_file.parent.mkdir(parents=True, exist_ok=True)
        cwd_file.touch()
        try:
            resolved = validate_path(cwd_file)
            # validate_path now returns string for CodeQL taint tracking
            assert resolved == str(cwd_file.resolve())
            assert isinstance(resolved, str)
        finally:
            if cwd_file.exists():
                cwd_file.unlink()

    def test_validate_path_valid_temp(self):
        """Test validation of a file in the temporary directory."""
        with tempfile.NamedTemporaryFile() as tmp:
            path = Path(tmp.name)
            resolved = validate_path(path)
            # validate_path now returns string for CodeQL taint tracking
            assert resolved == str(path.resolve())
            assert isinstance(resolved, str)

    def test_validate_path_traversal(self):
        """Test detection of path traversal attempts."""
        # Simple string check - now handled by resolve() + boundary check
        # If it resolves to outside, it raises SecurityError
        # ../outside.txt likely resolves to outside current dir
        with pytest.raises((PathValidationError, SecurityError)):
            validate_path("../outside.txt")

    def test_validate_path_empty(self):
        """Test validation of empty path."""
        with pytest.raises(PathValidationError, match="Path cannot be empty"):
            validate_path("")

    def test_validate_path_must_exist(self):
        """Test the must_exist parameter."""
        # Create a unique non-existent filename
        path = Path(
            "pain001/test_fixtures/non_existent_file_path_validator_test.txt"
        )
        if path.exists():
            path.unlink()

        # Should pass if must_exist=False (returns string)
        result = validate_path(path, must_exist=False)
        assert result == str(path.resolve())
        assert isinstance(result, str)

        # Should fail if must_exist=True
        with pytest.raises(FileNotFoundError):
            validate_path(path, must_exist=True)

    def test_validate_path_outside_allowed(self):
        """Test validation of existing system files outside allowed directories."""
        # /dev/null is a good candidate for a file that exists but is likely not in CWD or TMP
        target = Path("/dev/null")
        if target.exists():
            # Ensure it's not accidentally in allowed dirs (unlikely)
            if not any(
                str(target).startswith(d)
                for d in [tempfile.gettempdir(), os.getcwd(), "/var/tmp"]
            ):
                with pytest.raises(
                    SecurityError, match="outside allowed directories"
                ):
                    validate_path(target)

    def test_is_allowed_directory_logic(self):
        """Test internal logic of _is_allowed_directory directly."""
        # Non-existent files MUST be in allowed directories to be valid
        assert (
            _is_allowed_directory(Path("/non/existent/absolute/path")) is False
        )

    def test_sanitize_for_log(self):
        """Test string sanitization for logging."""
        assert sanitize_for_log("NormalString") == "NormalString"
        assert sanitize_for_log("Line\nBreak") == "LineBreak"
        assert sanitize_for_log("Tab\tCharacter") == "TabCharacter"
        assert sanitize_for_log(None) == ""
        assert sanitize_for_log("") == ""

        # Test truncation
        long_str = "a" * 20
        sanitized = sanitize_for_log(long_str, max_length=10)
        assert sanitized == "aaaaaaaaaa..."
        assert len(sanitized) == 13

    def test_validate_path_symlink_loop(self):
        """Test validation of a path with a symlink loop.

        os.path.realpath() resolves symlink loops without raising,
        so the path simply won't exist when must_exist=True.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            loop_path = Path(tmp_dir) / "loop"
            try:
                # Create a self-referencing symlink
                os.symlink(loop_path, loop_path)

                # With must_exist=True, realpath resolves the loop
                # but the resulting path won't exist on disk.
                with pytest.raises(FileNotFoundError):
                    validate_path(loop_path, must_exist=True)

            except OSError:
                pytest.skip("Symlinks not supported or permission denied")
