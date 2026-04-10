.. Pain001 documentation master file

========================================
Pain001: ISO 20022-Compliant Payment Files
========================================

Welcome to **Pain001** — a powerful Python library for automating ISO 20022-compliant payment file creation.

Pain001 simplifies payment processing by generating standardized payment initiation files (pain.001) from CSV files, SQLite databases, or Python data structures, with mandatory validation and enterprise-grade reliability.

.. grid:: 2
   :gutter: 2

   .. grid-item-card:: 🚀 Quick Start
      :link: installation
      :link-type: doc

      Get up and running in minutes with pip install and a simple example.

   .. grid-item-card:: 📚 User Guide
      :link: usage
      :link-type: doc

      Learn how to use Pain001 with CSV data, databases, and custom configurations.

   .. grid-item-card:: ⚙️ API Reference
      :link: modules
      :link-type: doc

      Complete API documentation with all classes, functions, and methods.

   .. grid-item-card:: 🔧 Configuration
      :link: configuration
      :link-type: doc

      Configure Pain001 for your specific payment processing needs.

Key Features
============

.. rst-class:: feature-grid

* **🏦 ISO 20022 Compliance** — Generate files compliant with pain.001.001.03 through pain.001.001.11 and pain.008.001.02
* **📊 Multiple Data Sources** — Support for CSV files, SQLite databases, and Python data structures
* **✅ Automatic Validation** — Built-in XSD schema validation for generated XML files
* **🔒 Secure by Design** — Uses defusedxml to prevent XXE attacks and SQL injection protection
* **🧪 Fully Tested** — 98.55% test coverage with 568 comprehensive tests
* **📦 Type-Safe** — Full type hints for better IDE support and mypy compatibility
* **🚀 Production-Ready** — Used in production for SEPA and international payments
* **💼 Enterprise Grade** — Robust error handling, comprehensive logging, and detailed reporting

Supported ISO 20022 Versions
=============================

.. list-table::
   :header-rows: 1
   :widths: 20 15 20 45

   * - Version
     - Status
     - CSV Fields
     - Primary Use Case
   * - pain.001.001.03
     - ✅ Stable
     - 42
     - SEPA credit transfers
   * - pain.001.001.04
     - ✅ Stable
     - 47
     - Non-SEPA international payments
   * - pain.001.001.05
     - ✅ Stable
     - 47
     - Enhanced global payments
   * - pain.001.001.06
     - ✅ Stable
     - 44
     - Instant SEPA payments
   * - pain.001.001.07
     - ✅ Stable
     - 44
     - Extended optional elements for regional requirements
   * - pain.001.001.08
     - ✅ Stable
     - 44
     - Enhanced validation and optional elements
   * - pain.001.001.09
     - ✅ Stable
     - 23
     - Modern simplified structure
   * - pain.001.001.10
     - ✅ Stable
     - 23
     - Enhanced compliance & validation
   * - pain.001.001.11
     - ✅ Latest
     - 23
     - Advanced features & future-proof
   * - pain.008.001.02
     - ✅ New
     - 26
     - SEPA direct debit initiation

Why Pain001?
============

**Reduce Complexity**
    Payment processing involves complex ISO 20022 standards and multiple validation steps. Pain001 handles all of this automatically.

**Ensure Compliance**
    Every generated file is validated against official XSD schemas, ensuring 100% compliance with payment networks.

**Save Time**
    Automated generation eliminates manual file creation and validation, reducing processing time from hours to minutes.

**Improve Reliability**
    With enterprise-grade error handling and comprehensive testing, Pain001 ensures consistent, reliable payment processing.

**Scale with Confidence**
    Process thousands of payments with the same confidence and reliability as a single payment.

Getting Started in 3 Steps
==========================

1. **Install**

   .. code-block:: bash

      pip install pain001

2. **Load Your Data**

   .. code-block:: python

      from pain001 import main

      main(
          xml_message_type='pain.001.001.03',
          xml_template_file_path='template.xml',
          xsd_schema_file_path='schema.xsd',
          data_file_path='payments.csv'
      )

3. **Get Validated Payment Files**

   Your ISO 20022-compliant XML payment file is generated and validated automatically.

Contents
========

.. toctree::
   :maxdepth: 2
   :caption: Documentation

   installation
   usage
   configuration
   version_migration
   security
   performance_large_batches
   additional_message_types
   structured_logging
   examples
   modules

.. toctree::
   :maxdepth: 2
   :caption: Additional Resources

   faq
   glossary

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
