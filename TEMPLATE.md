# Python Pain001 [![PyPI](https://img.shields.io/pypi/pyversions/pain001.svg?style=for-the-badge)](https://github.com/sebastienrousseau/pain001)

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
  the XML template file must exist. Otherwise, the function will raise a FileNotFoundError.
- Pain001 includes several features, including batch booking, generation
  of an end-to-end payment ID, and support for multiple currencies.

## Changelog 📚
