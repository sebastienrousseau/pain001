# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The audit must run after automated publication, including container builds."""

from pathlib import Path

import pytest
import render_ecosystem_workflows as workflow_cli
import yaml
from ecosystem_audit import inventory, workflows

ROOT = Path(__file__).resolve().parents[1]


def test_core_audit_runs_on_its_own_schedule_and_on_demand() -> None:
    """No other workflow's completion can start it with this repository's trust.

    The core publishes first, so an audit after its own release fails
    until the companions ship; each companion audits after its own
    publication, and the core's runs daily or when dispatched.
    """
    workflow = yaml.load(
        (ROOT / ".github/workflows/suite-consistency.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    events = workflow["on"]
    assert set(events) == {"schedule", "workflow_dispatch"}
    assert set(events["workflow_dispatch"]["inputs"]) == {"version"}
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["consistency"]
    assert "if" not in job
    assert "workflow_run" not in str(job)
    action = [
        step
        for step in job["steps"]
        if "check-ecosystem" in step.get("uses", "")
    ]
    assert action[0]["with"]["version"] == "${{ inputs.version }}"


def test_readme_and_roadmap_list_all_nine_members() -> None:
    """The generated tables must include the extension and deployed website."""
    for name in ("README.md", "ROADMAP.md"):
        text = (ROOT / name).read_text()
        assert "https://github.com/sebastienrousseau/pain001-fast" in text
        assert "https://github.com/sebastienrousseau/pain001.github.io" in text
        assert "unreleased `0.0.1`" not in text


@pytest.mark.parametrize(
    "name", ["pain001-mcp", "pain001-lsp", "pain001.github.io"]
)
def test_companion_workflows_watch_every_publisher_and_deployment(
    name: str,
) -> None:
    """The last actual publication, not just GitHub release creation, rechecks the family."""
    members = {member.name: member for member in inventory()}
    rendered = workflows.render(members[name], "d" * 40)
    workflow = yaml.load(rendered, Loader=yaml.BaseLoader)
    assert workflow["on"]["workflow_run"]["workflows"] == list(
        members[name].publishers
    )
    assert workflow["permissions"] == {"contents": "read"}
    action = next(
        step["uses"]
        for step in workflow["jobs"]["consistency"]["steps"]
        if "/check-ecosystem@" in step.get("uses", "")
    )
    assert action.endswith("@" + "d" * 40)
    if name == "pain001.github.io":
        assert "head_branch == 'main'" in workflow["jobs"]["consistency"]["if"]
        assert (
            "workflow_run.name == 'CI'"
            in workflow["jobs"]["consistency"]["if"]
        )


@pytest.mark.parametrize("ref", ["main", "v0.0.84", "abc", "d" * 39])
def test_workflow_action_reference_must_be_immutable(ref: str) -> None:
    """A later push must not silently change a companion's auditor."""
    with pytest.raises(ValueError, match="commit"):
        workflows.render(inventory()[1], ref)


def test_workflow_generator_emits_all_eight_companion_files(
    tmp_path: Path,
) -> None:
    """One command prepares a complete, reviewable rollout from the inventory."""
    assert (
        workflow_cli.main(["--core-ref", "d" * 40, "--out", str(tmp_path)])
        == 0
    )
    paths = list(tmp_path.glob("*/.github/workflows/suite-consistency.yml"))
    assert len(paths) == 8
    assert {path.parents[2].name for path in paths} == {
        member.name for member in inventory()[1:]
    }


def test_generated_workflows_have_standalone_copyright() -> None:
    """Website source headers need copyright as well as a license."""
    for member in inventory()[1:]:
        source = workflows.render(member, "1" * 40)
        assert "# SPDX-FileCopyrightText: 2026 Sebastien Rousseau" in source
        assert "# SPDX-License-Identifier: Apache-2.0 OR MIT" in source
