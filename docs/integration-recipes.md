<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Integration recipes

Open, copyable patterns for wiring Pain001 into a payments pipeline.
Each recipe runs on your own infrastructure.
[`examples/30_integration_recipes.py`](https://github.com/sebastienrousseau/pain001/blob/main/examples/30_integration_recipes.py)
runs recipes 1, 2, 4 and 5 end to end on synthetic data, and CI runs it
on every change. Contributions of new recipes are welcome.

## 1. ERP or treasury CSV export to pain.001

Most ERP and treasury systems can export a payment run as CSV. Map its
columns onto Pain001's input columns (listed in the
[input-column reference](input-columns.md)), and take the batch-level
fields (debtor, initiating party, execution date) from your own
configuration.

```python
MAPPING = {
    "Invoice": "payment_id",
    "Supplier": "creditor_name",
    "SupplierIBAN": "creditor_account_IBAN",
    "SupplierBIC": "creditor_agent_BIC",
    "Amount": "payment_amount",
    "Currency": "payment_currency",
}
```

`pain001 init pain.001.001.09 -o payments.csv` writes a scaffold with
every column the message type needs; the example's `map_export`
function shows the whole mapping.

## 2. Batch pipeline

Run these from the directory that holds the data: `validate` and
`generate` read data files only inside the working directory.

```sh
pain001 validate -t pain.001.001.09 -d payments.csv
pain001 generate -t pain.001.001.09 -d payments.csv -o out
pain001 check out/pain.001.001.09.xml
```

Add `--scheme sepa-sct` (or another rail) and a private
[bank profile](bank-profiles.md) (`--rules`, `--schematron`) to check
more than the schema. `pain001 check --format sarif` writes a report
for code scanning, and the GitHub Action in this repository's
`action.yml` (`uses: sebastienrousseau/pain001@v<version>`) runs `check`
in your own CI.

To send and collect files over SFTP, add `pain001 upload` and
`pain001 download` (the `upload` extra) as described in
[the SFTP guide](sftp-upload.md). Schedule the pipeline with
cron or a systemd timer; Pain001 runs no daemon.

## 3. API pipeline

`pain001 serve` (the `api` extra) exposes the same steps over REST:
`POST /api/v1/validate`, `POST /api/v1/generate` (and
`/api/v1/generate/async` with job status and download) and
`POST /api/v1/check` for an XML document you send. Without
`PAIN001_API_KEY` the server binds only loopback.
[`examples/05_api_job_lifecycle.py`](https://github.com/sebastienrousseau/pain001/blob/main/examples/05_api_job_lifecycle.py)
and [`examples/26_rest_server.py`](https://github.com/sebastienrousseau/pain001/blob/main/examples/26_rest_server.py)
run these calls.

## 4. pain.002 status reports

The bank answers a pain.001 with a pain.002 status report.
`pain001 status` reads it and exits 3 when any group, payment block or
transaction was rejected, so a scheduled job can alert on it:

```sh
pain001 status replies/*.xml            # exit 0 accepted, 3 rejected
pain001 status --format json replies/*.xml
```

Each rejected item is listed with its reason code (for example `AC04`,
closed account). From Python, `parse_pain002_report` returns the same
data.

## 5. camt.052, camt.053 and camt.054 reconciliation

Install the `camt` extra to read cash-management reports through the
[camt053](https://pypi.org/project/camt053/) package:

```sh
pip install "pain001[camt]"
pain001 status statements/*.xml
```

To reconcile, match each statement entry's end-to-end identifier with
the payments you sent:

```python
import camt053
from pain001.corpus.rules.projection import rows_from_xml

sent = {r["end_to_end_id"] for r in rows_from_xml(pain001_xml)}
statement = camt053.parse_document(camt_xml)
booked = {d.end_to_end_id for e in statement.all_entries() for d in e.details}
open_items = sorted(sent - booked)
```

`open_items` are the payments not yet booked, for example the one the
bank rejected in its pain.002.
