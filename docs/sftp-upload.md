<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Explicit SFTP delivery

Install `pain001[upload]`. Generating XML never uploads it automatically.
Obtain the server's host key through an independent trusted channel before
using a bank's endpoint. These examples use a reserved example hostname:

```sh
pain001 upload payment.xml --sftp sftp://user@bank.example/inbox/ \
  --known-hosts trusted_known_hosts --identity-file ./transfer_key
```

Without `--known-hosts`, the client checks the system and user's standard
known-hosts files. Unknown or changed keys are refused before authentication.
An independently verified OpenSSH SHA256 fingerprint can instead be supplied
with `--accept-host-key`. A known-key mismatch is never overridden by a pin.
No key is silently saved and no auto-add policy is used.

```sh
pain001 upload --sftp sftp://user@bank.example/inbox/ --print-host-key
```

This prints an **unverified** observation without authenticating or uploading.
It is not proof of identity; compare it with the independently supplied key.
For password authentication, use `--password-env BANK_SFTP_PASSWORD`; for an
encrypted private key, use `--passphrase-env BANK_SFTP_PASSPHRASE`. The named
variables must already contain secrets. Do not put passwords in URLs or
command arguments. The URL requires a username and an absolute remote path.

## Keys, certificates and ssh-agent

`--identity-file` takes an RSA, ECDSA or Ed25519 private key, in PEM or
OpenSSH format. The key is loaded before any connection opens, so a
missing or wrong passphrase is reported as such, not as a failed login.

If the server trusts a certificate authority instead of individual keys,
pass the certificate it issued for your key:

```sh
pain001 upload payment.xml --sftp sftp://user@bank.example/inbox/ \
  --accept-host-key SHA256:... --identity-file ./id_ed25519 \
  --certificate ./id_ed25519-cert.pub --passphrase-env BANK_SFTP_PASSPHRASE
```

Before connecting, pain001 checks that the certificate was issued for that
key and that the current time is inside its validity window, and says which
check failed. Whether the certificate's authority, principals and options are
accepted is decided by the server.

With no `--identity-file` and no password, keys from ssh-agent and the
default key files are offered. Giving either one turns those off, so only
what you named is used. Add `--use-agent` to offer ssh-agent keys as well:
this is how hardware-held keys that ssh-agent presents as RSA, ECDSA or
Ed25519 keys (PIV smartcards, for example) are used.

Some key files are refused by name before connecting:

| Key type | Why |
|---|---|
| `ssh-dss` (DSA) | OpenSSH 10.0 removed DSA, and paramiko has no DSA support. Use Ed25519. |
| `sk-ssh-ed25519@openssh.com`, `sk-ecdsa-sha2-nistp256@openssh.com` (FIDO) | paramiko cannot sign with FIDO security keys. |
| Any other type paramiko does not implement | Named in the error, with the paramiko version. |

The upload streams into an exclusively created, uniquely named `.tmp` file
in the destination directory, then publishes using standard SFTP rename.
The server must support same-directory atomic, no-clobber rename. An existing
destination is reused only when its length and streamed SHA256 match. A
different file or a symlink is refused. Retries do not overwrite a payment.
Failures clean up the temporary file where the connection remains usable;
an interrupted connection can require operator cleanup of an orphan `.tmp`.

This protects delivery bytes, not bank acceptance. Some banks remove inbox
files immediately, so absence on a later retry cannot prove whether a payment
was already processed. Use bank acknowledgements and your own submission
ledger to manage that case. Host-key rotation remains an explicit operator
decision. No live bank connection is part of the test suite.

## Fetching replies: `pain001 download`

`pain001 download` collects a bank's replies from a remote directory, each
file exactly once. It takes every trust and identity flag `upload` takes,
and checks the host key before any credential is sent:

```sh
pain001 download --sftp sftp://user@bank.example/outbox/ --to ./replies \
  --known-hosts trusted_known_hosts --identity-file ./transfer_key \
  --pattern '*.xml' --after-fetch move:/archive --settle-seconds 30
```

- **Exactly once.** Each file is read into a private (0600) temporary file
  in `--to`, hashed, and moved into place. A ledger,
  `.pain001-ledger.sqlite3` in `--to` unless `--ledger` names another,
  records it by remote path and SHA256 before the remote copy is touched.
  If a run stops between saving and the remote delete or move, the next run
  finishes the disposal without saving the file again.
- **Never overwritten.** A name that reappears with different bytes is saved
  beside the first as `name.<sha8>.xml`.
- **After the fetch.** `--after-fetch keep` (the default) leaves the remote
  file; a later `keep` run skips files the ledger holds at the same size and
  modification time (a server that reports no modification time never
  matches). `delete` removes it, and `move:/absolute/dir` renames
  it into an archive directory on the server. Both read and hash every
  file before touching the remote copy, so a reply reissued under the
  same name and size is saved as `name.<sha8>.xml`, never deleted unread.
  Use `delete` or `move` with a non-zero `--settle-seconds` for production
  runs. `keep` suits trying the
  command out and read-only bank outboxes: SFTP gives the modification
  time in whole seconds, so a file rewritten with the same size within
  the same second would be skipped.
- **Files still being written.** `--settle-seconds N` lists twice, N
  seconds apart, and leaves any file whose size or time changed for the
  next run. A file whose size changes during the transfer is refused.
- **Limits.** `--max-files` and `--max-bytes` bound one run; what they leave
  stays on the server and is reported.
- **Skipped names.** Symlinks, directories, hidden names, `.tmp` or
  `.part` files, and names holding a path separator, a colon or a control
  character are skipped and listed, so a link on the server cannot point
  the download at another file and a name cannot leave `--to` (a colon is
  drive-relative or a data stream on Windows). Listed names are printed
  with control characters and backslashes escaped as `\xNN` or `\uNNNN`.

There is no daemon. Run it from cron or a systemd timer. The MCP and REST
interfaces never open network connections, so they do not offer it.

## Reading replies: `pain001 status`

```sh
pain001 status replies/*.xml
```

`status` reads pain.002 status reports with the library's parser, and
camt.052, camt.053 and camt.054 with the
[camt053](https://pypi.org/project/camt053/) package when it is
installed (`pip install 'pain001[camt]'`); without it, camt.053 is read with the
library's own parser and camt.052 and camt.054 are refused. It prints
one line per file with its transaction count and how many of those
transactions were rejected, followed by the group or payment blocks
rejected, if any (`pain.002 RJCT, 3 transactions, 2 rejected; group and
1 payment block rejected`). Every rejected group, payment block and
transaction is then listed with its reason code. It exits `3` when anything
was rejected (`RJCT`), `2` when a file cannot be read or is another
message, and `0` otherwise; `--format json` prints the same as data. Together with
`download`, a scheduled job can fetch replies and alert on rejections.
