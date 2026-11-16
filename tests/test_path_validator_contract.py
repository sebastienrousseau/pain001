# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Pin the path validator's exact refusals and its /var/tmp base.

The broader suite only checked that a bad path is refused, with a
regex ``match=`` that a mutated message still satisfies, and never
proved that ``/var/tmp`` itself (rather than ``/var`` or a relative
``var/tmp``) is an allowed base. These tests compare messages with
``==`` and test the accepted and the refused side of each condition,
so the mutation run's survivors in ``_resolve_within_allowed_bases``
and ``validate_path`` are killed by a direct assertion.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from pain001.security import path_validator
from pain001.security.path_validator import (
    PathValidationError,
    SecurityError,
    _resolve_within_allowed_bases,
    validate_path,
)

_VAR_TMP = os.path.realpath(os.path.join(os.path.sep, "var", "tmp"))


@pytest.fixture
def jailed_cwd(tmp_path, monkeypatch):
    """Make the cwd and the temp directory one private folder."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        path_validator.tempfile, "gettempdir", lambda: str(tmp_path)
    )
    return tmp_path


def test_empty_path_message_is_exact():
    """An empty path is refused with the documented message."""
    with pytest.raises(PathValidationError) as caught:
        _resolve_within_allowed_bases("")
    assert str(caught.value) == "Path cannot be empty"


def test_traversal_message_is_exact():
    """A ``..`` component is refused with the documented message."""
    with pytest.raises(PathValidationError) as caught:
        _resolve_within_allowed_bases("a/../b")
    assert str(caught.value) == "Path contains invalid traversal sequences"


def test_path_without_traversal_is_accepted(jailed_cwd):
    """The same path without ``..`` resolves inside the cwd."""
    assert _resolve_within_allowed_bases("a/b") == os.path.join(
        os.path.realpath(str(jailed_cwd)), "a", "b"
    )


def test_realpath_failure_message_names_the_cause(monkeypatch):
    """An OS error while resolving becomes ``Invalid path: <cause>``."""
    cause = OSError("resolution failed")

    def failing_realpath(_path):
        raise cause

    monkeypatch.setattr(os.path, "realpath", failing_realpath)
    with pytest.raises(PathValidationError) as caught:
        _resolve_within_allowed_bases("a/b")
    monkeypatch.undo()
    assert str(caught.value) == "Invalid path: resolution failed"
    assert caught.value.__cause__ is cause


def test_var_tmp_is_an_allowed_base(jailed_cwd):
    """A file under /var/tmp passes when cwd and temp are elsewhere."""
    target = os.path.join(_VAR_TMP, "pain001-contract", "out.xml")
    assert _resolve_within_allowed_bases(target) == target


def test_var_tmp_itself_is_an_allowed_base(jailed_cwd):
    """/var/tmp itself (not only its children) is allowed."""
    assert _resolve_within_allowed_bases(_VAR_TMP) == _VAR_TMP


def test_var_outside_tmp_is_refused(jailed_cwd):
    """A sibling of /var/tmp under /var is not allowed."""
    var = os.path.realpath(os.path.join(os.path.sep, "var"))
    target = os.path.join(var, "pain001-not-tmp", "out.xml")
    with pytest.raises(SecurityError) as caught:
        _resolve_within_allowed_bases(target)
    assert str(caught.value) == (
        f"Path '{target}' is outside allowed directories."
    )


def test_prefix_sibling_of_var_tmp_is_refused(jailed_cwd):
    """``/var/tmpfoo`` shares a prefix with /var/tmp but is refused."""
    target = _VAR_TMP + "pain001"
    with pytest.raises(SecurityError) as caught:
        _resolve_within_allowed_bases(target)
    assert str(caught.value) == (
        f"Path '{target}' is outside allowed directories."
    )


def test_base_dir_escape_message_is_exact(tmp_path):
    """A path outside ``base_dir`` names both in the refusal."""
    base = tmp_path / "jail"
    base.mkdir()
    target = os.path.join(os.path.realpath(str(tmp_path)), "out.xml")
    with pytest.raises(SecurityError) as caught:
        _resolve_within_allowed_bases(target, base_dir=base)
    assert str(caught.value) == (
        f"Path '{target}' escapes base directory '{base}'."
    )


def test_base_dir_inside_is_accepted(tmp_path):
    """A path inside ``base_dir`` resolves to its real path."""
    target = os.path.join(os.path.realpath(str(tmp_path)), "out.xml")
    assert _resolve_within_allowed_bases(target, base_dir=tmp_path) == target


def test_untrusted_traversal_is_refused_before_any_resolution(monkeypatch):
    """With nothing trusted, a ``..`` path never reaches ``realpath``.

    Resolving follows symlinks on the filesystem; an attacker's path
    must be refused on its text before anything is touched.
    """
    calls: list[str] = []
    real = os.path.realpath

    def spy(path, *args, **kwargs):
        calls.append(str(path))
        return real(path, *args, **kwargs)

    monkeypatch.setattr(os.path, "realpath", spy)
    with pytest.raises(PathValidationError) as caught:
        validate_path("../etc/passwd")
    monkeypatch.undo()
    assert str(caught.value) == "Path contains invalid traversal sequences"
    assert calls == []


def test_trusted_file_outside_the_jail_is_accepted(tmp_path):
    """A file named by the command line passes from outside the jail."""
    outside = os.path.join(tempfile.gettempdir(), "..", "x")
    resolved = os.path.realpath(outside)
    with path_validator.trusted_paths(outside):
        assert validate_path(outside) == resolved


def test_missing_file_message_is_exact(jailed_cwd):
    """``must_exist`` refuses a missing file with its resolved path."""
    expected = os.path.join(os.path.realpath(str(jailed_cwd)), "absent.csv")
    with pytest.raises(FileNotFoundError) as caught:
        validate_path("absent.csv", must_exist=True)
    assert str(caught.value) == f"Path does not exist: {expected}"


def test_existing_file_passes_must_exist(jailed_cwd):
    """``must_exist`` accepts a file that is there."""
    (jailed_cwd / "present.csv").write_text("x", encoding="utf-8")
    expected = os.path.join(os.path.realpath(str(jailed_cwd)), "present.csv")
    assert validate_path("present.csv", must_exist=True) == expected
