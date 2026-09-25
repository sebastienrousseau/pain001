.. SPDX-License-Identifier: Apache-2.0 OR MIT

=============================================
Pain001: ISO 20022-Compliant Payment Files
=============================================

Pain001 generates and validates payment XML from tabular data. The bundled
templates cover pain.001.001.03 through pain.001.001.13, pain.008.001.02 and
pain.008.001.08. List the exact registry with ``pain001 versions``; field
mappings are generated in :doc:`input-columns`, not duplicated here.

Generation validates rendered XML against the bundled XSD before writing.
Schema validity is not proof of bank acceptance or regulatory compliance.
Scenario confidence and evidence are documented in :doc:`corpus`.

Quality and availability
========================

CI enforces 100% line and branch coverage, lint, types and security checks.
Python 3.10–3.14 is tested on Linux; development uses Python 3.12.
Branch-only features and remaining acceptance criteria are recorded in
:doc:`issue-audit`; source documentation is not a release announcement.

Getting started
===============

Install the package, then run these commands in a fresh writable directory:

.. code-block:: bash

   pain001 init pain.001.001.03 -o payments.csv
   pain001 validate -t pain.001.001.03 -d payments.csv
   pain001 generate -t pain.001.001.03 -d payments.csv -o output

The scaffold is synthetic sample data. The output flag names a directory,
not a filename. See :doc:`installation`, :doc:`usage`, :doc:`configuration`
and :doc:`modules` for the supported surfaces.

Contents
========

.. toctree::
   :maxdepth: 2
   :caption: Documentation

   installation
   usage
   configuration
   plugins
   custom-rules
   sftp-upload
   template_registry
   version_migration
   security
   performance_large_batches
   performance_playbook
   validate_only_streaming
   additional_message_types
   async_adapters
   troubleshooting
   testing_quality
   structured_logging
   examples
   modules

.. toctree::
   :maxdepth: 2
   :caption: Additional Resources

   faq
   glossary

.. toctree::
   :maxdepth: 1
   :caption: Project

   architecture
   corpus
   twins
   input-columns
   message-deltas
   development
   packaging
   adr/README

.. toctree::
   :maxdepth: 1
   :caption: Assurance and policies
   :glob:

   POLICIES
   COMPARISON
   BENCHMARKS
   issue-audit
   code-scanning-audit
   assurance-case
   deployment-cookbook
   quickstart
   custom_validation
   adr/000[1-7]*
   posts/*

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
