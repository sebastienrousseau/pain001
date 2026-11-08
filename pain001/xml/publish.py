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

"""Publish a payment file only once it is whole and checked.

A file that appears at its destination is picked up (by a watcher, an
SFTP push, an operator), so a writer must never leave a partial or
unchecked one there. Every writer stages the bytes in a temporary file
in the destination's own directory (so the final rename stays on one
filesystem and is atomic), fsyncs it, runs the caller's last checks,
and only then renames it over the destination with ``os.replace``. On
any failure the temporary file is removed and the destination keeps
whatever it held before.
"""

import contextlib
import os
import secrets
import time
import warnings
from collections.abc import Callable, Iterable
from typing import Any, TextIO

from pain001.exceptions import XMLGenerationError

#: A last check on the staged file (by path) before it is published.
StagedCheck = Callable[[str], None]


def _write_all(handle: TextIO, chunks: Iterable[str]) -> int:
    """Write every chunk to ``handle``; return the UTF-8 byte count."""
    total = 0
    for chunk in chunks:
        handle.write(chunk)
        total += len(chunk.encode("utf-8"))
    return total


def _stage(target: str) -> tuple[int, str]:
    """Create an exclusive temporary sibling of ``target``.

    ``os.open`` with mode 0o666 lets the process umask decide the final
    permissions, as a plain ``open()`` of the destination would.
    """
    folder, name = os.path.split(target)
    while True:
        staged = os.path.join(folder, f".{name}.{secrets.token_hex(6)}.tmp")
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            return os.open(staged, flags, 0o666), staged
        except FileExistsError:  # pragma: no cover - 48 random bits
            continue


