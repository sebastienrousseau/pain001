=============
Configuration
=============

Pain001 supports layered configuration from built-in defaults, user config,
project config, environment variables, profiles, and direct CLI flags.

Precedence
==========

Lowest to highest:

1. Built-in defaults
2. ``~/.config/pain001/config.yaml``, ``config.yml`` or ``config.toml``
3. ``./pain001.yaml``, ``./pain001.yml``, ``./pain001.toml`` or
   ``./pain001.ini`` (the first one found)
4. The file named by ``--config FILE``
5. Environment variables
6. ``--profile``
7. Explicit CLI options

An INI file supplies only the ``[Paths]`` keys ``xml_template_file_path``,
``xsd_schema_file_path`` and ``data_file_path``. An unknown profile, an unknown
key or a value of the wrong type exits with code 2.

Supported Keys
==============

- ``xml_message_type``
- ``xml_template_file_path``
- ``xsd_schema_file_path``
- ``data_file_path``
- ``output_dir``
- ``streaming``
- ``chunk_size``
- ``emit_metrics``

Example YAML
============

.. code-block:: yaml

   xml_message_type: pain.001.001.11
   streaming: true
   chunk_size: 500
   profiles:
     production:
       emit_metrics: true
     sepa_v12:
       xml_message_type: pain.001.001.12

Built-In Presets
================

- ``sepa_credit_transfer``
- ``sepa_credit_transfer_v12``
- ``sepa_direct_debit``
- ``instant_credit_transfer``

CLI Examples
============

.. code-block:: bash

   pain001 --config pain001.yaml --profile production -d payments.csv
   pain001 --show-config -t pain.001.001.12 -d payments.csv

Environment Variables
=====================

- ``PAIN001_MESSAGE_TYPE``
- ``PAIN001_TEMPLATE_PATH``
- ``PAIN001_SCHEMA_PATH``
- ``PAIN001_DATA_PATH``
- ``PAIN001_OUTPUT_DIR``
- ``PAIN001_STREAMING``
- ``PAIN001_CHUNK_SIZE``
- ``PAIN001_EMIT_METRICS``

