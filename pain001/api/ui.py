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

"""Single-file hosted dashboard at ``/api/v1/ui`` (issue #188).

A finance user without Python or a terminal opens one URL, drops a
CSV on the page, picks a message type and the scheme rulebooks to
enforce, and downloads the validated XML. The page is one vanilla HTML
document with inline CSS and JavaScript: no framework, no build step,
no CDN, no new runtime dependency. It talks to two JSON endpoints that
sit next to it:

* ``POST /api/v1/ui/validate`` - the file's text plus options in, the
  same :class:`~pain001.api.models.ValidationResponse` the path-based
  ``/validate`` returns out.
* ``POST /api/v1/ui/generate`` - the same input; the XML document comes
  back inline so the browser can offer it as a download without the
  server ever writing the batch to disk.

Both endpoints carry the file *content* rather than a path because a
browser cannot name a file on the server, which is what the path-based
endpoints expect. They honour ``PAIN001_API_KEY`` like every other
route; the page keeps the key in ``sessionStorage`` for the tab's
lifetime only. Operators running a pure-API deployment can switch the
whole surface off with ``PAIN001_UI_DISABLED=1``.
"""

from __future__ import annotations

import csv
import io
import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from pain001 import __version__
from pain001.api.auth import require_api_key
from pain001.api.guards import sanitise_message_type
from pain001.api.models import (
    UiFilePayload,
    UiGenerateResponse,
    ValidationError,
    ValidationResponse,
)
from pain001.constants import TEMPLATES_DIR, valid_xml_types
from pain001.data.loader import load_payment_data
from pain001.exceptions import DataSourceError, PaymentValidationError
from pain001.observability.otel import traced
from pain001.validation import validate_scheme
from pain001.validation.schema_validator import SchemaValidator
from pain001.validation.schemes import PROFILES
from pain001.xml.generate_xml import generate_xml_string

UI_DISABLED_ENV = "PAIN001_UI_DISABLED"
"""Set to ``1`` / ``true`` / ``yes`` to take the dashboard offline."""

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
"""Largest file the dashboard accepts, in UTF-8 bytes (10 MiB)."""

SUPPORTED_SUFFIXES: tuple[str, ...] = (".csv", ".json", ".jsonl")
"""Text formats the dashboard parses in memory."""


def is_ui_enabled() -> bool:
    """Return ``True`` unless the operator set ``PAIN001_UI_DISABLED``.

    Returns:
        ``False`` when the env var is one of ``1`` / ``true`` / ``yes``
        (case-insensitive); ``True`` otherwise.
    """
    return os.environ.get(UI_DISABLED_ENV, "").lower() not in {
        "1",
        "true",
        "yes",
    }


def _require_ui_enabled() -> None:
    """Dependency that hides the dashboard when it is switched off.

    Raises:
        HTTPException: ``404`` when ``PAIN001_UI_DISABLED`` is set.
    """
    if not is_ui_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The dashboard is disabled (PAIN001_UI_DISABLED).",
        )


ui_router = APIRouter(
    prefix="/ui",
    tags=["UI"],
    dependencies=[Depends(_require_ui_enabled)],
)


_BAD_REQUEST = status.HTTP_400_BAD_REQUEST


def _parse_rows(filename: str, content: str) -> list[dict[str, Any]]:
    """Turn the uploaded text into validated payment rows.

    Mirrors the file loaders: CSV through :class:`csv.DictReader`, JSON
    as a list or a single object, JSON Lines one object per line, then
    the same row validation the path-based loaders apply.

    Args:
        filename: The name the browser reported; only its suffix is used.
        content: The file's text.

    Returns:
        The validated rows.

    Raises:
        HTTPException: ``400`` for an unsupported suffix, malformed
            text, or rows that fail validation; ``413`` when the text
            exceeds :data:`MAX_UPLOAD_BYTES`.
    """
    suffix = os.path.splitext(filename.lower())[1]
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=_BAD_REQUEST,
            detail=f"Unsupported file type {suffix or '(none)'!r}; upload a "
            f"{', '.join(SUPPORTED_SUFFIXES)} file.",
        )
    if len(content.encode("utf-8")) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB; "
                "use the CLI or the path-based API for batches this size."
            ),
        )

    rows: list[Any]
    if suffix == ".csv":
        rows = list(csv.DictReader(io.StringIO(content)))
    elif suffix == ".json":
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=_BAD_REQUEST, detail=f"Invalid JSON: {exc.msg}"
            ) from exc
        if isinstance(parsed, dict):
            rows = [parsed]
        elif isinstance(parsed, list):
            rows = parsed
        else:
            raise HTTPException(
                status_code=_BAD_REQUEST,
                detail="JSON input must be an object or an array of objects.",
            )
    else:
        rows = []
        for number, line in enumerate(content.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=_BAD_REQUEST,
                    detail=f"Invalid JSON on line {number}: {exc.msg}",
                ) from exc

    if not rows:
        raise HTTPException(
            status_code=_BAD_REQUEST, detail="The file has no payment rows."
        )
    if not all(isinstance(row, dict) for row in rows):
        raise HTTPException(
            status_code=_BAD_REQUEST,
            detail="Every payment row must be a JSON object.",
        )
    try:
        return load_payment_data(rows)
    except (DataSourceError, PaymentValidationError) as exc:
        raise HTTPException(status_code=_BAD_REQUEST, detail=str(exc)) from exc


