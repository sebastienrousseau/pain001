# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""``pain001 face``: project a pain.001 file into a face (ADR-0005)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from pain001.faces.engine import available_faces, project_face
from pain001.faces.models import FaceError, LossReport


def _load_bindings(path: Path | None) -> dict[str, Any] | None:
    """Read a private bindings file: a JSON object, or nothing."""
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"Error loading bindings: {exc}") from exc
    if not isinstance(data, dict):
        raise click.ClickException(
            "Error loading bindings: expected a JSON object"
        )
    return data


def _echo_loss_report(report: LossReport) -> None:
    """Summarise a loss report on standard error."""
    click.echo("Face Loss Report:", err=True)
    click.echo(
        f"  mapped {len(report.mapped_paths)} of {report.total_source_elements} "
        f"source elements ({report.loss_ratio:.1%} not carried)",
        err=True,
    )
    for path in report.unmapped_paths:
        click.echo(f"  - {path}", err=True)


@click.command("face")
@click.argument(
    "source", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    "--face",
    "face_name",
    type=click.Choice(available_faces()),
    default="uk_open_banking",
    show_default=True,
    help="Target standard.",
)
@click.option(
    "--bindings",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Private side inputs (JSON object); keep this file out of version control.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write the payload here instead of standard output.",
)
@click.option(
    "--loss-report", is_flag=True, help="List the source elements not carried."
)
def face_cmd(
    source: Path,
    face_name: str,
    bindings: Path | None,
    output: Path | None,
    loss_report: bool,
) -> None:
    """Project a pain.001 XML file into an external standard's JSON shape.

    Faces are outbound only: UK Open Banking v4.0.1, Berlin Group
    NextGenPSD2 v1.3.16, or ISO 20022 element names in snake_case.
    \f
    Args:
        source: The pain.001 XML file.
        face_name: The target face.
        bindings: Optional private bindings file.
        output: Optional output file for the payload.
        loss_report: Print the loss report to standard error.

    Raises:
        click.ClickException: When the bindings cannot be read or the face
            refuses the document.
    """
    side_inputs = _load_bindings(bindings)
    try:
        result = project_face(source, face_name, bindings=side_inputs)
    except FaceError as exc:
        raise click.ClickException(f"Face projection error: {exc}") from exc
    if output is None:
        click.echo(result.to_json())
    else:
        output.write_text(result.to_json() + "\n", encoding="utf-8")
        click.echo(f"Wrote {face_name} face to {output}", err=True)
    if loss_report:
        _echo_loss_report(result.loss_report)
