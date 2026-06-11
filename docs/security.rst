Security
========

Pain001 applies several security controls relevant to payment processing:

* Path validation constrains template, schema, and data files to approved directories.
* XML parsing uses ``defusedxml`` protections.
* Template rendering uses a Jinja2 sandbox for XML generation and rejects filesystem directives such as ``include`` and ``extends``.
* Validation APIs reject paths that escape the working directory or temporary directories.
* Structured logging redacts common payment identifiers, and row-validation failures avoid printing raw IBAN/BIC values.

Operational notes:

* Keep templates and schemas under source control.
* Prefer the built-in validation and migration commands over ad hoc scripts.
* For large-file processing, use streaming mode to reduce memory pressure without widening file access.
* The library currently does not implement XML digital signatures, encryption, or certificate validation; those concerns remain external integration responsibilities.