def _format_errors(
    errors: list[tuple[int, list[Any]]],
) -> list[ValidationError]:
    """Flatten ``SchemaValidator.validate_batch`` errors into API models.

    Args:
        errors: ``(row_index, error_list)`` tuples for invalid rows.

    Returns:
        One :class:`ValidationError` per field error.
    """
    return [
        ValidationError(
            field=error.path,
            message=error.message,
            value=str(error.value),
        )
        for _, row_errors in errors
        for error in row_errors
    ]


def _scheme_violations(
    rows: list[dict[str, Any]], scheme: str | None
) -> tuple[bool, list[dict[str, Any]]]:
    """Run the requested scheme rulebooks, if any.

    Args:
        rows: Validated payment rows.
        scheme: Profile spec (one name, or comma-separated names), or
            ``None`` to skip scheme validation.

    Returns:
        ``(is_valid, violations)``; ``(True, [])`` when no scheme.

    Raises:
        HTTPException: ``400`` for an unknown profile name.
    """
    if not scheme:
        return True, []
    try:
        result = validate_scheme(rows, scheme)
    except ValueError as exc:
        raise HTTPException(status_code=_BAD_REQUEST, detail=str(exc)) from exc
    return result.is_valid, [v.as_dict() for v in result.violations]


@ui_router.post(
    "/validate",
    response_model=ValidationResponse,
    summary="Validate an uploaded file (dashboard)",
    dependencies=[Depends(require_api_key)],
)
@traced(
    "pain001.api.ui.validate", attributes={"http.route": "/api/v1/ui/validate"}
)
async def ui_validate(payload: UiFilePayload) -> ValidationResponse:
    """Validate the uploaded text against the schema and optional schemes.

    Args:
        payload: The file's text, its name, the message type, and an
            optional scheme spec.

    Returns:
        The same shape as ``POST /validate``.
    """
    rows = _parse_rows(payload.filename, payload.content)
    validator = SchemaValidator(
        sanitise_message_type(payload.message_type.value)
    )
    total, valid, errors = validator.validate_batch(rows)
    scheme_ok, violations = _scheme_violations(rows, payload.scheme)
    return ValidationResponse(
        is_valid=not errors and scheme_ok,
        total_rows=total,
        valid_rows=valid,
        invalid_rows=total - valid,
        errors=_format_errors(errors),
        scheme_violations=violations,
    )


