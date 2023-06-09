# Copyright (C) 2023 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""The setup.py file for Python Pain001."""

from setuptools import setup

LONG_DESCRIPTION = """
**Pain001** is a Python Library for Automating ISO 20022-Compliant Payment
Files Using CSV Data.

**Pain001** offers a streamlined solution for reducing complexity and costs
associated with payment processing. By providing a simple and efficient method
to create ISO 20022-compliant payment files, it eliminates the manual effort of
file creation and validation. This not only saves valuable time and resources
but also minimizes the risk of errors, ensuring accurate and seamless payment
processing.

If you are seeking to simplify and automate your payment processing, consider
leveraging the capabilities of **Pain001**.

## Features ✨

- **Easy to use:** The library is easy to use and requires minimal coding
knowledge, making it suitable for both developers and non-developers.
- **Open-source**: The library is open-source and free to use, making it
accessible to everyone.
- **Secure**: The library is secure and does not store any sensitive data,
ensuring that all information remains confidential.
- **Customizable**: The library allows developers to customize the output,
making it adaptable to specific business requirements and preferences.
- **Scalable solution**: The **Pain001** library can handle varying volumes of
payment files, making it suitable for businesses of different sizes and
transaction volumes.
- **Time-saving**: The automated file creation process reduces the time spent
on manual data entry and file generation, increasing overall productivity.
- **Seamless integration**: As a Python package, the **Pain001** library is
compatible with various Python-based applications and easily integrates into
any existing projects or workflows.
- **Cross-border compatibility**: The library supports both Single Euro
Payments Area (SEPA) and non-SEPA credit transfers, making it versatile for
use in different countries and regions.
- **Improve accuracy** by providing precise data, the library reduces errors in
payment file creation and processing.
- **Enhance efficiency** by automating the creation of Payment Initiation
message files
- **Accelerate payment file creation** by automating the process and reducing
the time required to create payment files.
- **Guarantee the highest quality and compliance** by validating all payment
files to meet the ISO 20022 standards.
- **Provide flexibility and choice to migrate to any supported ISO 20022
messaging standard definitions** by simplifying the message creation process
and providing a standardized format for payment files.

## Installation

It takes just a few seconds to get up and running with **Pain001**. Open your
terminal and run the following command:

```sh
pip install pain001
```

## Usage

After installation, you can run **Pain001** directly from the command line.
Simply call the main function with the path of your XML template file, XSD
schema file and the path of your CSV file containing the payment data.

Once you have installed **Pain001**, you can generate and validate XML files
using the following command:

```sh
python3 -m pain001 \
    <xml_message_type> \
    <xml_file_path> \
    <xsd_file_path> \
    <csv_file_path>
```

## Arguments

When running **Pain001**, you will need to specify four arguments:

- `xml_message_type`: This is the type of XML message you want to generate.
Currently, the valid options are:
    - pain.001.001.03
    - pain.001.001.09
- `xml_file_path`: This is the path to the XML template file you are using.
- `xsd_file_path`: This is the path to the XSD template file you are using.
- `csv_file_path`: This is the path to the CSV data file you want to convert to
XML.

## Examples

Here are a few example on how to use **Pain001** to generate a
pain.001.001.03 XML file from a CSV data file:

### Via the Command Line

```sh
python3 -m pain001 \
    pain.001.001.03 \
    /path/to/your/pain.001.001.03.xml \
    /path/to/your/pain.001.001.03.xsd \
    /path/to/your/pain.001.001.03.csv
```

**Note:** The XML file that **Pain001** generates will be automatically
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
    xml_file_path = 'template.xml'
    xsd_file_path = 'schema.xsd'
    csv_file_path = 'data.csv'
    main(xml_message_type, xml_file_path, xsd_file_path, csv_file_path)
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

> ℹ️ **Info:** Do check out our <https://pain001.com> for more information on
the Pain001 documentation.
""".strip()

SHORT_DESCRIPTION = """
Pain001 is a Python Library for Automating ISO 20022-Compliant Payment Files
Using CSV Data.""".strip()

DEPENDENCIES = ["xmlschema>=2.3.0"]

TEST_DEPENDENCIES = ["xmlschema>=2.3.0", "pytest>=7.3.1"]

VERSION = "0.0.19"

URL = "https://github.com/sebastienrousseau/pain001"

setup(
    name="pain001",
    version=VERSION,
    description=SHORT_DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    url=URL,
    author="Sebastien Rousseau",
    author_email="sebastian.rousseau@gmail.com",
    license="Apache Software License",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
        "Operating System :: POSIX",
        "Operating System :: MacOS",
        "Operating System :: Unix",
    ],
    keywords="""
    Pain001, finance python library, ISO 20022, payment files, payment
    processing, automate payments, ISO 20022-compliant, SWIFT, SEPA, payment
    initiation messages,
    """,
    packages=["pain001"],
    install_requires=DEPENDENCIES,
    tests_require=TEST_DEPENDENCIES,
)
