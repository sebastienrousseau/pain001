==============
Async Adapters
==============

Pain001 remains synchronous internally, but the library ships lightweight
``asyncio`` wrappers for service integrations that need non-blocking call sites.
Each runs its synchronous counterpart in a worker thread and takes exactly the
same parameters: ``process_files_async`` accepts ``output_path``, BAH
enveloping, signing and schematron options, and ``process_files_streaming_async``
accepts ``output_dir`` and the same options.

Available Helpers
=================

- ``process_files_async``
- ``process_files_streaming_async``
- ``generate_xml_string_async``
- ``validate_all_async``

Example
=======

.. code-block:: python

   import asyncio

   from pain001 import process_files_async

   async def main() -> None:
       await process_files_async(
           "pain.001.001.11",
           "pain001/templates/pain.001.001.11/template.xml",
           "pain001/templates/pain.001.001.11/pain.001.001.11.xsd",
           "payments.csv",
           output_path="out/payments.xml",
       )

   asyncio.run(main())