@ui_router.post(
    "/generate",
    response_model=UiGenerateResponse,
    summary="Generate XML from an uploaded file (dashboard)",
    dependencies=[Depends(require_api_key)],
)
@traced(
    "pain001.api.ui.generate", attributes={"http.route": "/api/v1/ui/generate"}
)
async def ui_generate(payload: UiFilePayload) -> UiGenerateResponse:
    """Validate the upload, then render the XML and return it inline.

    Args:
        payload: The file's text, its name, the message type, and an
            optional scheme spec.

    Returns:
        ``success=True`` with the XML document and a suggested filename,
        or ``success=False`` carrying the validation errors or scheme
        violations that blocked generation.

    Raises:
        HTTPException: ``400`` when rendering fails (for example the
            rendered document does not satisfy the XSD).
    """
    rows = _parse_rows(payload.filename, payload.content)
    # Allow-list barrier: the enum is already constrained, but the value
    # is joined into filesystem paths below and static analysis only
    # recognises an explicit membership check as a sanitiser.
    message_type = sanitise_message_type(payload.message_type.value)
    validator = SchemaValidator(message_type)
    total, valid, errors = validator.validate_batch(rows)
    if errors:
        return UiGenerateResponse(
            success=False,
            message=f"Validation failed: {valid}/{total} rows valid",
            validation_errors=_format_errors(errors),
        )
    scheme_ok, violations = _scheme_violations(rows, payload.scheme)
    if not scheme_ok:
        return UiGenerateResponse(
            success=False,
            message=f"Scheme '{payload.scheme}' validation failed",
            scheme_violations=violations,
        )
    template_base = TEMPLATES_DIR / message_type
    try:
        xml = generate_xml_string(
            rows,
            message_type,
            str(template_base / "template.xml"),
            str(template_base / f"{message_type}.xsd"),
        )
    except (ValueError, RuntimeError, PaymentValidationError) as exc:
        raise HTTPException(
            status_code=_BAD_REQUEST, detail=f"Generation failed: {exc}"
        ) from exc
    return UiGenerateResponse(
        success=True,
        message=f"Generated {message_type} for {total} payment rows",
        filename=f"{message_type}.xml",
        xml=xml,
    )


@ui_router.get("", include_in_schema=False, response_class=HTMLResponse)
async def ui_page() -> HTMLResponse:
    """Serve the dashboard page.

    Returns:
        The single-file HTML application, with the supported message
        types and scheme profiles of this build embedded.
    """
    page = (
        _UI_HTML.replace("__VERSION__", __version__)
        .replace("__MESSAGE_TYPES__", json.dumps(list(valid_xml_types)))
        .replace("__SCHEMES__", json.dumps(list(PROFILES)))
    )
    return HTMLResponse(page)


_UI_HTML = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pain001 dashboard</title>
<style>
  :root {
    --bg: #f7f7f5; --fg: #1d1d1b; --muted: #6b6b66; --line: #d9d9d4;
    --card: #ffffff; --accent: #0b5cad; --ok: #1a7f37; --bad: #b42318;
    --warn: #9a6700;
    color-scheme: light dark;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #161614; --fg: #ecece8; --muted: #a3a39c; --line: #35352f;
      --card: #1f1f1c; --accent: #6cb4ff; --ok: #57c078; --bad: #ff7a6e;
      --warn: #e2b53e;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--fg);
    font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  main { max-width: 760px; margin: 0 auto; padding: 32px 16px 64px; }
  h1 { font-size: 1.5rem; margin: 0 0 4px; }
  h1 small { font-weight: 400; color: var(--muted); font-size: 0.9rem; }
  .badge {
    display: inline-block; font-size: 0.7rem; text-transform: uppercase;
    letter-spacing: .06em; border: 1px solid var(--warn); color: var(--warn);
    border-radius: 999px; padding: 1px 8px; vertical-align: middle;
  }
  p.lead { color: var(--muted); margin: 0 0 24px; }
  section {
    background: var(--card); border: 1px solid var(--line);
    border-radius: 10px; padding: 20px; margin-bottom: 16px;
  }
  label { display: block; font-weight: 600; margin-bottom: 6px; }
  .hint { color: var(--muted); font-weight: 400; font-size: 0.85rem; }
  input[type=password], select {
    width: 100%; padding: 8px 10px; border: 1px solid var(--line);
    border-radius: 6px; background: var(--bg); color: var(--fg); font: inherit;
  }
  #drop {
    border: 2px dashed var(--line); border-radius: 10px; padding: 28px;
    text-align: center; cursor: pointer; transition: border-color .15s;
  }
  #drop.over, #drop:focus-within { border-color: var(--accent); }
  #drop input { position: absolute; width: 1px; height: 1px; opacity: 0; }
  #filename { font-weight: 600; margin-top: 8px; }
  .row { display: flex; gap: 16px; flex-wrap: wrap; }
  .row > div { flex: 1 1 240px; }
  fieldset { border: 0; padding: 0; margin: 0; }
  fieldset legend { font-weight: 600; margin-bottom: 6px; }
  .schemes { display: flex; flex-wrap: wrap; gap: 6px 16px; }
  .schemes label { font-weight: 400; display: flex; gap: 6px; align-items: center; margin: 0; }
  .actions { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  button {
    font: inherit; font-weight: 600; padding: 9px 16px; border-radius: 6px;
    border: 1px solid var(--accent); background: var(--accent); color: #fff;
    cursor: pointer;
  }
  button.secondary { background: transparent; color: var(--accent); }
  button:disabled { opacity: .5; cursor: not-allowed; }
  #status { margin: 0; min-height: 1.5em; }
  #status.ok { color: var(--ok); } #status.bad { color: var(--bad); }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; margin-top: 12px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { color: var(--muted); font-weight: 600; }
  .wrap { overflow-x: auto; }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85em; }
  footer { color: var(--muted); font-size: 0.85rem; margin-top: 24px; }
  footer a { color: var(--accent); }
