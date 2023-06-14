# Pain001: Automate ISO 20022-Compliant Payment File Creation

![Pain001 banner][banner]

[![PyPI][pypi-badge]][3] [![License][license-badge]][1]
[![Codecov][codecov-badge]][6]

## Overview

**Pain001** is an open-source Python Library that you can use to create
**ISO 20022-Compliant Payment Files** directly from your **CSV** or **SQLite**
Data Files.

The Python library focuses specifically on
**Payment Initiation and Advice Messages**, commonly known as **Pain**. It is
currently designed to be compatible with the **pain.001.001.03** and
**pain.001.001.09** message types and will support more message types in the
future.

Payments usually start with a **pain.001 payment initiation message**. The
payer sends it to the payee (or the payee’s bank) via a secure network. This
network could be **SWIFT** or **SEPA (Single Euro Payments Area) network**, or
other payment networks such as **CHAPS**, **BACS**, **Faster Payments**, etc.
The message contains the payer’s and payee’s bank account details, payment
amount, and other information required to process the payment.

The **Pain001** library can reduce payment processing complexity and costs by
generating ISO 20022-compliant payment files. These files automatically remove
the need to create and validate them manually, making the payment process more
efficient and cost-effective. It will save you time and resources and minimises
the risk of errors, making sure accurate and seamless payment processing.

Use the **Pain001** library to simplify, accelerate and automate your payment
processing.

## Requirements

**Pain001** works with macOS, Linux and Windows and requires Python 3.9.0 and
above.

## Installation

It takes just a few seconds to get up and running with **Pain001**. You can
install Pain001 from PyPI with pip or your favorite package manager:

Open your terminal and run the following command:

```sh
pip install pain001
```

Add the -U switch to update to the current version, if `pain001` is already
installed.

## Quick Start

After installation, you can run **Pain001** directly from the command line.
Simply call the main module pain001 with the paths of your

- **XML template file** containing the various parameters you want to pass from
  your Data file,
- **XSD schema file** to validate the generated XML file, and
- **Data file (CSV or SQLite)** containing the payment instructions that you
  want to submit.

Here’s how you would do that:

```sh
python3 -m pain001 \
    <xml_message_type> \
    <xml_template_file_path> \
    <xsd_schema_file_path> \
    <data_file_path>
```

### Arguments

When running **Pain001**, as briefly described above, you will need to specify
four arguments to the **Pain001** module:

- `xml_message_type`: This is the type of XML message you want to generate.

  The currently supported types are:
  - pain.001.001.03
  - pain.001.001.09
- `xml_template_file_path`: This is the path to the XML template file you are
  using that contains variables to be replaced with data from the Data file.
- `xsd_schema_file_path`: This is the path to the XSD schema file you are using
  to validate the generated XML file.
- `data_file_path`: This is the path to the CSV or SQLite Data file you want to
  convert to XML format.

## Examples

The following examples demonstrate how to use **Pain001** to generate a payment
initiation message from a CSV file and a SQLite Data file.

### Using a CSV Data File as the source

```sh
python3 -m pain001 \
    pain.001.001.03 \
    /path/to/your/template.xml \
    /path/to/your/pain.001.001.03.xsd \
    /path/to/your/template.csv
```

### Using a SQLite Data File as the source

```sh
python3 -m pain001 \
    pain.001.001.03 \
    /path/to/your/template.xml \
    /path/to/your/pain.001.001.03.xsd \
    /path/to/your/template.db
```

### Using the source code

You can use the source code and run the example code in your
terminal/command-line. To check out the source code, clone the repository from
GitHub:

```sh
git clone https://github.com/sebastienrousseau/pain001.git
```

You can then run this script to generate a payment initiation message from the
sample CSV Data file:

```sh
python3 pain001/__main__.py \
  --xml_message_type "pain.001.001.03" \
  --xml_template_file_path "templates/pain.001.001.03/template.xml" \
  --xsd_schema_file_path "templates/pain.001.001.03/pain.001.001.03.xsd" \
  --data_file_path "templates/pain.001.001.03/template.csv"
```

or the sample SQLite Data File

```sh
python3 pain001/__main__.py \
  --xml_message_type "pain.001.001.03" \
  --xml_template_file_path "templates/pain.001.001.03/template.xml" \
  --xsd_schema_file_path "templates/pain.001.001.03/pain.001.001.03.xsd" \
  --data_file_path "templates/pain.001.001.03/template.db"
```

> **Note:** The XML file that **Pain001** generates will automatically be
validated against the XSD template file before the new XML file is saved. If
the validation fails, **Pain001** will stop running and display an error
message in your terminal.

### Embedded in an Application

To embed **Pain001** in a new or existing application, import the main function
and use it in your code.

Here's an example:

