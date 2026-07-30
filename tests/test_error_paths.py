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

"""Edge-case and error-path tests for core, CLI, and XSD validation."""

import os
import tempfile

import pytest

from pain001.context.context import Context
from pain001.core.core import process_files
from pain001.xml.generate_xml import generate_xml


class TestErrorPaths:
    """Behavioural tests for error handling and edge cases."""

    def test_context_logger_with_existing_handlers(self) -> None:
        """Test context logger when handlers already exist."""
        # Create a fresh context instance for testing
        import logging

        # Reset the singleton for this test
        Context._instance = None
        ctx = Context.get_instance()

        # Manually set up logger with handler to test the branch
        ctx.logger = logging.getLogger("test_pain001")
        handler = logging.StreamHandler()
        ctx.logger.addHandler(handler)

        # Try to initialize - should raise exception because logger exists
        with pytest.raises(
            Exception, match="Logger has already been initialized"
        ):
            ctx.init_logger()

    def test_process_files_with_failed_xml_generation(self) -> None:
        """Test process_files when XML file generation fails."""
        # Create temporary files
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv"
        ) as csv_file:
            csv_file.write(
                "id,date,nb_of_txs,initiator_name,payment_id,payment_method\n"
            )
            csv_file.write(
                "MSG001,2026-01-09T10:00:00,1,Test Corp,PMT001,TRF\n"
            )
            csv_path = csv_file.name

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xsd"
        ) as xsd_file:
            xsd_file.write(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
                "</xs:schema>"
            )
            xsd_path = xsd_file.name

        # Create a path that will cause generation to fail
        # (non-writable directory)
        nonexistent_xml_path = "/nonexistent/path/template.xml"

        try:
            with pytest.raises((FileNotFoundError, OSError)):
                process_files(
                    "pain.001.001.03",
                    nonexistent_xml_path,
                    xsd_path,
                    csv_path,
                )
        finally:
            # Clean up
            if os.path.exists(csv_path):
                os.remove(csv_path)
            if os.path.exists(xsd_path):
                os.remove(xsd_path)

    def test_generate_xml_with_empty_data(self) -> None:
        """Test generate_xml with empty data list."""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xml"
        ) as xml_file:
            xml_path = xml_file.name

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xsd"
        ) as xsd_file:
            xsd_file.write(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
                "</xs:schema>"
            )
            xsd_path = xsd_file.name

        try:
            # Test with empty data
            with pytest.raises(ValueError):
                generate_xml(
                    [],
                    "pain.001.001.03",
                    xml_path,
                    xsd_path,
                )
        finally:
            if os.path.exists(xml_path):
                os.remove(xml_path)
            if os.path.exists(xsd_path):
                os.remove(xsd_path)

    def test_validate_via_xsd_with_validation_error(self) -> None:
        """Test validate_via_xsd with schema validation error."""
        from pain001.xml.validate_via_xsd import validate_via_xsd

        # Create an XML file that doesn't match schema
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xml"
        ) as xml_file:
            xml_file.write('<?xml version="1.0"?><wrong>data</wrong>')
            xml_path = xml_file.name

        # Create a strict XSD schema
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xsd"
        ) as xsd_file:
            xsd_file.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
    <xs:element name="root">
        <xs:complexType>
            <xs:sequence>
                <xs:element name="child" type="xs:string"/>
            </xs:sequence>
        </xs:complexType>
    </xs:element>
</xs:schema>"""
            )
            xsd_path = xsd_file.name

        try:
            # This should return False due to validation failure
            result = validate_via_xsd(xml_path, xsd_path)
            assert result is False
        finally:
            if os.path.exists(xml_path):
                os.remove(xml_path)
            if os.path.exists(xsd_path):
                os.remove(xsd_path)

    def test_main_with_general_exception(self) -> None:
        """Test main function with general exception handling."""
        from pain001.__main__ import main

        # Pass invalid arguments that will cause an exception
        with pytest.raises(SystemExit):
            main(
                "invalid_type",
                "/nonexistent/template.xml",
                "/nonexistent/schema.xsd",
                "/nonexistent/data.csv",
            )

    def test_main_missing_xsd_template(self) -> None:
        """Test main function with missing XSD template file."""
        from pain001.__main__ import main

        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv"
        ) as csv_file:
            csv_file.write("id,date\n")
            csv_path = csv_file.name

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xml"
        ) as xml_file:
            xml_path = xml_file.name

        try:
            with pytest.raises(SystemExit):
                main(
                    "pain.001.001.03",
                    xml_path,
                    None,  # Missing XSD
                    csv_path,
                )
        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)
            if os.path.exists(xml_path):
                os.remove(xml_path)

    def test_main_missing_data_file(self) -> None:
        """Test main function with missing data file."""
        from pain001.__main__ import main

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xml"
        ) as xml_file:
            xml_path = xml_file.name

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xsd"
        ) as xsd_file:
            xsd_path = xsd_file.name

        try:
            with pytest.raises(SystemExit):
                main(
                    "pain.001.001.03",
                    xml_path,
                    xsd_path,
                    None,  # Missing data file
                )
        finally:
            if os.path.exists(xml_path):
                os.remove(xml_path)
            if os.path.exists(xsd_path):
                os.remove(xsd_path)

    def test_validate_xsd_with_corrupt_xsd(self) -> None:
        """Test validate_via_xsd with corrupt XSD schema."""
        from pain001.xml.validate_via_xsd import validate_via_xsd

        # Create a valid XML file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xml"
        ) as xml_file:
            xml_file.write(
                '<?xml version="1.0"?><root><child>test</child></root>'
            )
            xml_path = xml_file.name

        # Create a corrupt XSD file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xsd"
        ) as xsd_file:
            xsd_file.write("This is not valid XML/XSD")
            xsd_path = xsd_file.name

        try:
            # This should return False due to XSD loading error
            result = validate_via_xsd(xml_path, xsd_path)
            assert result is False
        finally:
            if os.path.exists(xml_path):
                os.remove(xml_path)
            if os.path.exists(xsd_path):
                os.remove(xsd_path)