def publish_stream(
    chunks: Iterable[str],
    destination: str,
    check: StagedCheck | None = None,
) -> tuple[str, int]:
    """Write ``chunks`` to ``destination`` atomically, after ``check``.

    Args:
        chunks: The document, in order.
        destination: Where the file is published; its directory is
            created when missing.
        check: Called with the staged file's path once it is fsynced;
            raising refuses the publication.

    Returns:
        The destination's real path and the number of bytes written.

    Raises:
        BaseException: Whatever rendering, writing, ``check`` or the
            rename raised, after the staged file was removed.
    """
    target = os.path.realpath(str(destination))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    descriptor, staged = _stage(target)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            size = _write_all(handle, chunks)
            handle.flush()
            os.fsync(handle.fileno())
        if check is not None:
            check(staged)
        os.replace(staged, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(staged)
        raise
    return target, size


def publish_text(content: str, destination: str) -> str:
    """Write ``content`` to ``destination`` atomically.

    Args:
        content: The whole document.
        destination: Where the file is published.

    Returns:
        The destination's real path.
    """
    return publish_stream((content,), destination)[0]


def require_schematron(content: str, rulebook: Any, failure: str) -> None:
    """Refuse ``content`` that breaks the Schematron ``rulebook``.

    Args:
        content: The XML document as it will be published.
        rulebook: A preset name (``sepa``, ``fednow``, ``cbpr``) or a
            ``.sch`` path.
        failure: The start of the error message, naming the file.

    Raises:
        XMLGenerationError: With every violation, when one is an error.
    """
    from pain001.schematron import validate_schematron

    result = validate_schematron(content, rulebook=rulebook)
    if not result.is_valid:
        raise XMLGenerationError(
            f"{failure} using '{rulebook}': {result.error_count} "
            f"error(s).\n{result.format_report()}"
        )


def require_xsd_valid(content: str, xsd_path: str, message_type: str) -> None:
    """Refuse ``content`` that the XSD at ``xsd_path`` rejects.

    Emits the ``validation_failed`` or ``xsd_validation_passed`` metric
    event, and reports every violation at once (element path and
    reason) so a caller can fix all inputs in a single retry.

    Args:
        content: The XML document.
        xsd_path: A validated path to the message type's schema.
        message_type: The message type, for the metric events.

    Raises:
        RuntimeError: Listing the violations, when the XSD rejects it.
    """
    from pain001.observability import emit_metric_event
    from pain001.xml.validate_via_xsd import (
        collect_xsd_validation_errors,
        validate_xml_string_via_xsd,
    )

    started = time.time()
    if not validate_xml_string_via_xsd(content, xsd_path):
        emit_metric_event(
            "validation_failed",
            message_type=message_type,
            schema_path=str(xsd_path),
        )
        reasons = collect_xsd_validation_errors(content, xsd_path)
        detail = "; ".join(reasons) if reasons else "unknown reason"
        raise RuntimeError(
            f"Generated XML failed validation against {xsd_path}: {detail}"
        )
    emit_metric_event(
        "xsd_validation_passed",
        message_type=message_type,
        schema_path=str(xsd_path),
        duration_ms=int((time.time() - started) * 1000),
    )


def xsd_check(xsd_path: str, message_type: str) -> StagedCheck:
    """A staged-file check that applies :func:`require_xsd_valid`.

    Args:
        xsd_path: A validated path to the message type's schema.
        message_type: The message type, for the metric events.

    Returns:
        The check, reading the staged file it is handed.
    """

    def check(staged: str) -> None:
        """Validate the staged file against the schema."""
        with open(staged, encoding="utf-8") as handle:
            require_xsd_valid(handle.read(), xsd_path, message_type)

    return check


def finalise_message(
    xml_content: str,
    envelop_bah: bool = False,
    bah_header: Any | None = None,
    xml_sign_key: str | bytes | None = None,
    xml_sign_cert: str | bytes | None = None,
    xml_sign_passphrase: str | bytes | None = None,
) -> str:
    """Wrap the message in a BAH envelope and sign it, when asked.

    Args:
        xml_content: The XSD-valid message.
        envelop_bah: Wrap it in an ISO 20022 BAH (head.001) envelope.
        bah_header: A customised BusinessApplicationHeader; implies the
            envelope.
        xml_sign_key: RSA private key (PEM) to sign the document with.
        xml_sign_cert: X.509 certificate (PEM) for KeyInfo.
        xml_sign_passphrase: Passphrase for the private key.

    Returns:
        The document as it will be published.
    """
    if envelop_bah or bah_header is not None:
        from pain001.xml.envelope import (
            BusinessApplicationHeader,
            envelop_iso20022_message,
        )

        header = bah_header or BusinessApplicationHeader()
        xml_content = envelop_iso20022_message(xml_content, header)
    if xml_sign_key is not None:
        from pain001.security.dsig import sign_xml_document

        xml_content = sign_xml_document(
            xml_content,
            private_key_pem=xml_sign_key,
            cert_pem=xml_sign_cert,
            passphrase=xml_sign_passphrase,
        )
    return xml_content


def prepare_stream_target(
    data: list[dict[str, Any]],
    message_type: str,
    template_path: str,
    output_path: str,
    xsd_schema_path: str | None,
) -> tuple[str, str]:
    """Check a streamed write's inputs, paths, schema and rows up front.

    Args:
        data: The payment rows.
        message_type: The target message type.
        template_path: The Jinja2 template the rows will be rendered by.
        output_path: Where the caller wants the file.
        xsd_schema_path: The schema, or ``None`` for the bundled one.

    Returns:
        The validated output path and schema path.

    Raises:
        ValueError: If the message type is unknown, the data empty, or
            the template, output or schema path fails validation.
        PaymentValidationError: If the rows break the message type's
            column contract.
    """
    from pain001.csv.validate_csv_data import validate_csv_data
    from pain001.exceptions import PaymentValidationError
    from pain001.security import validate_path
    from pain001.xml.generate_xml import (
        _validate_generation_inputs,
        canonicalize_payment_record,
    )

    _validate_generation_inputs(data, message_type, template_path)
    try:
        safe_output = validate_path(output_path)
    except Exception as e:
        raise ValueError(f"Invalid output path: {e}") from e
    if xsd_schema_path is None:
        from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

        template = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
        xsd_schema_path = str(template.xsd_path)
    try:
        safe_xsd = validate_path(xsd_schema_path, must_exist=True)
    except Exception as e:
        raise ValueError(f"Invalid schema path: {e}") from e
    rows = [canonicalize_payment_record(row) for row in data]
    if not validate_csv_data(rows, message_type):
        raise PaymentValidationError(
            f"Row validation failed for {message_type}; the log names "
            "each missing or mistyped column",
            field="records",
        )
    return safe_output, safe_xsd


def resolve_output_path(
    output_path: str | None, xml_file_path: str, message_type: str
) -> str:
    """Where generate_xml writes: ``output_path``, or next to the template.

    Args:
        output_path: The caller's explicit destination, if any.
        xml_file_path: The template path (the deprecated default).
        message_type: The message type, naming the default file.

    Returns:
        The real destination path; its directory exists.

    Raises:
        ValueError: If the derived default path fails validation.
    """
    if output_path is not None:
        safe_xml_path = os.path.realpath(str(output_path))
        os.makedirs(os.path.dirname(safe_xml_path) or ".", exist_ok=True)
        return safe_xml_path
    warnings.warn(
        "Calling generate_xml without output_path writes next to the "
        "template and requires it to be under the current working "
        "directory; pass output_path explicitly instead.",
        DeprecationWarning,
        stacklevel=3,
    )
    from pain001.security import validate_path
    from pain001.xml.generate_updated_xml_file_path import (
        generate_updated_xml_file_path,
    )

    # Legacy behavior: derive the output path from the template path.
    updated_xml_file_path = generate_updated_xml_file_path(
        xml_file_path, message_type
    )

    try:
        safe_xml_path = validate_path(updated_xml_file_path)
    except (
        Exception
    ) as e:  # pragma: no cover - the template path was already validated
        raise ValueError(f"Path validation failed: {e}") from e

    # Explicit startswith guard for CodeQL CWE-22 sanitiser recognition.
    cwd_prefix = str(os.path.realpath(os.getcwd()))
    if not safe_xml_path.startswith(
        cwd_prefix + os.sep
    ):  # pragma: no cover - CodeQL barrier; validate_path enforces it
        raise ValueError(
            f"Output path outside working directory: {safe_xml_path}"
        )
    return safe_xml_path
