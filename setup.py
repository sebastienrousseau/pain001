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

with open("README.md") as f:
    LONG_DESCRIPTION = f.read()

SHORT_DESCRIPTION = """
Pain001, A Python Library for Automating ISO 20022-Compliant Payment Files
Using CSV Or SQlite Data Files.
""".strip()

DEPENDENCIES = [
    "click==8.1.3",
    "defusedxml==0.7.1",
    "rich==13.4.2",
    "xmlschema==2.3.1",
]

TEST_DEPENDENCIES = [
    "pytest>=7.3.2",
]

NAME = "pain001"
URL = "https://github.com/sebastienrousseau/pain001"
VERSION = "0.0.22"

setup(
    name=NAME,
    version=VERSION,
    description=SHORT_DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url=URL,
    author="Sebastien Rousseau",
    author_email="sebastian.rousseau@gmail.com",
    license="Apache Software License",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: MacOS",
        "Operating System :: OS Independent",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="""
    pain001,iso20022,payment-processing,automate-payments,sepa,financial,banking-payments,csv,sqlite
    """,
    packages=["pain001"],
    install_requires=DEPENDENCIES,
    tests_require=TEST_DEPENDENCIES,
)
