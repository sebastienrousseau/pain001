<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0013. Download bank replies exactly once, with a local ledger

- **Status:** Accepted
- **Date:** 2026-11-09
- **Deciders:** Sebastien Rousseau (accepted 2026-11-09; ships in 0.0.85)

## Context

`pain001 upload` delivers a payment file over SFTP, but the bank's
answer (a pain.002 status report, or a camt.053 statement) has to be
fetched by hand or by a separate tool. The implementation plan's
download step asks for a command that collects those replies on a
schedule without losing one or saving one twice, through the same
host-key checks as `upload`.

A bank's outbox is shared, append-mostly state. Files can still be
growing when they are listed, names can be reused with new content, and
a run can stop between saving a file and removing it from the server.

## Options considered

1. Mirror the directory (fetch whatever is new by name). Simple, but a
   reused name overwrites an earlier reply, and a stop between saving and
   deleting either loses the file or fetches it twice.
2. A long-running watcher. Reacts sooner, but adds a daemon to operate
   and secure, and the core has none.
3. A one-shot command with a local ledger keyed by remote path and
   content hash: save, commit the ledger row, and only then delete or
   move the remote copy.

## Decision

Option 3. `download_sftp()` and `pain001 download` read each file into
a 0600 temporary file in the target directory, hash it, and move it into
place with `os.replace`; different bytes under a name already used are
saved as `name.<sha8>.ext`, never over it. A SQLite ledger (0600, never a
symlink) records every saved file by source and SHA256, and is committed
before the remote delete or move, so an interrupted run finishes the
disposal next time without saving again. Upload and download share one
`session()`, so the host-key check before credentials exists once.
`pain001 status` reads the replies with the existing pain.002 and
camt.053 parsers and exits 3 on any rejection, for a scheduled job to
alert on.

Scheduling stays with cron or systemd timers. MCP and REST do not offer
the download: they never open network connections.

## Consequences

- The `upload` extra now covers download too; no new dependency
  (`sqlite3` is in the standard library).
- A `keep` run skips files whose remote size and mtime the ledger
  already holds, without reading them. SFTP reports the mtime in whole
  seconds, so a file the bank rewrites with the same size within the
  same second would be missed; while nothing is deleted, the earlier
  copy also stays on the server. `delete` or `move` avoids that, and
  is the setting for production runs.
- `status` reads pain.002 with the core's parser. Plan decision D6
  (2026-11-09) gives camt parsing to the `camt053` package rather than
  a second parser here: when camt053 is installed, `status` reads
  camt.052, camt.053 and camt.054 with it; without it, the core's own
  camt.053 parser reads camt.053, and camt.052 and camt.054 are refused
  with exit 2 and the install command. A `pain001[camt]` extra follows
  once camt053 releases with version ranges instead of its exact
  jinja2, colorama and defusedxml pins, and the in-tree camt.053 parser
  is then deprecated.
- `status` reads the files named on its command line wherever they are
  (`download --to` saves anywhere): the parsers take a `base_dir`, and
  the file's own directory is the only base allowed.
- The ledger holds remote paths and local paths, not file contents or
  credentials.
