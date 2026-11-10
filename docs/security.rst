Security
========

Pain001 applies several security controls relevant to payment processing:

* Path validation constrains template, schema, and data files to approved directories. The command line is the one exception: a file its user names on it is that user's own and is read wherever it lives. The REST API, the MCP server and the dashboard take paths from a request and keep the restriction.
* XML parsing uses ``defusedxml`` protections.
* Template rendering uses a Jinja2 sandbox for XML generation and rejects filesystem directives such as ``include`` and ``extends``.
* Validation APIs reject paths that escape the working directory or temporary directories.
* Structured logging redacts common payment identifiers, and row-validation failures avoid printing raw IBAN/BIC values.

Operational notes:

* Keep templates and schemas under source control.
* Prefer the built-in validation and migration commands over ad hoc scripts.
* For large-file processing, use streaming mode to reduce memory pressure without widening file access.
* XML signing: ``sign_xml_document`` writes enveloped RSA-SHA256,
  RSA-PSS or ECDSA signatures using exclusive C14N 1.0 and the parsed
  document's namespace prefixes (install ``pain001[sign]``).
  ``verify_xml_signature`` requires the caller's public key or
  certificate; missing trust raises ``ValueError``. ``verify_signature``
  permits an explicit ``trust_embedded_cert=True`` integrity check and
  reports that trust choice. Certificate chains, expiry and revocation
  are not checked.
* Encryption: generated files are not encrypted. GPG-encrypted ``.gpg`` / ``.asc`` input files are decrypted with the ``gpg`` extra (``--decrypt-key``, ``--decrypt-passphrase-env``), and ``pain001 upload`` sends files over SSH.
* SFTP certificates: ``pain001 upload --certificate`` checks locally that an OpenSSH certificate was issued for the key and is inside its validity window; whether its authority and principals are trusted is the server's decision.
