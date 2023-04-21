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
The pain001 library is a Python package that generates a Customer-to-
Bank Credit Transfer payload in the pain.001.001.03 format from a CSV
file.

The package is named after the standard file format for SEPA and non-
SEPA Credit Transfer, which is the Pain (payment initiation) format
001.001.03.

The pain001 library provides a convenient way for developers to create
payment files in this format.
""".strip()

SHORT_DESCRIPTION = """
pain001 is a Python library that makes it easy to automate the creation
of ISO 20022 compliant payment files (XML PAIN.001.03) directly from a
CSV file.
""".strip()

DEPENDENCIES = [
    'python-dateutil>=2.8.2',
    'xmlschema>=1.8.0',
]

TEST_DEPENDENCIES = [
    'xmlschema>=1.8.0',
]

VERSION = '0.0.13'
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
