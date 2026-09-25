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
