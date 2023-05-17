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

"""The setup.py file for Python pain001."""

from setuptools import setup


LONG_DESCRIPTION = """
The `pain001` Python package is a CLI tool that makes it easy to
automate the creation of ISO20022-compliant payment files directly from
a CSV file.

With `pain001`, you can easily create payment transactions files in just
a few simple steps.

The library supports both **Single Euro Payments Area (SEPA)** and
**non-SEPA credit transfers**, making it versatile for use in different
countries and regions.

The following **ISO 20022 Payment Initiation message types** are
currently supported:

- **pain.001.001.03** - Customer Credit Transfer Initiation

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

- **pain.001.001.09** - Customer Credit Transfer Initiation

This message format is part of the ISO 20022 standard and is commonly
used for SEPA Credit Transfers within the Single Euro Payments Area. It
enables the transmission of credit transfer instructions from the
originator to the originator's bank. The message includes essential
information such as the originator's and beneficiary's details, payment
amounts, payment references, and other transaction-related information
required for processing the credit transfers.
""".strip()

SHORT_DESCRIPTION = """pain001 is a Python library that makes it easy to
automate the creation of ISO20022-compliant payment files directly from
a CSV file.""".strip()

DEPENDENCIES = [
    'xmlschema>=1.8.0'
]

TEST_DEPENDENCIES = [
    'xmlschema>=1.8.0',
]

VERSION = '0.0.14'
URL = 'https://github.com/sebastienrousseau/pain001'

setup(
    name='pain001',
    version=VERSION,
    description=SHORT_DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    url=URL,

    author='Sebastien Rousseau',
    author_email='sebastian.rousseau@gmail.com',
    license='Apache Software License',

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Financial and Insurance Industry',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Operating System :: OS Independent',
        'Operating System :: POSIX',
        'Operating System :: MacOS',
        'Operating System :: Unix',
    ],

    keywords='iso 20022 pain.001 credit transfer financial banking \
        payments csv sepa',

    packages=['pain001'],


    install_requires=DEPENDENCIES,
    tests_require=TEST_DEPENDENCIES,
)
