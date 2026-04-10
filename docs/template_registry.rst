=================
Template Registry
=================

Pain001 now discovers bundled ISO 20022 templates from metadata files under
``pain001/templates/``.

What It Provides
================

- Query supported message types programmatically
- Resolve bundled template and schema paths automatically
- Validate template/schema/example drift with guardrails

Python Usage
============

.. code-block:: python

   from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

   template = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.001.001.11")
   print(template.template_path)
   print(template.xsd_path)

CLI Usage
=========

.. code-block:: bash

   pain001 --list-templates
   pain001 --show-template pain.001.001.12

Schema Guardrails
=================

Use the registry validation helper to catch template/schema drift early:

.. code-block:: python

   from pain001.templates import validate_registry

   validate_registry()