```python
from pain001 import main

if __name__ == '__main__':
  xml_message_type = 'pain.001.001.03'
  xml_template_file_path = 'template.xml'
  xsd_schema_file_path = 'schema.xsd'
  data_file_path = 'data.csv'
  main(xml_message_type, xml_template_file_path, xsd_schema_file_path, data_file_path)
```

### Validation

To validate the generated XML file against a given xsd schema, use the
following method:

```python
from pain001.core import validate_xml_against_xsd

xml_message_type = 'pain.001.001.03'
xml_file = 'generated.xml'
xsd_file = 'schema.xsd'

is_valid = validate_xml_against_xsd(
  xml_message_type,
  xml_file,
  xsd_file
)
print(f"XML validation result: {is_valid}")
```

## Documentation 📖

> **Info:** Do check out our [website][0] for comprehensive documentation.

### Supported messages

This section gives access to the documentation related to the ISO 20022
message definitions supported by **Pain001**.

#### Bank-to-Customer Cash Management

Set of messages used to request and provide account information for
reconciliation and cash positioning between an account servicer and its
customer.

| Status | Message type | Name |
|---|---|---|
| ⏳ | camt.052.001.10 | Bank-to-Customer Account Statement |
| ⏳ | camt.060.001.10 | Customer Account Notification |
| ⏳ | camt.054.001.10 | Customer Account Statement Request |
| ⏳ | camt.053.001.10 | Customer Account Identification |

#### Payments Clearing and Settlement

Set of messages used between financial institutions for the clearing and
settlement of payment transactions.

| Status | Message type | Name |
|---|---|---|
| ⏳ | pacs.002.001.12 | Credit Transfer Notification |
| ⏳ | pacs.003.001.09 | Direct Debit Initiation |
| ⏳ | pacs.004.001.11 | Direct Debit Reversal |
| ⏳ | pacs.007.001.11 | Customer Direct Debit Confirmation |
| ⏳ | pacs.008.001.10 | Credit Transfer Initiation |
| ⏳ | pacs.009.001.10 | Credit Transfer Reversal |
| ⏳ | pacs.010.001.05 | Account Identification |
| ⏳ | pacs.028.001.05 | Account Statement Request |

#### Payments Initiation

Set of messages exchanged between a debtor (or buyer) and its bank or
between a creditor (or seller) and its bank to initiate, collect, manage
and monitor payments.

| Status | Message type | Name |
|---|---|---|
| ✅ | [pain.001.001.03][pain.001.001.03] | Customer Credit Transfer Initiation |
| ⏳ | pain.001.001.04 | Customer Direct Debit Initiation |
| ⏳ | pain.001.001.05 | Customer Direct Debit Reversal |
| ⏳ | pain.001.001.06 | Customer Credit Transfer Reversal |
| ⏳ | pain.001.001.07 | Customer Account Notification |
| ⏳ | pain.001.001.08 | Customer Account Statement |
| ✅ | [pain.001.001.09][pain.001.001.09] | Customer Credit Transfer Initiation |
| ⏳ | pain.001.001.10 | Customer Account Closure Request |
| ⏳ | pain.001.001.11 | Customer Account Change Request |

## License 📝

The project is licensed under the terms of both the MIT license and the
Apache License (Version 2.0).

- [Apache License, Version 2.0][1]
- [MIT license][2]

## Contribution 🤝

We welcome contributions to **Pain001**. Please see the
[contributing instructions][4] for more information.

Unless you explicitly state otherwise, any contribution intentionally
submitted for inclusion in the work by you, as defined in the
Apache-2.0 license, shall be dual licensed as above, without any
additional terms or conditions.

## Acknowledgements 💙

We would like to extend a big thank you to all the awesome contributors
of [Pain001][5] for their help and support.

[0]: https://Pain001.co
[1]: https://opensource.org/license/apache-2-0/
[2]: http://opensource.org/licenses/MIT
[3]: https://github.com/sebastienrousseau/pain001
[4]: https://github.com/sebastienrousseau/pain001/blob/main/CONTRIBUTING.md
[5]: https://github.com/sebastienrousseau/pain001/graphs/contributors
[6]: https://codecov.io/github/sebastienrousseau/pain001?branch=main

[pain.001.001.03]: https://www.pain001.com/pain.001.001.03/index.html
[pain.001.001.09]: https://www.pain001.com/pain.001.001.09/index.html

[banner]: https://kura.pro/pain001/images/banners/banner-pain001.svg 'Pain001, A Python Library for Automating ISO 20022-Compliant Payment Files Using CSV Or SQlite Data Files.'
[codecov-badge]: https://img.shields.io/codecov/c/github/sebastienrousseau/pain001?style=for-the-badge&token=AaUxKfRiou 'Codecov badge'
[license-badge]: https://img.shields.io/pypi/l/pain001?style=for-the-badge 'License badge'
[pypi-badge]: https://img.shields.io/pypi/pyversions/pain001.svg?style=for-the-badge 'PyPI badge'
