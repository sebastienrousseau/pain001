Security
========

Pain001 applies several security controls relevant to payment processing:

* Path validation constrains template, schema, and data files to approved directories.
* XML parsing uses ``defusedxml`` protections.
* Template rendering uses Jinja2 sandboxing for XML generation.
* Validation APIs reject paths that escape the working directory or temporary directories.

Operational notes:

* Keep templates and schemas under source control.
* Prefer the built-in validation and migration commands over ad hoc scripts.
* For large-file processing, use streaming mode to reduce memory pressure without widening file access.

