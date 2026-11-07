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

"""Drive ``pain001 plugins``, ``upload`` and ``serve --help``.

Demonstrates the CLI commands the other examples leave out:

* ``plugins list`` / ``plugins show`` - inspect the plugin substrate
  (exit ``0``; an unknown plugin name exits ``1``)
* ``plugins disable`` - prints the ``PAIN001_DISABLE_PLUGINS`` line to
  export; it changes no settings, which this script checks
* ``upload`` - SFTP delivery: the local refusals (no network), then a
  real round trip against a throwaway SFTP server this script starts
  on ``127.0.0.1`` with a fresh host key, logging in with a synthetic
  password, a passphrase-protected private key, and that key with a
  short-lived OpenSSH certificate (``--certificate``)
* ``serve --help`` - the REST launcher's options (26_rest_server.py
  starts the server itself)

Every subprocess runs with a temporary ``HOME`` and ``XDG_CONFIG_HOME``
so nothing touches the user's real configuration or SSH trust files.
The loopback round trip needs the ``upload`` extra (``paramiko``); it
is skipped with a message when that extra is not installed.

Run from the repository root::

    python examples/25_cli_plugins_and_upload.py
"""

import importlib.util
import json
import logging
import os
import socket
import subprocess  # nosec B404
import sys
import tempfile
import time
from pathlib import Path
from threading import Event, Thread

from pain001 import DEFAULT_TEMPLATE_REGISTRY

_SAMPLE = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.001.001.03")
assert _SAMPLE.example_xml_path is not None, "bundle ships a sample XML"
SAMPLE_XML: Path = _SAMPLE.example_xml_path
PASSWORD_ENV = "EXAMPLE_SFTP_PASSWORD"
PASSWORD = "example-only"  # nosec B105 - synthetic loopback credential
PASSPHRASE_ENV = "EXAMPLE_SFTP_KEY_PASSPHRASE"
PASSPHRASE = "example-key-only"  # nosec B105 - synthetic loopback key
#: Key types the loopback server was offered, to show a certificate.
PRESENTED: list[str] = []


def isolated_env(home: Path) -> dict[str, str]:
    """Return an environment whose home and config dirs are temporary.

    Args:
        home: Temporary directory standing in for the user's home.

    Returns:
        A copy of ``os.environ`` with ``HOME`` and ``XDG_CONFIG_HOME``
        redirected and any inherited plugin override removed.
    """
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env.pop("PAIN001_DISABLE_PLUGINS", None)
    return env


