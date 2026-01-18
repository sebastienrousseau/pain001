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
    _is_allowed_directory,
    sanitize_for_log,
    validate_path,
)


class TestPathValidator:
    """Test cases for path validation and sanitization."""

    def test_validate_path_valid_cwd(self):
        """Test validation of a file in the current working directory."""
        cwd_file = Path("test_file_cwd.txt")
        cwd_file.touch()
        try:
            resolved = validate_path(cwd_file)
            assert resolved == cwd_file.resolve()
        finally:
            if cwd_file.exists():
                cwd_file.unlink()

    def test_validate_path_valid_temp(self):
        """Test validation of a file in the temporary directory."""
        with tempfile.NamedTemporaryFile() as tmp:
            path = Path(tmp.name)
            resolved = validate_path(path)
            assert resolved == path.resolve()

    def test_validate_path_traversal(self):
        """Test detection of path traversal attempts."""
        # Simple string check
        with pytest.raises(PathValidationError, match="traversal detected"):
            validate_path("../outside.txt")

    def test_validate_path_empty(self):
        """Test validation of empty path."""
        with pytest.raises(PathValidationError, match="Path cannot be empty"):
            validate_path("")

    def test_validate_path_must_exist(self):
        """Test the must_exist parameter."""
        # Create a unique non-existent filename
        path = Path("non_existent_file_path_validator_test.txt")
        if path.exists():
            path.unlink()

        # Should pass if must_exist=False
        assert validate_path(path, must_exist=False) == path.resolve()

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
                    PathValidationError, match="outside allowed directories"
                ):
                    validate_path(target)

    def test_is_allowed_directory_logic(self):
        """Test internal logic of _is_allowed_directory directly."""
        # Non-existent files are allowed (assuming they will be created safely or fail later)
        assert (
            _is_allowed_directory(Path("/non/existent/absolute/path")) is True
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
        """Test validation of a path with a symlink loop (RuntimeError)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            loop_path = Path(tmp_dir) / "loop"
            try:
                # Create a self-referencing symlink
                os.symlink(loop_path, loop_path)
                with pytest.raises(PathValidationError, match="Invalid path"):
                    validate_path(loop_path)
            except OSError:
                pytest.skip("Symlinks not supported or permission denied")

    def test_coverage_legacy_python(self):
        """Force execution of Python < 3.9 fallback logic (missing is_relative_to)."""
        # pylint: disable=import-outside-toplevel
        from unittest.mock import patch

        # Create a Mock object that behaves like a Path but lacks is_relative_to
        class LegacyPath:
            """Mock path class to simulate Python < 3.9 behavior."""

            def __init__(self, path_str):
                self.path_str = str(path_str)

            def __str__(self):
                return self.path_str

            def exists(self):
                return True

            def startswith(self, other):
                return self.path_str.startswith(other)

        # Define paths
        dummy_base = "/dummy/base"
        real_base_path = Path("/real/base")
        target_path_str = str(real_base_path / "valid_file.txt")

        target = LegacyPath(target_path_str)

        # We need to ensure the INITIAL string check in _is_allowed_directory fails
        # The initial check allows: temp_dir, var_tmp, os.getcwd()
        # We mock these to be unrelated to our target

        with patch("os.getcwd", return_value=dummy_base), patch(
            "tempfile.gettempdir", return_value="/dummy/temp"
        ), patch("pathlib.Path.cwd", return_value=real_base_path):
            # Now, _is_allowed_directory will:
            # 1. Check if target starts with dummy_base, /dummy/temp, or var/tmp. (False)
            # 2. Check if target exists (True)
            # 3. Iterate bases. One base is Path.cwd() which is mocked to real_base_path.
            # 4. Check hasattr(target, "is_relative_to") -> False (LegacyPath doesn't have it)
            # 5. Fallback: str(target).startswith(str(real_base_path)) -> True

            assert _is_allowed_directory(target) is True
