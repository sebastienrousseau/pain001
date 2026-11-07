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