def run_cli(
    args: list[str], cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run the pain001 CLI in a subprocess and return the result.

    Args:
        args: CLI arguments to append after ``python -m pain001``.
        cwd: Working directory for the subprocess.
        env: Environment for the subprocess.

    Returns:
        The completed process with captured output.
    """
    return subprocess.run(  # nosec B603
        [sys.executable, "-m", "pain001", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _plugins_list_and_show(cwd: Path, env: dict[str, str]) -> None:
    """List every plugin as JSON, then show one by name."""
    result = run_cli(["plugins", "list", "--json"], cwd, env)
    assert result.returncode == 0, result.stdout + result.stderr
    plugins = {(p["kind"], p["name"]) for p in json.loads(result.stdout)}
    assert {("loader", "csv"), ("scheme", "sepa-sct")} <= plugins
    assert ("writer", "xml-file") in plugins
    kinds = sorted({kind for kind, _ in plugins})
    print(f"plugins list --json   -> exit 0 ({len(plugins)} plugins: {kinds})")

    result = run_cli(["plugins", "show", "sepa-sct"], cwd, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "source:      built-in" in result.stdout
    print("plugins show sepa-sct -> exit 0 (metadata)")

    result = run_cli(["plugins", "show", "no-such-plugin"], cwd, env)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "No plugin named" in result.stdout
    print("plugins show unknown  -> exit 1")


def _plugins_disable(cwd: Path, env: dict[str, str], home: Path) -> None:
    """Show that ``disable`` only prints advice; the env var does the work."""
    result = run_cli(["plugins", "disable", "parquet"], cwd, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "export PAIN001_DISABLE_PLUGINS=parquet" in result.stdout
    assert "no settings were changed" in result.stdout
    assert not any(home.rglob("*")), "disable must not write to HOME"
    print("plugins disable       -> exit 0 (advice only, HOME untouched)")

    result = run_cli(["plugins", "disable", "x;rm -rf ~"], cwd, env)
    assert result.returncode == 2, result.stdout + result.stderr
    print("disable shell expr    -> exit 2 (rejected)")

    args = ["plugins", "list", "--kind", "loader", "--json"]
    disabled_env = env | {"PAIN001_DISABLE_PLUGINS": "parquet"}
    loaders = json.loads(run_cli(args, cwd, disabled_env).stdout)
    names = {loader["name"] for loader in loaders}
    assert "parquet" not in names and "csv" in names
    restored = json.loads(run_cli(args, cwd, env).stdout)
    assert "parquet" in {loader["name"] for loader in restored}
    print("PAIN001_DISABLE_PLUGINS=parquet -> parquet gone for that run only")


def _upload_local_checks(cwd: Path, env: dict[str, str]) -> None:
    """Show the refusals ``upload`` makes before opening any socket."""
    result = run_cli(["upload", "--help"], cwd, env)
    assert result.returncode == 0 and "--sftp" in result.stdout
    print("upload --help         -> exit 0")

    url = "sftp://ops@127.0.0.1/inbox/"
    checks = [
        (["--sftp", url], 2, "FILE_PATH is required"),
        (
            [str(SAMPLE_XML), "--sftp", "https://example.invalid/"],
            1,
            "sftp://",
        ),
        (
            [str(SAMPLE_XML), "--sftp", url, "--accept-host-key", "abc"],
            1,
            "OpenSSH SHA256",
        ),
        (
            [str(SAMPLE_XML), "--sftp", url, "--password-env", PASSWORD_ENV],
            1,
            "is not set",
        ),
    ]
    for args, code, needle in checks:
        result = run_cli(["upload", *args], cwd, env)
        assert result.returncode == code, result.stdout + result.stderr
        assert needle in result.stderr, result.stderr
        print(f"upload refusal        -> exit {code} ({needle!r})")


def _auth_class(client_key: str) -> type:
    """Build the loopback server's credential checks (needs ``paramiko``).

    Args:
        client_key: Base64 of the only public key ``ops`` may use.
    """
    import paramiko

    class LoopbackAuth(paramiko.ServerInterface):
        """Accept only the synthetic ``ops`` account on session channels."""

        def check_auth_password(self, username: str, password: str) -> int:
            """Validate the synthetic password."""
            ok = (username, password) == ("ops", PASSWORD)
            return paramiko.AUTH_SUCCESSFUL if ok else paramiko.AUTH_FAILED

        def check_auth_publickey(self, username: str, key: object) -> int:
            """Accept the one generated client key for ``ops``."""
            ok = username == "ops" and key.get_base64() == client_key
            blob = key.public_blob
            PRESENTED.append(blob.key_type if blob else key.get_name())
            return paramiko.AUTH_SUCCESSFUL if ok else paramiko.AUTH_FAILED

        def get_allowed_auths(self, username: str) -> str:
            """Advertise password and public-key authentication."""
            return "password,publickey"

        def check_channel_request(self, kind: str, chanid: int) -> int:
            """Permit SSH session channels only."""
            if kind == "session":
                return paramiko.OPEN_SUCCEEDED
            return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    return LoopbackAuth


def _files_class() -> type:
    """Build an SFTP handler confined to one temp directory."""
    import paramiko

    class LoopbackFiles(paramiko.SFTPServerInterface):
        """Map the SFTP calls ``upload`` makes into ``root``."""

        def __init__(self, server: object, *, root: Path) -> None:
            super().__init__(server)
            self.root = root

        def _path(self, path: str) -> Path:
            result = (self.root / path.lstrip("/")).resolve()
            if not result.is_relative_to(self.root):
                raise PermissionError("outside the loopback root")
            return result

        def lstat(self, path: str) -> object:
            try:
                return paramiko.SFTPAttributes.from_stat(
                    self._path(path).lstat()
                )
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)

        def open(self, path: str, flags: int, attr: object) -> object:
            try:
                fd = os.open(self._path(path), flags, 0o600)
                handle = paramiko.SFTPHandle(flags)
                if flags & os.O_WRONLY:
                    handle.writefile = os.fdopen(fd, "wb")
                else:
                    handle.readfile = os.fdopen(fd, "rb")
                return handle
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)

        def rename(self, oldpath: str, newpath: str) -> int:
            try:
                os.link(self._path(oldpath), self._path(newpath))
                self._path(oldpath).unlink()
                return paramiko.SFTP_OK
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)

    return LoopbackFiles


def _serve_one(
    connection: socket.socket,
    key: object,
    root: Path,
    stop: Event,
    client_key: str,
) -> None:
    """Run one SSH session with an SFTP subsystem rooted at ``root``."""
    import paramiko

    try:
        with paramiko.Transport(connection) as transport:
            transport.add_server_key(key)
            transport.set_subsystem_handler(
                "sftp", paramiko.SFTPServer, _files_class(), root=root
            )
            transport.start_server(server=_auth_class(client_key)())
            while transport.is_active() and not stop.wait(0.01):
                pass
    except (EOFError, OSError, paramiko.SSHException):
        pass  # --print-host-key and a rejected pin hang up mid-handshake


def _start_sftp_server(
    root: Path, stop: Event, client_key: str
) -> tuple[int, str]:
    """Start a throwaway SFTP server on loopback.

    Args:
        root: Directory the server exposes as its filesystem root.
        stop: Event that ends the server thread when set.
        client_key: Public key accepted for the ``ops`` account.

    Returns:
        The bound port and the host key's SHA256 fingerprint.
    """
    import paramiko

    from pain001.transport.sftp import fingerprint

    # The client side hangs up mid-handshake on purpose (host-key probe,
    # rejected pin); keep paramiko's server-side log of that quiet.
    logging.getLogger("paramiko").addHandler(logging.NullHandler())
    key = paramiko.RSAKey.generate(2048)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    listener.settimeout(0.1)

    def serve() -> None:
        """Handle client sessions one at a time until stopped."""
        with listener:
            while not stop.is_set():
                try:
                    connection, _ = listener.accept()
                except TimeoutError:
                    continue
                _serve_one(connection, key, root, stop, client_key)

    Thread(target=serve, daemon=True).start()
    return listener.getsockname()[1], fingerprint(key)


def _certificate(work: Path, user: object) -> Path:
    """Issue a one-hour user certificate for ``ops`` from a fresh CA."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    now = int(time.time())
    certificate = (
        serialization.SSHCertificateBuilder()
        .public_key(user.public_key())  # type: ignore[attr-defined]
        .serial(1)
        .type(serialization.SSHCertificateType.USER)
        .key_id(b"example-ops")
        .valid_principals([b"ops"])
        .valid_after(now - 60)
        .valid_before(now + 3600)
        .sign(ed25519.Ed25519PrivateKey.generate())
    )
    path = work / "id_ed25519-cert.pub"
    path.write_bytes(certificate.public_bytes())
    return path


def _client_key(work: Path) -> tuple[str, Path, Path]:
    """Generate an Ed25519 key, save it encrypted, and certify it.

    Returns:
        The public key's base64, the private-key file and its certificate.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    user = ed25519.Ed25519PrivateKey.generate()
    path = work / "id_ed25519"
    path.write_bytes(
        user.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.BestAvailableEncryption(PASSPHRASE.encode()),
        )
    )
    public = user.public_key().public_bytes(
        serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
    )
    return public.split()[1].decode(), path, _certificate(work, user)


def _upload_with_key(
    work: Path, env: dict[str, str], url: str, pin: str, key_file: Path
) -> None:
    """Log in with the private key, then refuse a wrong passphrase."""
    args = [str(SAMPLE_XML), "--sftp", url, "--accept-host-key", pin]
    args += ["--identity-file", str(key_file), "--passphrase-env"]
    args += [PASSPHRASE_ENV]
    keyed_env = env | {PASSPHRASE_ENV: PASSPHRASE}
    result = run_cli(["upload", *args], work, keyed_env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith("Uploaded"), result.stdout
    print("upload (private key)  -> exit 0 (Uploaded, no password)")

    wrong_env = env | {PASSPHRASE_ENV: "not-the-passphrase"}
    result = run_cli(["upload", *args], work, wrong_env)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "wrong passphrase" in result.stderr, result.stderr
    print("upload (bad passphrase) -> exit 1 (wrong passphrase, offline)")


def _upload_with_certificate(
    work: Path, env: dict[str, str], url: str, pin: str, files: tuple
) -> None:
    """Log in with the key plus its certificate; the server sees the cert."""
    key_file, certificate = files
    args = [str(SAMPLE_XML), "--sftp", url, "--accept-host-key", pin]
    args += ["--identity-file", str(key_file), "--certificate"]
    args += [str(certificate), "--passphrase-env", PASSPHRASE_ENV]
    PRESENTED.clear()
    result = run_cli(
        ["upload", *args], work, env | {PASSPHRASE_ENV: PASSPHRASE}
    )
    assert result.returncode == 0, result.stdout + result.stderr
    cert_type = "ssh-ed25519-cert-v01@openssh.com"
    assert cert_type in PRESENTED, PRESENTED
    print(f"upload (certificate)  -> exit 0 (server saw {cert_type})")


def _upload_round_trip(work: Path, env: dict[str, str]) -> None:
    """Pin, upload, retry and reject a wrong pin against loopback SFTP."""
    remote = work / "remote"
    (remote / "inbox").mkdir(parents=True)
    (remote / "keyed").mkdir()
    (remote / "certified").mkdir()
    known_hosts = work / "known_hosts"
    known_hosts.write_text("", encoding="utf-8")  # trust nothing by default
    client_key, key_file, certificate = _client_key(work)
    stop = Event()
    port, pin = _start_sftp_server(remote.resolve(), stop, client_key)
    url = f"sftp://ops@127.0.0.1:{port}/inbox/"
    env = env | {PASSWORD_ENV: PASSWORD}
    try:
        result = run_cli(
            ["upload", "--sftp", url, "--print-host-key"], work, env
        )
        assert result.returncode == 0 and result.stdout.strip() == pin
        print("upload --print-host-key -> exit 0 (prints the server key)")

        args = [str(SAMPLE_XML), "--sftp", url, "--known-hosts"]
        args += [str(known_hosts), "--password-env", PASSWORD_ENV]
        for expected in ("Uploaded", "Already delivered"):
            result = run_cli(
                ["upload", *args, "--accept-host-key", pin], work, env
            )
            assert result.returncode == 0, result.stdout + result.stderr
            assert result.stdout.startswith(expected), result.stdout
            print(f"upload (pinned)       -> exit 0 ({expected})")
        delivered = remote / "inbox" / SAMPLE_XML.name
        assert delivered.read_bytes() == SAMPLE_XML.read_bytes()

        wrong = "SHA256:" + "A" * 43
        result = run_cli(
            ["upload", *args, "--accept-host-key", wrong], work, env
        )
        assert result.returncode == 1 and "Host key mismatch" in result.stderr
        print("upload (wrong pin)    -> exit 1 (refused before auth)")

        keyed_url = f"sftp://ops@127.0.0.1:{port}/keyed/"
        _upload_with_key(work, env, keyed_url, pin, key_file)
        keyed = remote / "keyed" / SAMPLE_XML.name
        assert keyed.read_bytes() == SAMPLE_XML.read_bytes()

        certified_url = f"sftp://ops@127.0.0.1:{port}/certified/"
        files = (key_file, certificate)
        _upload_with_certificate(work, env, certified_url, pin, files)
    finally:
        stop.set()
    assert known_hosts.read_text(encoding="utf-8") == "", "trust not saved"


def _has_paramiko() -> bool:
    """Return True when the optional ``upload`` extra is installed."""
    return importlib.util.find_spec("paramiko") is not None


def main() -> None:
    """Exercise plugins, upload and serve with an isolated HOME."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        home = work / "home"
        home.mkdir()
        env = isolated_env(home)
        _plugins_list_and_show(work, env)
        _plugins_disable(work, env, home)
        _upload_local_checks(work, env)
        if _has_paramiko():
            _upload_round_trip(work, env)
        else:
            print("upload round trip -> skipped (needs pain001[upload])")
        result = run_cli(["serve", "--help"], work, env)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "--host" in result.stdout and "127.0.0.1" in result.stdout
        print("serve --help          -> exit 0 (see 26_rest_server.py)")
        assert not any(home.rglob("*")), "nothing persisted under HOME"


if __name__ == "__main__":
    main()
