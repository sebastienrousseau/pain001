<!-- markdownlint-disable MD033 MD041 -->

<img src="https://kura.pro/pain001/images/logos/pain001.svg" alt="pain001 logo" width="261" align="right" />

<!-- markdownlint-enable MD033 MD041 -->

# Python pain001

![pain001 banner][banner]

[![PyPI][pypi-badge]][3] [![License][license-badge]][1] [![Codecov][codecov-badge]][6]

## Overview 📖

The pain001 Python package is a CLI tool that makes it easy to automate
the creation of ISO 20022 compliant payment files (XML PAIN.001.03)
directly from a CSV file. With pain001, you can easily create payment
transactions files in just a few simple steps.

## Features ✨

- **Simplified file creation:** The library generates payment files in
  the PAIN.001.001.03 format quickly and efficiently.
- **Ensuring the Highest Quality and Compliance:** The library
  guarantees that all created payment files follow ISO 20022 standards.
- **Enhanced efficiency:** The Pain001 library automates the creation of
  PAIN.001.001.03 files, freeing developers to focus on other aspects of
  their projects.
- **Improved accuracy:** By providing precise data, the library reduces
  errors in payment file creation.
- **Seamless integration:** As a Python package, the pain001 library is
  compatible with various Python-based applications and easily
  integrates into any existing projects.
- **Cross-border compatibility:** The library supports both Single Euro
  Payments Area (SEPA) and non-SEPA credit transfers, making it
  versatile for use in different countries and regions.
- **Time-saving:** The automated file creation process reduces the time
  spent on manual data entry and file generation, increasing overall
  productivity.
- **Scalable solution:** The Pain001 library can handle varying volumes
  of payment files, making it suitable for businesses of different sizes
  and transaction volumes.
- **Customisable:** The library allows developers to customise the
  output, making it adaptable to specific business requirements and
  preferences.

## Supported messages 📬

This section gives access to the documentation related to the ISO 20022
message definitions supported by `pain001`.

### Bank-to-Customer Cash Management

Set of messages used to request and provide account information for
reconciliation and cash positioning between an account servicer and its
customer.

- [ ] **camt.052.001.10**: [BankToCustomerAccountReportV10][10]
- [ ] **camt.053.001.10**: [BankToCustomerStatementV10][11]
- [ ] **camt.054.001.10**: [BankToCustomerDebitCreditNotificationV10][12]
- [ ] **camt.060.001.06**: [BankToCustomerAccountReportV06][13]

### Payments Clearing and Settlement

Set of messages used between financial institutions for the clearing and
settlement of payment transactions.

- [ ] **pacs.002.001.12**: [FIToFIPaymentStatusReportV12][14]
- [ ] **pacs.003.001.09**: [FIToFICustomerCreditTransferV09][15]
- [ ] **pacs.004.001.11**: [FIToFICustomerDirectDebitV11][16]
- [ ] **pacs.007.001.11**: [FIToFIPaymentReversalV11][17]
- [ ] **pacs.008.001.10**: [CustomerPaymentStatusReportV10][18]
- [ ] **pacs.009.001.10**: [CustomerDirectDebitInitiationV10][19]
- [ ] **pacs.010.001.05**: [CustomerPaymentReversalV05][20]
- [ ] **pacs.028.001.05**: [FIToFIPaymentCancellationRequestV05][21]

### Payments Initiation

Set of messages exchanged between a debtor (or buyer) and its bank or
between a creditor (or seller) and its bank to initiate, collect, manage
and monitor payments.

- [ ] **pain.001.001.11**: [CustomerCreditTransferInitiationV11][22]
- [ ] **pain.002.001.12**: [CustomerDirectDebitInitiationV12][23]
- [ ] **pain.007.001.11**: [CustomerPaymentReversalV11][24]
- [ ] **pain.008.001.10**: [CustomerPaymentStatusReportV10][25]
- [x] **pain.001.001.03**: [CustomerCreditTransferInitiationV3][26]

## Getting Started 🚀

It takes just a few seconds to get up and running with `pain001`.

### Installation

To install pain001, run `pip install pain001`

### Documentation

> ℹ️ **Info:** Do check out our [website][0] for more information.

## Usage 📖

`pain001` can be used in two ways:

