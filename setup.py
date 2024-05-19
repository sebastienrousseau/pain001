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

from pathlib import Path
from setuptools import setup, find_packages

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="pain001",
    version="0.0.25",
    description="Pain001, A Python Library for Automating ISO 20022-Compliant Payment Files Using CSV Or SQLite Data Files.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Sebastien Rousseau",
    author_email="sebastian.rousseau@gmail.com",
    url="https://pain001.com",
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
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="pain001,iso20022,payment-processing,automate-payments,sepa,financial,banking-payments,csv,sqlite",
    packages=find_packages(exclude=["docs", "tests*"]),
    install_requires=[
        "click==8.1.7",
        "colorama==0.4.6",
        "datetime==5.5",
        "defusedxml==0.7.1",
        "elementpath==4.4.0",
        "jinja2==3.1.4",
        "markdown-it-py==3.0.0",
        "markupsafe==2.1.5",
        "mdurl==0.1.2",
        "pygments==2.18.0",
        "rich==13.7.1",
        "setuptools==69.5.1",
        "xmlschema==3.3.1",
    ],
    extras_require={
        "dev": [
            "pytest==8.2.0",
            "pytest-cov==5.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "pain001=pain001.cli:main",
        ],
    },
    python_requires=">=3.9,<3.13",
    setup_requires=["pytest-runner"],
    tests_require=["pytest"],
    test_suite="tests",
)
