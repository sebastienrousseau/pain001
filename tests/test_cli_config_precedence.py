# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Config files, environment and profiles reach streaming settings.

The CLI used to pass its own defaults (streaming False, chunk size 1000,
metrics off) as explicit values, so they overrode every config layer.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from pain001.cli.cli import cli
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

MTYPE = "pain.001.001.09"


@pytest.fixture
def workdir(tmp_path, monkeypatch) -> Path:
    """A working directory holding a sample CSV and no config file."""
    template = DEFAULT_TEMPLATE_REGISTRY.get_template(MTYPE).template_path
    shutil.copy(Path(template).parent / "template.csv", tmp_path / "p.csv")
    monkeypatch.chdir(tmp_path)
    for name in ("PAIN001_STREAMING", "PAIN001_CHUNK_SIZE"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def _show_config(*args: str, env: dict[str, str] | None = None) -> str:
    """Return the --show-config output for the sample CSV."""
    result = CliRunner().invoke(
        cli,
        ["-t", MTYPE, "-d", "p.csv", "--show-config", *args],
        env=env,
    )
    assert result.exit_code == 0, result.output
    return result.output


def test_config_file_sets_streaming_and_chunk_size(workdir):
    """Values from a config file are used when no flag is given."""
    (workdir / "c.yaml").write_text(
        "streaming: true\nchunk_size: 500\nemit_metrics: true\n",
        encoding="utf-8",
    )
    output = _show_config("--config", "c.yaml")
    assert "'streaming': True" in output
    assert "'chunk_size': 500" in output
    assert "'emit_metrics': True" in output


def test_environment_sets_streaming_and_chunk_size(workdir):
    """PAIN001_STREAMING and PAIN001_CHUNK_SIZE are honoured."""
    output = _show_config(
        env={"PAIN001_STREAMING": "true", "PAIN001_CHUNK_SIZE": "7"}
    )
    assert "'streaming': True" in output
    assert "'chunk_size': 7" in output


def test_flags_still_win_over_config(workdir):
    """An explicit flag overrides the config file."""
    (workdir / "c.yaml").write_text(
        "streaming: true\nchunk_size: 500\n", encoding="utf-8"
    )
    output = _show_config(
        "--config", "c.yaml", "--no-streaming", "--chunk-size", "9"
    )
    assert "'streaming': False" in output
    assert "'chunk_size': 9" in output


def test_defaults_without_any_config(workdir):
    """With nothing configured the documented defaults apply."""
    output = _show_config()
    assert "'streaming': False" in output
    assert "'chunk_size': 1000" in output
    assert "'emit_metrics': False" in output


@pytest.mark.parametrize(
    ("args", "files", "message"),
    [
        (["--profile", "no-such-profile"], {}, "Unknown profile"),
        (
            ["--config", "bad.yaml"],
            {"bad.yaml": "chunk_size: 0\n"},
            "chunk_size",
        ),
        (
            ["--config", "broken.yaml"],
            {"broken.yaml": "streaming: [true\n"},
            "broken.yaml",
        ),
    ],
    ids=["unknown-profile", "invalid-config", "malformed-yaml"],
)
def test_bad_configuration_is_a_usage_error(workdir, args, files, message):
    """An unknown profile or invalid config exits 2 without a traceback."""
    for name, text in files.items():
        (workdir / name).write_text(text, encoding="utf-8")
    result = CliRunner().invoke(
        cli, ["-t", MTYPE, "-d", "p.csv", "--show-config", *args]
    )
    assert result.exit_code == 2, result.output
    assert message in result.output
    assert not isinstance(result.exception, (KeyError, ValueError))