### Command Line Interface (CLI)

After installation, you can run `pain001` directly from the command
line. Simply call the main function with the path of your XML template
file, XSD schema file and the path of your CSV file containing the
payment data.

```bash
python3 -m pain001 ./templates/template.xml ./templates/template.xsd ./templates/template.csv
```

### Embedded in an Application

To embed pain001 in a new or existing application, import the main
function and use it in your code.

Here's an example:

```python
from pain001 import main

if __name__ == '__main__':
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

xml_file = 'generated.xml'
xsd_file = 'schema.xsd'

is_valid = validate_xml_against_xsd(xml_file, xsd_file)
print(f"XML validation result: {is_valid}")
```

## License 📝

The project is licensed under the terms of both the MIT license and the
Apache License (Version 2.0).

- [Apache License, Version 2.0][1]
- [MIT license][2]

## Contribution 🤝

We welcome contributions to `pain001`. Please see the
[contributing instructions][4] for more information.

Unless you explicitly state otherwise, any contribution intentionally
submitted for inclusion in the work by you, as defined in the
Apache-2.0 license, shall be dual licensed as above, without any
additional terms or conditions.

## Acknowledgements 💙

We would like to extend a big thank you to all the awesome contributors
of [pain001][5] for their help and support.

[0]: https://pain001.co
[1]: https://opensource.org/license/apache-2-0/
[2]: http://opensource.org/licenses/MIT
[3]: https://github.com/sebastienrousseau/pain001
[4]: https://github.com/sebastienrousseau/pain001/blob/main/CONTRIBUTING.md
[5]: https://github.com/sebastienrousseau/pain001/graphs/contributors
[6]: https://codecov.io/github/sebastienrousseau/pain001?branch=main

[10]: docs/bank-to-customer-cash-management/messages/banktocustomeraccountreportv10/camt.052.001.10.md
[11]: docs/bank-to-customer-cash-management/messages/banktocustomerstatementv10/camt.053.001.10.md
[12]: docs/bank-to-customer-cash-management/messages/banktocustomerdebitcreditnotificationv10/camt.054.001.10.md
[13]: docs/bank-to-customer-cash-management/messages/accountreportingrequestv06/camt.060.001.06.md
[14]: docs/payments-clearing-and-settlement/messages/fitofipaymentstatusreportv12/pacs.002.001.12.md
[15]: docs/payments-clearing-and-settlement/messages/fitoficustomerdirectdebitv09/pacs.003.001.09.md
[16]: docs/payments-clearing-and-settlement/messages/paymentreturnv11/pacs.004.001.11.md
[17]: docs/payments-clearing-and-settlement/messages/fitofipaymentreversalv11/pacs.007.001.11.md
[18]: docs/payments-clearing-and-settlement/messages/fitoficustomercredittransferv10/pacs.008.001.10.md
[19]: docs/payments-clearing-and-settlement/messages/financialinstitutioncredittransferv10/pacs.009.001.10.md
[20]: docs/payments-clearing-and-settlement/messages/financialinstitutiondirectdebitv05/pacs.010.001.05.md
[21]: docs/payments-clearing-and-settlement/messages/fitofipaymentstatusrequestv05/pacs.028.001.05.md
[22]: docs/payments-initiation/messages/customercredittransferinitiationv11/pain.001.001.11.md
[23]: docs/payments-initiation/messages/customerpaymentstatusreportv12/pain.002.001.12.md
[24]: docs/payments-initiation/messages/customerpaymentreversalv11/pain.007.001.11.md
[25]: docs/payments-initiation/messages/customerdirectdebitinitiationv10/pain.008.001.10.md
[26]: docs/payments-initiation/messages/customercredittransferinitiationv03/pain.001.001.03.md

[banner]: https://kura.pro/pain001/images/titles/title-pain001.svg
[codecov-badge]: https://img.shields.io/codecov/c/github/sebastienrousseau/pain001?style=for-the-badge&token=AaUxKfRiou 'Codecov badge'
[license-badge]: https://img.shields.io/pypi/l/pain001?style=for-the-badge 'License badge'
[pypi-badge]: https://img.shields.io/pypi/pyversions/pain001.svg?style=for-the-badge 'PyPI badge'
