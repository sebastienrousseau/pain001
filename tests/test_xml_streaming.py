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

"""Unit tests for constant-memory streaming XML chunk generator."""

from pathlib import Path
from typing import Any

import pytest

from pain001 import stream_xml_chunks, stream_xml_to_file
from pain001.observability import (
    clear_metrics_callbacks,
    register_metrics_callback,
)
from pain001.xml.generate_xml import generate_xml_string


@pytest.fixture
def sample_payment_data() -> list[dict[str, Any]]:
    """Return a minimal valid payment data record for pain.001.001.03."""
    return [
        {
            "id": "MSG001",
            "date": "2026-01-15T10:30:00",
            "initiator_name": "Acme Corp",
            "payment_information_id": "PMT001",
            "payment_method": "TRF",
            "batch_booking": "false",
            "service_level_code": "SEPA",
            "requested_execution_date": "2026-01-20",
            "debtor_name": "Acme Corp",
            "debtor_street_name": "Main Street",
            "debtor_building_number": "100",
            "debtor_postal_code": "10001",
            "debtor_town_name": "New York",
            "debtor_country_code": "US",
            "debtor_account_IBAN": "GB29NWBK60161331926819",
            "debtor_agent_BIC": "NWBKGB2L",
            "payment_id": "TX001",
            "end_to_end_id": "E2E001",
            "payment_currency": "EUR",
            "payment_amount": "100.50",
            "creditor_agent_BIC": "BNPAFRPP",
            "creditor_name": "Supplier Inc",
            "creditor_account_IBAN": "FR1420041010050500013M02606",
            "remittance_information": "Invoice 123",
        }
    ]


@pytest.fixture
def template_path() -> str:
    """Return path to pain.001.001.03 XML template."""
    return "pain001/templates/pain.001.001.03/template.xml"


@pytest.fixture
def xsd_path() -> str:
    """Return path to pain.001.001.03 XSD schema."""
    return "pain001/templates/pain.001.001.03/pain.001.001.03.xsd"


def test_stream_xml_chunks_exact_match(
    sample_payment_data: list[dict[str, Any]],
    template_path: str,
    xsd_path: str,
) -> None:
    """Verify stream_xml_chunks produces output byte-identical to generate_xml_string."""
    rendered = generate_xml_string(
        sample_payment_data,
        "pain.001.001.03",
        template_path,
        xsd_path,
    )

    for buffer_size in (10, 1, 0):
        chunks = list(
            stream_xml_chunks(
                sample_payment_data,
                "pain.001.001.03",
                template_path,
                buffer_size=buffer_size,
            )
        )
        assert len(chunks) > 0
        streamed = "".join(chunks)
        assert streamed == rendered


def test_stream_xml_to_file(
    sample_payment_data: list[dict[str, Any]],
    template_path: str,
    xsd_path: str,
    tmp_path: Path,
) -> None:
    """Verify stream_xml_to_file writes exact XML and returns canonical path."""
    rendered = generate_xml_string(
        sample_payment_data,
        "pain.001.001.03",
        template_path,
        xsd_path,
    )
    dest_path = tmp_path / "nested" / "output.xml"

    result_path = stream_xml_to_file(
        sample_payment_data,
        "pain.001.001.03",
        template_path,
        str(dest_path),
    )

    assert result_path == str(dest_path.resolve())
    assert dest_path.is_file()
    assert dest_path.read_text(encoding="utf-8") == rendered


def test_stream_xml_chunks_invalid_message_type(
    sample_payment_data: list[dict[str, Any]],
    template_path: str,
) -> None:
    """Verify ValueError is raised for an unsupported message type."""
    with pytest.raises(ValueError, match="Invalid XML message type"):
        list(
            stream_xml_chunks(
                sample_payment_data,
                "invalid.type",
                template_path,
            )
        )


def test_stream_xml_chunks_empty_data(
    template_path: str,
) -> None:
    """Verify ValueError is raised when data list is empty."""
    with pytest.raises(ValueError, match="data list is empty"):
        list(
            stream_xml_chunks(
                [],
                "pain.001.001.03",
                template_path,
            )
        )


def test_stream_xml_chunks_invalid_template(
    sample_payment_data: list[dict[str, Any]],
) -> None:
    """Verify ValueError is raised when template does not exist."""
    with pytest.raises(ValueError, match="Invalid template path"):
        list(
            stream_xml_chunks(
                sample_payment_data,
                "pain.001.001.03",
                "nonexistent/path/template.xml",
            )
        )


def test_stream_xml_metrics_emitted(
    sample_payment_data: list[dict[str, Any]],
    template_path: str,
    tmp_path: Path,
) -> None:
    """Verify observability metrics are emitted during streaming."""
    events: list[dict[str, Any]] = []

    def _callback(event: Any) -> None:
        events.append(
            {"name": event.name, "attributes": dict(event.attributes)}
        )

    register_metrics_callback(_callback)
    try:
        dest_file = tmp_path / "metric_test.xml"
        stream_xml_to_file(
            sample_payment_data,
            "pain.001.001.03",
            template_path,
            str(dest_file),
        )
        event_names = [e["name"] for e in events]
        assert "xml_prepared" in event_names
        assert "xml_stream_rendered" in event_names
        assert "xml_generated" in event_names

        gen_event = next(e for e in events if e["name"] == "xml_generated")
        assert gen_event["attributes"].get("streaming") is True
    finally:
        clear_metrics_callbacks()
