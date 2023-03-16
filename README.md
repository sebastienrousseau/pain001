<!-- markdownlint-disable MD033 MD041 -->

<img src="https://raw.githubusercontent.com/sebastienrousseau/vault/main/assets/pain001/icon/ico-pain001.svg" alt="pain001 logo" width="261" align="right" />

<!-- markdownlint-enable MD033 MD041 -->

# Python Pain001

![pain001 banner][banner]

[![PyPI][pypi-badge]][3] [![License][license-badge]][1]

## Overview 📖

Pain001 is a powerful library that allows you to generate a Customer-to
-Bank Credit Transfer payload in the pain.001.001.03 format from a CSV
file. With Pain001, you can easily create professional-looking payment
data in just a few simple steps.

## Features ✨

- Pain001 is a command-line interface (CLI) that when called, generates
  a Customer-to-Bank Credit Transfer payload in a pain.001.001.03 format
  from a CSV file.
- Pain001 uses an XML template file and maps CSV column names to XML
  element tags to generate the XML file.
- The CSV file must contain the payment data in the required format, and
  the XML template file must exist. Otherwise, the function will raise a
  FileNotFoundError.
- Pain001 includes several features, including batch booking, generation
  of an end-to-end payment ID, and support for multiple currencies.

## Getting Started 🚀

It takes just a few seconds to get up and running with `Pain001`.

### Installation

To install Pain001, run `pip install pain001`

### Documentation

> ℹ️ **Info:** Do check out our [website][0] for more information.

## Usage 📖

With `Pain001`, you can quickly and easily generate a Customer-to-Bank
Credit Transfer payload in the pain.001.001.03 format from a CSV file.
To get started, simply call the main function with the path of your XML
template file and the path of your CSV file containing the payment data.

Here's an example of how to use Pain001:

```python
from pain001 import main

if __name__ == '__main__':
  xml_file_path = 'template.xml'
  csv_file_path = 'data.csv'
  main(xml_file_path, csv_file_path)
```

Once you have your script set up, you can run it from the command line
using the following command:

```bash
python -m pain001 ./templates/template.xml ./templates/template.csv
```

For more information on Pain001 features, including batch booking and
end-to-end payment ID generation, please see the Pain001 usage page.

## License 📝

The project is licensed under the terms of both the MIT license and the
Apache License (Version 2.0).

- [Apache License, Version 2.0][1]
- [MIT license][2]

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

[0]: https://pain001.co
[1]: https://opensource.org/license/apache-2-0/
[2]: http://opensource.org/licenses/MIT
[3]: https://github.com/sebastienrousseau/pain001
[4]: https://github.com/sebastienrousseau/pain001/blob/main/CONTRIBUTING.md
[5]: https://github.com/sebastienrousseau/pain001/graphs/contributors
[banner]: https://raw.githubusercontent.com/sebastienrousseau/vault/main/assets/pain001/title/title-pain001.svg
[license-badge]: https://img.shields.io/pypi/l/pain001?style=for-the-badge 'License badge'
[pypi-badge]: https://img.shields.io/pypi/pyversions/pain001.svg?style=for-the-badge 'PyPI badge'
