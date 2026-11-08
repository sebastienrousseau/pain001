# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

from pathlib import Path

from pain001.core.core import process_files_streaming


def test_process_files_streaming_generates_multiple_xml_outputs(
    tmp_path: Path,
) -> None:
    template = Path("pain001/templates/pain.001.001.03/template.xml").resolve()
    schema = Path(
        "pain001/templates/pain.001.001.03/pain.001.001.03.xsd"
    ).resolve()
    # Two rows of the bundled sample: the CSV contract process_files
    # applies (the streamed chunks are validated the same way).
    sample = Path("pain001/templates/pain.001.001.03/template.csv")
    lines = sample.read_text(encoding="utf-8").splitlines()
    data = tmp_path / "payments.csv"
    data.write_text("\n".join(lines[:3]) + "\n", encoding="utf-8")

    outputs = process_files_streaming(
        "pain.001.001.03",
        str(template),
        str(schema),
        str(data),
        chunk_size=1,
    )

    assert len(outputs) == 2
    assert all(Path(path).exists() for path in outputs)
    # each file is its own message, so the two MsgIds differ
    msg_ids = {
        Path(path)
        .read_text(encoding="utf-8")
        .split("<MsgId>")[1]
        .split("</MsgId>")[0]
        for path in outputs
    }
    assert len(msg_ids) == 2
