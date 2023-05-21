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

## Installation

To install **Pain001**, run this command in your terminal:

```sh
pip install pain001
```

## Usage

To use **Pain001**, run this command in your terminal:

```sh
python3 -m pain001 \
    <xml_message_type> \
    <xml_file_path> \
    <xsd_file_path> \
    <csv_file_path>
```

## Arguments:

- `xml_message_type`: The type of XML message. The current valid values are:
    - pain.001.001.03 and
    - pain.001.001.09
- `xml_file_path`: The path to the XML template file.
- `xsd_file_path`: The path to the XSD template file.
- `csv_file_path`: The path to the CSV data file.

## Example:

To generate a pain.001.001.03 XML file from the CSV data file you can run the
following command in your terminal:

```sh
python3 -m pain001 \
    pain.001.001.03 \
    /path/to/your/pain.001.001.03.xml \
    /path/to/your/pain.001.001.03.xsd \
    /path/to/your/pain.001.001.03.csv
```

Note: The generated XML file will be validated against the XSD template
file before being saved. If the validation fails, the program will exit
with an error message.

For more information, please visit the project's GitHub page at:
<https://github.com/sebastienrousseau/pain001>.
""".strip()

SHORT_DESCRIPTION = """
Pain001 is a Python Library for Automating ISO 20022-Compliant Payment Files
Using CSV Data.""".strip()

DEPENDENCIES = ["xmlschema>=2.3.0"]

TEST_DEPENDENCIES = ["xmlschema>=2.3.0", "pytest>=7.3.1"]

VERSION = "0.0.18"

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
