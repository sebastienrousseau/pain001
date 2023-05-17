<!-- markdownlint-disable MD033 MD041 -->

<img
  src="https://kura.pro/pain001/images/logos/pain001.svg"
  alt="Pain001 logo"
  height="261"
  width="261"
  align="right"
/>

<!-- markdownlint-enable MD033 MD041 -->

# Python Pain001

![Pain001 banner][banner]

[![PyPI][pypi-badge]][3] [![License][license-badge]][1]
[![Codecov][codecov-badge]][6]

## Overview 📖

The `Pain001` Python package is a CLI tool that makes it easy to
automate the creation of ISO20022-compliant payment files directly from
a CSV file.

With `Pain001`, you can easily create payment transactions files in just
a few simple steps.

The library supports both **Single Euro Payments Area (SEPA)** and
**non-SEPA credit transfers**, making it versatile for use in different
countries and regions.

## ISO 20022 Payment Initiation Message Types 📨

The following **ISO 20022 Payment Initiation message types** are
currently supported:

* **pain.001.001.03** - Customer Credit Transfer Initiation

This message is used to transmit credit transfer instructions from the
originator (the party initiating the payment) to the originator's bank.
The message supports both bulk and single payment instructions, allowing
for the transmission of multiple payments in a batch or individual
payments separately. The pain.001.001.03 message format is part of the
ISO 20022 standard and is commonly used for SEPA Credit Transfers within
the Single Euro Payments Area. It includes relevant information such as
the originator's and beneficiary's details, payment amounts, payment
references, and other transaction-related information required for
processing the credit transfers.

* **pain.001.001.09** - Customer Credit Transfer Initiation

This message format is part of the ISO 20022 standard and is commonly
used for SEPA Credit Transfers within the Single Euro Payments Area. It
enables the transmission of credit transfer instructions from the
originator to the originator's bank. The message includes essential
information such as the originator's and beneficiary's details, payment
amounts, payment references, and other transaction-related information
required for processing the credit transfers.

More message types will be added in the future. Please refer to the
[supported messages section][supported-messages] section for more
details.

## Features ✨

* **Simplify file creation:** The library generates payment files in
  the desired format quickly and efficiently.
* **Ensure the highest quality and compliance:** The library
  guarantees that all created payment files follow the ISO 20022
  standards.
* **Enhance efficiency:** The Pain001 library automates the creation of
  Payment Initiation message files, freeing developers to focus on other
  aspects of their projects and simplifying the payment process for
  users.
* **Improve accuracy:** By providing precise data, the library reduces
  errors in payment file creation and processing.
* **Seamless integration:** As a Python package, the Pain001 library is
  compatible with various Python-based applications and easily
  integrates into any existing projects or workflows.
* **Cross-border compatibility:** The library supports both Single Euro
  Payments Area (SEPA) and non-SEPA credit transfers, making it
  versatile for use in different countries and regions.
* **Time-saving:** The automated file creation process reduces the time
  spent on manual data entry and file generation, increasing overall
  productivity.
* **Scalable solution:** The Pain001 library can handle varying volumes
  of payment files, making it suitable for businesses of different sizes
  and transaction volumes.
* **Customisable:** The library allows developers to customise the
  output, making it adaptable to specific business requirements and
  preferences.

### Supported messages

This section gives access to the documentation related to the ISO 20022
message definitions supported by `Pain001`.

#### Bank-to-Customer Cash Management

Set of messages used to request and provide account information for
reconciliation and cash positioning between an account servicer and its
customer.

| Status | Message type | Name |
|---|---|---|
| ⏳ | [camt.052.001.10] | Bank-to-Customer Account Statement |
| ⏳ | [camt.060.001.10] | Customer Account Notification |
| ⏳ | [camt.054.001.10] | Customer Account Statement Request |
| ⏳ | [camt.053.001.10] | Customer Account Identification |

#### Payments Clearing and Settlement

Set of messages used between financial institutions for the clearing and
settlement of payment transactions.

| Status | Message type | Name |
|---|---|---|
| ⏳ | [pacs.002.001.12] | Credit Transfer Notification |
| ⏳ | [pacs.003.001.09] | Direct Debit Initiation |
| ⏳ | [pacs.004.001.11] | Direct Debit Reversal |
| ⏳ | [pacs.007.001.11] | Customer Direct Debit Confirmation |
| ⏳ | [pacs.008.001.10] | Credit Transfer Initiation |
| ⏳ | [pacs.009.001.10] | Credit Transfer Reversal |
| ⏳ | [pacs.010.001.05] | Account Identification |
| ⏳ | [pacs.028.001.05] | Account Statement Request |

#### Payments Initiation

Set of messages exchanged between a debtor (or buyer) and its bank or
between a creditor (or seller) and its bank to initiate, collect, manage
and monitor payments.