</style>
</head>
<body>
<main>
  <h1>Pain001 <small>v__VERSION__</small> <span class="badge">beta</span></h1>
  <p class="lead">Drop a payment file, pick the message type and rulebooks, validate, and download the ISO 20022 XML. Nothing is stored on the server.</p>

  <section>
    <label for="apikey">API key <span class="hint">(only if the server sets <code>PAIN001_API_KEY</code>; kept in this tab only)</span></label>
    <input id="apikey" type="password" autocomplete="off" placeholder="Bearer token">
  </section>

  <section>
    <div id="drop" tabindex="0" role="button" aria-label="Choose or drop a payment file">
      <input id="file" type="file" accept=".csv,.json,.jsonl,text/csv,application/json">
      <div>Drop a <strong>.csv</strong>, <strong>.json</strong> or <strong>.jsonl</strong> file here, or click to choose</div>
      <div id="filename" aria-live="polite"></div>
    </div>
  </section>

  <section>
    <div class="row">
      <div>
        <label for="mt">Message type</label>
        <select id="mt"></select>
      </div>
      <div>
        <fieldset>
          <legend>Scheme rulebooks <span class="hint">(optional, combine freely)</span></legend>
          <div class="schemes" id="schemes"></div>
        </fieldset>
      </div>
    </div>
  </section>

  <section>
    <div class="actions">
      <button id="validate" type="button" disabled>Validate</button>
      <button id="generate" type="button" disabled>Generate</button>
      <button id="download" type="button" class="secondary" hidden>Download XML</button>
      <p id="status" role="status" aria-live="polite"></p>
    </div>
    <div id="results" class="wrap"></div>
  </section>

  <footer>Interactive API reference at <a href="/api/reference">/api/reference</a>. Larger batches: use the CLI or the path-based <code>/api/v1/generate</code>.</footer>
