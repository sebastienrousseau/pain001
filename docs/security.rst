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
* XML signing: ``sign_xml_document`` and ``verify_xml_signature`` implement W3C XML-DSig enveloped RSA-SHA256 signatures (install ``pain001[sign]``). Verification checks the signature against the public key or certificate you pass; it does not validate a certificate chain, expiry or revocation. Given neither, it uses the certificate embedded in the document, which proves the bytes are unchanged since signing but not who signed them, so pass the signer's key or certificate from a trusted source.
* Encryption: generated files are not encrypted. GPG-encrypted ``.gpg`` / ``.asc`` input files are decrypted with the ``gpg`` extra (``--decrypt-key``, ``--decrypt-passphrase-env``), and ``pain001 upload`` sends files over SSH.
* SFTP certificates: ``pain001 upload --certificate`` checks locally that an OpenSSH certificate was issued for the key and is inside its validity window; whether its authority and principals are trusted is the server's decision.