| Status | Message type | Name |
|---|---|---|
| ✅ | [pain.001.001.03][pain.001.001.03] | Customer Credit Transfer Initiation |
| ⏳ | [pain.001.001.04][pain.001.001.04] | Customer Direct Debit Initiation |
| ⏳ | [pain.001.001.05][pain.001.001.05] | Customer Direct Debit Reversal |
| ⏳ | [pain.001.001.06][pain.001.001.06] | Customer Credit Transfer Reversal |
| ⏳ | [pain.001.001.07][pain.001.001.07] | Customer Account Notification |
| ⏳ | [pain.001.001.08][pain.001.001.08] | Customer Account Statement |
| ✅ | [pain.001.001.09][pain.001.001.09] | Customer Credit Transfer Initiation |
| ⏳ | [pain.001.001.10][pain.001.001.10] | Customer Account Closure Request |
| ⏳ | [pain.001.001.11][pain.001.001.11] | Customer Account Change Request |

## Getting Started 🚀

It takes just a few seconds to get up and running with `Pain001`.

### Installation

To install Pain001, run `pip install pain001`

### Documentation

> ℹ️ **Info:** Do check out our [website][0] for more information.

## Usage 📖

`Pain001` can be used in two ways:

### Command Line Interface (CLI)

After installation, you can run `pain001` directly from the command
line. Simply call the main function with the path of your XML template
file, XSD schema file and the path of your CSV file containing the
payment data.

#### Example pain.001.001.03

```bash
python3 -m \pain001 "pain.001.001.03" \
  ./templates/pain.001.001.03/template.xml \
  ./templates/pain.001.001.03/pain.001.001.03.xsd \
  ./templates/pain.001.001.03/template.csv

```

#### Example pain.001.001.09

```bash
python3 -m \pain001 "pain.001.001.09" \
  ./templates/pain.001.001.09/template.xml \
  ./templates/pain.001.001.09/pain.001.001.09.xsd \
  ./templates/pain.001.001.09/template.csv

```

### Embedded in an Application

To embed Pain001 in a new or existing application, import the main
function and use it in your code.

Here's an example:

```python
from pain001 import main

if __name__ == '__main__':
  xml_message_type = 'pain.001.001.03'
  xml_file_path = 'template.xml'
  xsd_file_path = 'schema.xsd'
  csv_file_path = 'data.csv'
  main(xml_file_path, xsd_file_path, csv_file_path)
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

## License 📝

The project is licensed under the terms of both the MIT license and the
Apache License (Version 2.0).

* [Apache License, Version 2.0][1]
* [MIT license][2]

## Contribution 🤝

We welcome contributions to `Pain001`. Please see the
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

[camt.052.001.10]: docs/bank-to-customer-cash-management/messages/camt.052.001.10/README.md
[camt.060.001.10]: docs/bank-to-customer-cash-management/messages/camt.053.001.10/README.md
[camt.054.001.10]: docs/bank-to-customer-cash-management/messages/camt.054.001.10/README.md
[camt.053.001.10]: docs/bank-to-customer-cash-management/messages/camt.053.001.10/README.md
[pacs.002.001.12]: docs/payments-clearing-and-settlement/messages/pacs.002.001.12/README.md
[pacs.003.001.09]: docs/payments-clearing-and-settlement/messages/pacs.003.001.09/README.md
[pacs.004.001.11]: docs/payments-clearing-and-settlement/messages/pacs.004.001.11/README.md
[pacs.007.001.11]: docs/payments-clearing-and-settlement/messages/pacs.007.001.11/README.md
[pacs.008.001.10]: docs/payments-clearing-and-settlement/messages/pacs.008.001.10/README.md
[pacs.009.001.10]: docs/payments-clearing-and-settlement/messages/pacs.009.001.10/README.md
[pacs.010.001.05]: docs/payments-clearing-and-settlement/messages/pacs.010.001.05/README.md
[pacs.028.001.05]: docs/payments-clearing-and-settlement/messages/pacs.028.001.05/README.md
[pain.001.001.03]: docs/payments-initiation/messages/pain.001.001.03/README.md
[pain.001.001.04]: docs/payments-initiation/messages/pain.001.001.04/README.md
[pain.001.001.05]: docs/payments-initiation/messages/pain.001.001.05/README.md
[pain.001.001.06]: docs/payments-initiation/messages/pain.001.001.06/README.md
[pain.001.001.07]: docs/payments-initiation/messages/pain.001.001.07/README.md
[pain.001.001.08]: docs/payments-initiation/messages/pain.001.001.08/README.md
[pain.001.001.09]: docs/payments-initiation/messages/pain.001.001.09/README.md
[pain.001.001.10]: docs/payments-initiation/messages/pain.001.001.10/README.md
[pain.001.001.11]: docs/payments-initiation/messages/pain.001.001.11/README.md

[banner]: https://kura.pro/pain001/images/titles/title-pain001.svg 'Pain001'
[codecov-badge]: https://img.shields.io/codecov/c/github/sebastienrousseau/pain001?style=for-the-badge&token=AaUxKfRiou 'Codecov badge'
[license-badge]: https://img.shields.io/pypi/l/pain001?style=for-the-badge 'License badge'
[pypi-badge]: https://img.shields.io/pypi/pyversions/pain001.svg?style=for-the-badge 'PyPI badge'
[supported-messages]: #supported-messages 'Supported messages'