</main>
<script>
(function () {
  'use strict';
  var MESSAGE_TYPES = __MESSAGE_TYPES__;
  var SCHEMES = __SCHEMES__;
  var base = location.pathname.replace(/\\/+$/, '');
  var $ = function (id) { return document.getElementById(id); };
  var fileInput = $('file'), drop = $('drop'), status = $('status'), results = $('results');
  var validateBtn = $('validate'), generateBtn = $('generate'), downloadBtn = $('download');
  var current = null, downloadUrl = null;

  MESSAGE_TYPES.forEach(function (mt) {
    var o = document.createElement('option'); o.value = mt; o.textContent = mt; $('mt').appendChild(o);
  });
  SCHEMES.forEach(function (name) {
    var l = document.createElement('label');
    var c = document.createElement('input'); c.type = 'checkbox'; c.value = name; c.name = 'scheme';
    l.appendChild(c); l.appendChild(document.createTextNode(name)); $('schemes').appendChild(l);
  });
  try { $('apikey').value = sessionStorage.getItem('pain001.apikey') || ''; } catch (e) {}
  $('apikey').addEventListener('input', function () {
    try { sessionStorage.setItem('pain001.apikey', this.value); } catch (e) {}
  });

  function setStatus(text, kind) { status.textContent = text; status.className = kind || ''; }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function takeFile(file) {
    if (!file) { return; }
    var reader = new FileReader();
    reader.onload = function () {
      current = { filename: file.name, content: reader.result };
      $('filename').textContent = file.name + ' (' + file.size.toLocaleString() + ' bytes)';
      validateBtn.disabled = generateBtn.disabled = false;
      downloadBtn.hidden = true; results.innerHTML = ''; setStatus('');
    };
    reader.readAsText(file);
  }
  fileInput.addEventListener('change', function () { takeFile(this.files[0]); });
  drop.addEventListener('click', function (e) { if (e.target !== fileInput) { fileInput.click(); } });
  drop.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); } });
  ['dragenter', 'dragover'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('over'); });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('over'); });
  });
  drop.addEventListener('drop', function (e) { takeFile(e.dataTransfer.files[0]); });

  function selectedSchemes() {
    return Array.prototype.map.call(document.querySelectorAll('input[name=scheme]:checked'), function (c) { return c.value; }).join(',');
  }
  function payload() {
    return { filename: current.filename, content: current.content, message_type: $('mt').value, scheme: selectedSchemes() || null };
  }
  function call(path) {
    var headers = { 'Content-Type': 'application/json' };
    var key = $('apikey').value;
    if (key) { headers.Authorization = 'Bearer ' + key; }
    return fetch(base + path, { method: 'POST', headers: headers, body: JSON.stringify(payload()) })
      .then(function (r) { return r.json().then(function (body) { return { ok: r.ok, status: r.status, body: body }; }); });
  }
  function renderFindings(errors, violations) {
    var html = '';
    if (errors && errors.length) {
      html += '<table><thead><tr><th>Field</th><th>Problem</th><th>Value</th></tr></thead><tbody>';
      errors.forEach(function (e) {
        html += '<tr><td><code>' + escapeHtml(e.field) + '</code></td><td>' + escapeHtml(e.message) + '</td><td><code>' + escapeHtml(e.value == null ? '' : e.value) + '</code></td></tr>';
      });
      html += '</tbody></table>';
    }
    if (violations && violations.length) {
      html += '<table><thead><tr><th>Row</th><th>Rule</th><th>Field</th><th>Message</th><th>Fix</th></tr></thead><tbody>';
      violations.forEach(function (v) {
        html += '<tr><td>' + escapeHtml(v.index) + '</td><td><code>' + escapeHtml(v.rule) + '</code></td><td><code>' + escapeHtml(v.field || '') + '</code></td><td>' + escapeHtml(v.message) + '</td><td>' + escapeHtml(v.remediation || '') + '</td></tr>';
      });
      html += '</tbody></table>';
    }
    results.innerHTML = html;
  }
  function busy(on) { validateBtn.disabled = generateBtn.disabled = on; }

  validateBtn.addEventListener('click', function () {
    busy(true); setStatus('Validating…'); downloadBtn.hidden = true;
    call('/validate').then(function (r) {
      if (!r.ok) { setStatus(r.body.detail || ('HTTP ' + r.status), 'bad'); results.innerHTML = ''; return; }
      var b = r.body;
      renderFindings(b.errors, b.scheme_violations);
      setStatus(b.is_valid ? 'Valid: ' + b.valid_rows + ' of ' + b.total_rows + ' rows pass.'
                           : 'Invalid: ' + b.invalid_rows + ' of ' + b.total_rows + ' rows fail' + (b.scheme_violations.length ? ', ' + b.scheme_violations.length + ' scheme violation(s).' : '.'),
                b.is_valid ? 'ok' : 'bad');
    }).catch(function (e) { setStatus('Request failed: ' + e, 'bad'); }).then(function () { busy(false); });
  });

  generateBtn.addEventListener('click', function () {
    busy(true); setStatus('Generating…'); downloadBtn.hidden = true;
    call('/generate').then(function (r) {
      if (!r.ok) { setStatus(r.body.detail || ('HTTP ' + r.status), 'bad'); results.innerHTML = ''; return; }
      var b = r.body;
      renderFindings(b.validation_errors, b.scheme_violations);
      if (!b.success) { setStatus(b.message, 'bad'); return; }
      if (downloadUrl) { URL.revokeObjectURL(downloadUrl); }
      downloadUrl = URL.createObjectURL(new Blob([b.xml], { type: 'application/xml' }));
      downloadBtn.hidden = false; downloadBtn.dataset.name = b.filename;
      setStatus(b.message + '. Ready to download.', 'ok');
    }).catch(function (e) { setStatus('Request failed: ' + e, 'bad'); }).then(function () { busy(false); });
  });

  downloadBtn.addEventListener('click', function () {
    var a = document.createElement('a'); a.href = downloadUrl; a.download = downloadBtn.dataset.name || 'pain001.xml';
    document.body.appendChild(a); a.click(); a.remove();
  });
})();
</script>
</body>
</html>
"""
